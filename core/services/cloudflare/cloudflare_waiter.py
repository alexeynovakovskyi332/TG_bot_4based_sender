import asyncio
import time


class CloudflareWaiter:

    async def wait(self, page, timeout: int = 30) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            title   = await page.title()
            content = await page.content()
            is_cf = (
                "Just a moment" in title
                or "Checking your browser" in title
                or "cf-browser-verification" in content
                or "challenge-platform" in content
                or "ray ID" in content.lower()
            )
            if not is_cf:
                return True
            await asyncio.sleep(2)
        return False