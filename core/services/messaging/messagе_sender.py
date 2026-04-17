from playwright.async_api import TimeoutError as PWTimeoutError
import logging

log = logging.getLogger("4based_bot")

_DEEP_FIND_JS = """
function deepFindTextarea(root) {
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
"""

_SHADOW_CHAIN_JS = """
function shadowChainTextarea() {
    const footer = document.querySelector('ion-footer.chat-write-area');
    if (!footer || !footer.shadowRoot) return null;
    const taHost = footer.shadowRoot.querySelector('text-area');
    if (!taHost || !taHost.shadowRoot) return null;
    const tac = taHost.shadowRoot.querySelector('text-autocomplete');
    if (!tac || !tac.shadowRoot) return null;
    const ion = tac.shadowRoot.querySelector('ion-textarea');
    if (!ion || !ion.shadowRoot) return null;
    return ion.shadowRoot.querySelector('textarea.native-textarea');
}
"""

_IS_TEXTAREA_READY_JS = """
() => {
    function deepFindTextarea(root) {
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
    function shadowChainTextarea() {
        const footer = document.querySelector('ion-footer.chat-write-area');
        if (!footer || !footer.shadowRoot) return null;
        const taHost = footer.shadowRoot.querySelector('text-area');
        if (!taHost || !taHost.shadowRoot) return null;
        const tac = taHost.shadowRoot.querySelector('text-autocomplete');
        if (!tac || !tac.shadowRoot) return null;
        const ion = tac.shadowRoot.querySelector('ion-textarea');
        if (!ion || !ion.shadowRoot) return null;
        return ion.shadowRoot.querySelector('textarea.native-textarea');
    }
    const ta = shadowChainTextarea() || deepFindTextarea(document);
    return ta !== null && !ta.disabled && !ta.readOnly;
}
"""

_IS_TEXTAREA_EMPTY_JS = """
() => {
    function deepFindTextarea(root) {
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
    const ta = deepFindTextarea(document);
    return !ta || ta.value === '';
}
"""

_READ_TEXTAREA_STATE_JS = f"""
() => {{
    {_DEEP_FIND_JS}
    {_SHADOW_CHAIN_JS}
    const ta = shadowChainTextarea() || deepFindTextarea(document);
    if (!ta) return 'NOT_FOUND';
    return JSON.stringify({{
        value: ta.value,
        disabled: ta.disabled,
        readOnly: ta.readOnly,
        focused: (document.activeElement === ta)
    }});
}}
"""


class MessageSender:

    async def fill_text(self, page, text: str, timeout: int = 10_000) -> bool:
        await page.wait_for_selector("ion-footer.chat-write-area", timeout=timeout)

        try:
            await page.wait_for_function(_IS_TEXTAREA_READY_JS, timeout=10_000)
        except PWTimeoutError:
            log.warning("fill_text: textarea не стала активной за 10 сек")
            return False

        focused = await page.evaluate(
            f"""
            () => {{
                {_DEEP_FIND_JS}
                {_SHADOW_CHAIN_JS}
                const ta = shadowChainTextarea() || deepFindTextarea(document);
                if (!ta) return false;
                ta.scrollIntoView({{block: 'center'}});
                ta.click();
                ta.focus();
                return true;
            }}
            """
        )
        if not focused:
            log.warning("fill_text: textarea не найдена для фокуса")
            return False

        log.info("fill_text: печатаю сообщение…")
        await page.keyboard.type(text, delay=50)

        try:
            await page.wait_for_function(
                f"""
                () => {{
                    {_DEEP_FIND_JS}
                    {_SHADOW_CHAIN_JS}
                    const ta = shadowChainTextarea() || deepFindTextarea(document);
                    return ta && ta.value.length > 0;
                }}
                """,
                timeout=3_000,
            )
            log.info("fill_text: ✅ текст введён")
            return True
        except PWTimeoutError:
            pass

        log.warning("fill_text: keyboard.type не дал результата — пробую через value+InputEvent")
        filled = await page.evaluate(
            f"""
            (text) => {{
                {_DEEP_FIND_JS}
                {_SHADOW_CHAIN_JS}
                const ta = shadowChainTextarea() || deepFindTextarea(document);
                if (!ta) return 'NO_TEXTAREA';
                ta.focus();
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value'
                ).set;
                setter.call(ta, text);
                ta.dispatchEvent(new InputEvent('input', {{
                    bubbles: true, composed: true,
                    data: text, inputType: 'insertText'
                }}));
                ta.dispatchEvent(new Event('change', {{bubbles: true}}));
                return 'OK';
            }}
            """,
            text,
        )
        if filled != "OK":
            log.error("fill_text: fallback не нашёл textarea (вернул: %s)", filled)
            return False

        try:
            await page.wait_for_function(
                f"""
                () => {{
                    {_DEEP_FIND_JS}
                    {_SHADOW_CHAIN_JS}
                    const ta = shadowChainTextarea() || deepFindTextarea(document);
                    return ta && ta.value.length > 0;
                }}
                """,
                timeout=3_000,
            )
            log.info("fill_text: ✅ текст введён через fallback")
            return True
        except PWTimeoutError:
            state = await page.evaluate(_READ_TEXTAREA_STATE_JS)
            log.error("fill_text: ❌ текст не появился. Состояние: %s", state)
            return False

    async def send_enter(self, page, timeout: int = 10_000) -> None:
        # Пробуем кликнуть кнопку Send напрямую (она в shadowRoot text-area)
        sent = await page.evaluate(
            """
            () => {
                const ta = document.querySelector('text-area');
                if (!ta || !ta.shadowRoot) return 'no_shadow';
                const btn = ta.shadowRoot.querySelector('ion-button.send');
                if (!btn) return 'no_btn';
                if (btn.disabled || btn.classList.contains('button-disabled')) return 'btn_disabled';
                btn.click();
                return 'clicked';
            }
            """
        )
        log.info("send_enter: Send button → %s", sent)

        if sent == "clicked":
            try:
                await page.wait_for_function(_IS_TEXTAREA_EMPTY_JS, timeout=timeout)
                log.info("send_enter: ✅ отправлено кнопкой Send")
                return
            except PWTimeoutError:
                log.warning("send_enter: Send button не очистил textarea — fallback Enter")

        # Fallback: keyboard Enter
        await page.evaluate(
            f"""
            () => {{
                {_DEEP_FIND_JS}
                {_SHADOW_CHAIN_JS}
                const ta = shadowChainTextarea() || deepFindTextarea(document);
                if (ta) ta.focus();
            }}
            """
        )
        await page.keyboard.press("Enter")
        log.info("send_enter: Enter нажат")

        try:
            await page.wait_for_function(_IS_TEXTAREA_EMPTY_JS, timeout=timeout)
            log.info("send_enter: ✅ отправлено через Enter")
        except PWTimeoutError:
            log.warning("send_enter: textarea не очистилась — продолжаем")
