from typing import Optional
from playwright_stealth import Stealth

from core.services.proxy.proxy_parser import ProxyParser


class PlaywrightBrowserFactory:

    def __init__(self, proxy_parser: ProxyParser):
        self._proxy_parser = proxy_parser

    async def create(self, playwright, proxy_url: Optional[str]):
        proxy_dict = self._proxy_parser.to_playwright_dict(proxy_url) if proxy_url else None

        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--lang=en-US",
            ],
        )
        ctx_kwargs = {
            "viewport": {"width": 1280, "height": 900},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "locale": "en-US",
            "timezone_id": "Europe/London",
            "java_script_enabled": True,
            "ignore_https_errors": True,
        }
        if proxy_dict:
            ctx_kwargs["proxy"] = proxy_dict

        context = await browser.new_context(**ctx_kwargs)

        stealth = Stealth()
        await stealth.apply_stealth_async(context)

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'platform',  {get: () => 'Win32'});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
            Object.defineProperty(navigator, 'plugins',   {get: () => [1,2,3]});
        """)

        return browser, context