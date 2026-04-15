import asyncio
import threading
import logging
from core.services.browser.browser_factory import PlaywrightBrowserFactory
from core.services.session.session_manager import SessionManager
from core.services.messaging.messagе_sender import MessageSender
from core.services.cloudflare.cloudflare_waiter import CloudflareWaiter
from core.models.models import Account, SendResult

log = logging.getLogger("4based_bot")

SESSION_CHECK_EVERY = 50


class AccountWorker:
    """
    Orchestrates: браузер → логин → рассылка по профилям.
    Зависит только от абстракций (DIP).
    """

    def __init__(
            self,
            browser_factory: PlaywrightBrowserFactory,
            session_manager: SessionManager,
            message_sender: MessageSender,
            cf_waiter: CloudflareWaiter,
    ):
        self._factory = browser_factory
        self._session = session_manager
        self._sender = message_sender
        self._cf = cf_waiter

    async def run(
            self,
            playwright,
            account: Account,
            profiles: list[str],
            stop_event: threading.Event,
    ) -> SendResult:
        errors: list[str] = []
        success_count = 0

        browser, context = await self._factory.create(playwright, account.proxy_url)
        page = await context.new_page()

        try:
            # ── первичный логин ──────────────────────────────────
            if not await self._session.login(page, account):
                return SendResult(account.email, 0, [f"{account.email}: логин не удался"])

            # ── рассылка ────────────────────────────────────────
            for i, profile_url in enumerate(profiles):
                if stop_event.is_set():
                    log.info("[%s] получен сигнал остановки на профиле %d", account.email, i)
                    break

                # плановая проверка сессии каждые SESSION_CHECK_EVERY профилей
                if i > 0 and i % SESSION_CHECK_EVERY == 0:
                    log.info(
                        "[%s] плановая проверка сессии (профиль %d/%d)…",
                        account.email, i, len(profiles),
                    )
                    if not await self._session.ensure_logged_in(page, account):
                        err = f"{account.email}: не удалось восстановить сессию на шаге {i}"
                        log.error(err)
                        errors.append(err)
                        break

                try:
                    await self._process_profile(page, account, profile_url, errors)
                    success_count += 1
                    log.info(
                        "[%s] ✅ сообщение отправлено (%d) → %s",
                        account.email, success_count, profile_url,
                    )

                except _SessionExpiredError:
                    log.warning("[%s] сессия вылетела → восстанавливаю", account.email)
                    if not await self._session.ensure_logged_in(page, account):
                        err = f"{account.email}: не удалось восстановить сессию"
                        log.error(err)
                        errors.append(err)
                        break
                    errors.append(f"{account.email}: пропущен {profile_url} из-за вылета сессии")

                except _SkipProfile as e:
                    log.debug("[%s] пропуск профиля %s: %s", account.email, profile_url, e)

                except Exception as e:
                    err = f"{account.email}: ошибка {e} для {profile_url}"
                    log.error(err)
                    errors.append(err)

        except Exception as e:
            err = f"{account.email}: критическая ошибка: {e}"
            log.error(err)
            errors.append(err)
        finally:
            await self._safe_close(context, browser)

        log.info(
            "[%s] завершено: отправлено=%d ошибок=%d",
            account.email, success_count, len(errors),
        )
        return SendResult(account.email, success_count, errors)

    # ── внутренние helpers ───────────────────────────────────────

    async def _process_profile(self, page, account: Account, profile_url: str, errors: list[str]):
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=30_000)

        if "/login" in page.url.lower():
            raise _SessionExpiredError()

        await self._cf.wait(page, timeout=20)
        await asyncio.sleep(3)

        # профиль не существует
        not_found = await page.locator(
            ".user-not-found ion-button, user-not-found ion-button"
        ).count()
        if not_found > 0:
            raise _SkipProfile("user-not-found")

        # кнопка Message
        msg_btn = None
        for xpath in [
            "//ion-button[.//ion-label[normalize-space()='Message']]",
            "//ion-button[.//ion-label[contains(normalize-space(),'Message')]]",
            "//ion-button[contains(@class,'chat-button')]",
        ]:
            loc = page.locator(f"xpath={xpath}")
            try:
                await loc.first.wait_for(state="visible", timeout=5_000)
                msg_btn = loc.first
                break
            except PWTimeoutError:
                continue

        if not msg_btn:
            raise _SkipProfile("кнопка Message не найдена")

        await msg_btn.scroll_into_view_if_needed()
        await msg_btn.click()

        # ждём footer чата
        try:
            await page.wait_for_selector("ion-footer.chat-write-area", timeout=10_000)
        except PWTimeoutError:
            if "/login" in page.url.lower():
                raise _SessionExpiredError()
            raise _SkipProfile("chat-footer не появился")

        await asyncio.sleep(2)

        filled = await self._sender.fill_text(page, account.message_text)
        if not filled:
            raise _SkipProfile("textarea не найдена")

        await asyncio.sleep(1)
        await self._sender.send_enter(page)
        await asyncio.sleep(2)

    @staticmethod
    async def _safe_close(context, browser):
        for obj in (context, browser):
            try:
                await obj.close()
            except Exception:
                pass


class _SessionExpiredError(Exception):
    pass


class _SkipProfile(Exception):
    pass
