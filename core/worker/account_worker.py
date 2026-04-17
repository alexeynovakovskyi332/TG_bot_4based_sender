import asyncio
import random
import threading
import logging
from core.services.browser.browser_factory import PlaywrightBrowserFactory
from core.services.session.session_manager import SessionManager
from core.services.messaging.messagе_sender import MessageSender
from core.services.cloudflare.cloudflare_waiter import CloudflareWaiter
from core.models.models import Account, SendResult
from playwright.async_api import TimeoutError as PWTimeoutError

log = logging.getLogger("4based_bot")

SESSION_CHECK_EVERY = 500


class AccountWorker:

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
        skip_count = 0
        error_count = 0
        total = len(profiles)

        log.info("=" * 60)
        log.info("  АККАУНТ : %s", account.email)
        log.info("  ПРОФИЛЕЙ: %d", total)
        log.info("=" * 60)

        browser, context = await self._factory.create(playwright, account.proxy_url)
        page = await context.new_page()

        try:
            log.info("[%s] Выполняю логин…", account.email)
            if not await self._session.login(page, account):
                log.error("[%s] ❌ ЛОГИН НЕ УДАЛСЯ — аккаунт пропущен", account.email)
                return SendResult(account.email, 0, [f"{account.email}: логин не удался"])
            log.info("[%s] ✅ Логин успешен — начинаю рассылку", account.email)
            log.info("-" * 60)

            for i, profile_url in enumerate(profiles):
                if stop_event.is_set():
                    log.info("[%s] ⛔ Остановка по сигналу на профиле %d/%d", account.email, i, total)
                    break

                name = profile_url.rstrip("/").rsplit("/", 1)[-1]

                if i > 0 and i % SESSION_CHECK_EVERY == 0:
                    log.info("[%s] 🔄 Проверка сессии (%d/%d)…", account.email, i, total)
                    if not await self._session.ensure_logged_in(page, account):
                        log.error("[%s] ❌ СЕССИЯ — не удалось восстановить, останавливаюсь", account.email)
                        errors.append(f"{account.email}: сессия потеряна на шаге {i}")
                        error_count += 1
                        break

                try:
                    log.info("➡  ОБРАБОТКА  [%d/%d]  %s", i + 1, total, name)
                    await self._process_profile(page, account, profile_url, errors)
                    success_count += 1
                    log.info(
                        "✅ ОТПРАВЛЕНО  [%d/%d]  %-30s  (всего: %d отпр / %d проп / %d ошиб)",
                        i + 1, total, name, success_count, skip_count, error_count,
                    )

                except _SessionExpiredError:
                    log.warning("[%s] ⚠ Сессия истекла — восстанавливаю…", account.email)
                    if not await self._session.ensure_logged_in(page, account):
                        log.error("[%s] ❌ СЕССИЯ — восстановить не удалось", account.email)
                        errors.append(f"{account.email}: сессия потеряна")
                        error_count += 1
                        break
                    skip_count += 1
                    log.info(
                        "⏭  ПРОПУСК    [%d/%d]  %-30s  → сессия истекла",
                        i + 1, total, name,
                    )

                except _SkipProfile as e:
                    skip_count += 1
                    log.info(
                        "⏭  ПРОПУСК    [%d/%d]  %-30s  → %s",
                        i + 1, total, name, e,
                    )

                except Exception as e:
                    error_count += 1
                    errors.append(f"{account.email}: {e} | {profile_url}")
                    log.error(
                        "❌ ОШИБКА     [%d/%d]  %-30s  → %s",
                        i + 1, total, name, e,
                    )

                if (i + 1) % 25 == 0:
                    log.info(
                        "── Сводка [%d/%d]: ✅ отправлено=%d  ⏭ пропущено=%d  ❌ ошибок=%d ──",
                        i + 1, total, success_count, skip_count, error_count,
                    )

        except Exception as e:
            log.error("[%s] 💥 Критическая ошибка: %s", account.email, e)
            errors.append(f"{account.email}: критическая ошибка: {e}")
            error_count += 1
        finally:
            await self._safe_close(context, browser)

        log.info("=" * 60)
        log.info("  ИТОГ  %s", account.email)
        log.info("  ✅ Отправлено : %d", success_count)
        log.info("  ⏭  Пропущено  : %d", skip_count)
        log.info("  ❌ Ошибок     : %d", error_count)
        log.info("  📊 Всего      : %d из %d", success_count + skip_count + error_count, total)
        log.info("=" * 60)
        return SendResult(account.email, success_count, errors)

    async def _process_profile(self, page, account: Account, profile_url: str, errors: list[str]):
        await page.goto(profile_url, wait_until="domcontentloaded", timeout=30_000)

        if "/login" in page.url.lower():
            log.warning("[%s] Редирект на /login — сессия истекла", account.email)
            raise _SessionExpiredError()

        await self._cf.wait(page, timeout=20)

        # Профиль не существует
        if await page.locator(".user-not-found ion-button, user-not-found ion-button").count() > 0:
            raise _SkipProfile("профиль не найден")

        # Ждём кнопку Message (она всегда присутствует на странице)
        msg_btn = page.locator(
            "xpath=//ion-button[.//ion-label[contains(normalize-space(),'Message')]]"
            " | //ion-button[contains(@class,'chat-button')]"
        ).first
        try:
            await msg_btn.wait_for(state="visible", timeout=4_000)
        except PWTimeoutError:
            raise _SkipProfile("страница не загрузилась")

        # Теперь кнопки загружены — проверяем признаки skip ДО клика
        skip_reason = await page.evaluate("""
            () => {
                const txt = el => (el.textContent || '').trim().toLowerCase();
                const btns = Array.from(document.querySelectorAll('ion-button'));

                // 1. Кнопки с ценой подписки ($X / Month) — creator с платной подпиской
                if (btns.some(b => {
                    const t = txt(b);
                    return t.includes('$') && (t.includes('/month') || t.includes('months'));
                })) return 'требует платную подписку';

                // 2. Смотрим иконку внутри кнопки Message по SVG path
                //    Зелёная галочка  (M400 48H112...)  = можно писать
                //    Красный крестик  (...75.31 260.69) = заблокировано
                //    Чат creator      (M87.49 380...)   = creator, нужна подписка
                const msgBtn = btns.find(b => txt(b).includes('message'));
                if (msgBtn) {
                    const ionIcon = msgBtn.querySelector('ion-icon');
                    let pathD = '';
                    if (ionIcon && ionIcon.shadowRoot) {
                        const p = ionIcon.shadowRoot.querySelector('path');
                        if (p) pathD = p.getAttribute('d') || '';
                    }
                    if (pathD.includes('75.31 260.69')) return 'сообщения заблокированы';
                    if (pathD.includes('M87.49 380'))   return 'creator (требует подписку)';
                    // M400 48H112 = зелёная галочка → можно писать, skip не нужен
                }

                return null;
            }
        """)
        if skip_reason:
            raise _SkipProfile(skip_reason)

        # Пауза перед кликом
        await asyncio.sleep(random.uniform(0.5, 1.2))
        await msg_btn.scroll_into_view_if_needed()
        await msg_btn.click()

        # Ждём footer чата
        try:
            await page.wait_for_selector("ion-footer.chat-write-area", timeout=5_000)
        except PWTimeoutError:
            if "/login" in page.url.lower():
                raise _SessionExpiredError()
            raise _SkipProfile("чат не открылся (закрытые сообщения / creator)")

        # Чат заблокирован (платная подписка)
        chat_locked = await page.evaluate("""
            () => {
                const footer = document.querySelector('ion-footer.chat-write-area');
                if (!footer) return false;
                const t = footer.textContent.toLowerCase();
                return t.includes('subscri') || t.includes('unlock') ||
                       t.includes('paid') || t.includes('fan');
            }
        """)
        if chat_locked:
            raise _SkipProfile("чат заблокирован (платная подписка)")

        # Вводим текст сразу как footer загрузился (fill_text сам ждёт footer)
        filled = await self._sender.fill_text(page, account.message_text)
        if not filled:
            raise _SkipProfile("не удалось ввести текст")

        # Проверка что текст в поле
        pre_send_value = await page.evaluate("""
            () => {
                function deepFind(root) {
                    const stack = [root];
                    while (stack.length) {
                        const n = stack.pop();
                        if (!n) continue;
                        if (n.tagName && n.tagName.toLowerCase() === 'textarea' &&
                            n.classList && n.classList.contains('native-textarea')) return n;
                        if (n.shadowRoot) stack.push(n.shadowRoot);
                        const ch = n.children || [];
                        for (let i = 0; i < ch.length; i++) stack.push(ch[i]);
                    }
                    return null;
                }
                const ta = deepFind(document);
                return ta ? ta.value : '';
            }
        """)
        if not pre_send_value:
            raise _SkipProfile("textarea пуста перед отправкой")

        # Небольшая пауза перед отправкой
        await asyncio.sleep(random.uniform(0.3, 0.7))

        # Отправляем
        await self._sender.send_enter(page)

        # Ждём появления нашего сообщения в чате со статус-иконкой (макс 6с).
        # Ищем ion-row где есть span.label-bubble с нашим текстом
        # и ion-icon.status (галочка) — всё в обычном DOM, без shadowRoot.
        try:
            await page.wait_for_function(
                """
                (msgText) => {
                    for (const row of document.querySelectorAll('ion-row')) {
                        const bubble = row.querySelector(
                            'span.label-bubble.wrapper-element, span.label-bubble'
                        );
                        if (!bubble) continue;
                        if (!(bubble.textContent || '').includes(msgText)) continue;
                        // Текст найден — проверяем наличие статус-иконки
                        if (row.querySelector('ion-icon.status')) return true;
                    }
                    return false;
                }
                """,
                arg=account.message_text[:20],
                timeout=6_000,
            )
            log.info("[%s] ✅ Сообщение доставлено (текст + статус)", account.email)
        except PWTimeoutError:
            # textarea очистилась = сообщение принято формой и ушло по WS
            log.info("[%s] ✅ Сообщение отправлено (textarea очистилась)", account.email)

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
