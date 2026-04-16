from playwright.async_api import TimeoutError as PWTimeoutError
import logging

log = logging.getLogger("4based_bot")

# Глубокий поиск textarea через все shadowRoot
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

# Точная цепочка shadow DOM специфичная для 4based.com
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

# Проверка что textarea активна и готова к вводу
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

# Проверка что textarea очистилась (сообщение ушло)
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


class MessageSender:

    async def fill_text(self, page, text: str, timeout: int = 10_000) -> bool:
        await page.wait_for_selector("ion-footer.chat-write-area", timeout=timeout)

        # Ждём пока textarea станет активной (WebSocket инициализирован)
        try:
            await page.wait_for_function(_IS_TEXTAREA_READY_JS, timeout=10_000)
        except PWTimeoutError:
            log.warning("textarea не стала активной за 10 сек")
            return False

        filled = await page.evaluate(
            f"""
            async (text) => {{
                {_DEEP_FIND_JS}
                {_SHADOW_CHAIN_JS}

                let ta = shadowChainTextarea() || deepFindTextarea(document);
                if (!ta) return false;

                ta.scrollIntoView({{block: 'center'}});
                ta.focus();
                ta.value = text;
                ta.dispatchEvent(new Event('input',  {{bubbles: true}}));
                ta.dispatchEvent(new Event('change', {{bubbles: true}}));

                return true;
            }}
            """,
            text,
        )

        if not filled:
            log.warning("fill_text: textarea не найдена")
            return False

        # Убеждаемся что текст реально появился в поле
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
                timeout=5_000,
            )
        except PWTimeoutError:
            log.warning("fill_text: текст не появился в textarea после ввода")
            return False

        log.debug("fill_text: текст успешно введён")
        return True

    async def send_enter(self, page, timeout: int = 10_000) -> None:
        # Шаг 1: отправляем через KeyboardEvent
        await page.evaluate(
            f"""
            async () => {{
                {_DEEP_FIND_JS}
                {_SHADOW_CHAIN_JS}

                let ta = shadowChainTextarea() || deepFindTextarea(document);
                if (!ta) return false;

                ta.focus();
                const opts = {{
                    bubbles: true, cancelable: true,
                    key: 'Enter', code: 'Enter',
                    which: 13, keyCode: 13, composed: true
                }};
                ta.dispatchEvent(new KeyboardEvent('keydown',  opts));
                ta.dispatchEvent(new KeyboardEvent('keypress', opts));
                ta.dispatchEvent(new KeyboardEvent('keyup',    opts));
                return true;
            }}
            """
        )

        # Шаг 2: ждём очистки textarea — подтверждение что сообщение ушло
        try:
            await page.wait_for_function(_IS_TEXTAREA_EMPTY_JS, timeout=timeout)
            log.debug("send_enter: textarea очистилась — сообщение отправлено")
            return
        except PWTimeoutError:
            log.warning("send_enter: Enter не сработал — пробую кнопку submit")

        # Шаг 3 (fallback): кликаем кнопку отправки через shadow DOM
        sent_via_btn = await page.evaluate("""
            () => {
                const footer = document.querySelector('ion-footer.chat-write-area');
                const s0 = footer && footer.shadowRoot;
                const taHost = s0 && s0.querySelector('text-area');
                if (!taHost || !taHost.shadowRoot) return false;
                const form = taHost.shadowRoot.querySelector('form.write-area');
                if (!form) return false;
                const btn = form.querySelector('ion-button[type="submit"], button[type="submit"]');
                if (btn) { btn.click(); return true; }
                if (typeof form.requestSubmit === 'function') {
                    form.requestSubmit();
                    return true;
                }
                return false;
            }
        """)

        if not sent_via_btn:
            raise RuntimeError("send_enter: ни Enter ни кнопка submit не сработали")

        # Шаг 4: финальная проверка после кнопки
        try:
            await page.wait_for_function(_IS_TEXTAREA_EMPTY_JS, timeout=timeout)
            log.debug("send_enter: отправлено через кнопку submit")
        except PWTimeoutError:
            raise RuntimeError("send_enter: сообщение зависло в статусе отправки")