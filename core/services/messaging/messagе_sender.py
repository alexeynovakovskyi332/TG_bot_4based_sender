from playwright.async_api import TimeoutError as PWTimeoutError


_DEEP_FIND_JS = """
function deepFindTextarea(root) {
...
}
"""

_SHADOW_CHAIN_JS = """
function shadowChainTextarea() {
...
}
"""


class MessageSender:

    async def fill_text(self, page, text: str, timeout: int = 10000) -> bool:
        await page.wait_for_selector("ion-footer.chat-write-area", timeout=timeout)

        return await page.evaluate(
            f"""
            async (text) => {{
                {_DEEP_FIND_JS}
                {_SHADOW_CHAIN_JS}
                let ta = shadowChainTextarea() || deepFindTextarea(document);
                if (!ta) return false;
                ta.focus();
                ta.value = text;
                ta.dispatchEvent(new Event('input', {{bubbles:true}}));
                return true;
            }}
            """,
            text
        )

    async def send_enter(self, page, timeout: int = 10000):

        sent = await page.evaluate(
            f"""
            async () => {{
                {_DEEP_FIND_JS}
                {_SHADOW_CHAIN_JS}
                let ta = shadowChainTextarea() || deepFindTextarea(document);
                if (!ta) return false;

                ta.dispatchEvent(new KeyboardEvent('keydown', {{key:'Enter'}}));
                return true;
            }}
            """
        )

        if not sent:
            raise RuntimeError("send failed")

        try:
            await page.wait_for_function(
                f"""
                () => {{
                    {_DEEP_FIND_JS}
                    const ta = deepFindTextarea(document);
                    return !ta || ta.value === '';
                }}
                """,
                timeout=timeout
            )
        except PWTimeoutError:
            raise RuntimeError("Textarea not cleared")