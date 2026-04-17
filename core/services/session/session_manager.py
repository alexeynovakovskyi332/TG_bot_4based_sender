import asyncio
import logging

from core.models.models import Account
from core.services.cloudflare.cloudflare_waiter import CloudflareWaiter

log = logging.getLogger("4based_bot")


class SessionManager:

    def __init__(self, cf_waiter: CloudflareWaiter):
        self._cf = cf_waiter

    async def is_logged_in(self, page) -> bool:
        try:
            if "/login" in page.url.lower():
                return False
            result = await page.evaluate("""
                () => {
                    const hasAvatar   = !!document.querySelector('app-avatar, .user-avatar, ion-avatar');
                    const hasProfile  = !!document.querySelector('[routerlink="/profile"], [href="/profile"]');
                    const hasLoginBtn = !!document.querySelector('ion-button[routerlink="/login"]');
                    return (hasAvatar || hasProfile) && !hasLoginBtn;
                }
            """)
            return bool(result)
        except Exception:
            return False

    async def login(self, page, account: Account) -> bool:
        for attempt in range(1, 4):
            try:
                log.info("[%s] логин, попытка %d/3…", account.email, attempt)

                await page.goto(
                    "https://4based.com/login",
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )

                cf_ok = await self._cf.wait(page, timeout=30)

                if not cf_ok:
                    log.warning("[%s] Cloudflare не пройден (попытка %d)", account.email, attempt)
                    continue

                await page.wait_for_selector('[name="email"]', timeout=15000)
                await page.fill('[name="email"]', account.email)
                await page.fill('[name="password"]', account.password)

                btn = page.locator("ion-button.submit-button, button[type='submit']").first
                await btn.wait_for(state="visible", timeout=10_000)
                await btn.click()

                for _ in range(20):
                    if "/login" not in page.url.lower():
                        log.info("[%s] ✅ залогинен успешно (попытка %d)", account.email, attempt)
                        return True
                    await asyncio.sleep(0.5)

            except Exception:
                await asyncio.sleep(1)

        log.error("[%s] ❌ логин не удался после 3 попыток", account.email)
        return False

    async def ensure_logged_in(self, page, account: Account) -> bool:
        if await self.is_logged_in(page):
            return True
        log.warning("[%s] сессия истекла — перелогиниваюсь…", account.email)
        return await self.login(page, account)