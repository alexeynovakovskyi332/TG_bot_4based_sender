import asyncio
import html
import logging
from collections import deque

from aiogram import Bot

log = logging.getLogger("4based_bot")


class TelegramLiveLogger(logging.Handler):
    """
    Logging-хэндлер, который перехватывает логи и отображает их
    в одном Telegram-сообщении, динамически редактируя его каждые N секунд.

    Использование:
        live = TelegramLiveLogger(bot, chat_id)
        logger = logging.getLogger("4based_bot")
        logger.addHandler(live)
        await live.start()
        ...
        logger.removeHandler(live)
        await live.stop()
    """

    MAX_LINES = 30          # сколько последних строк хранить
    UPDATE_INTERVAL = 3     # секунд между редактированиями сообщения
    MAX_CHARS = 3800        # лимит Telegram — 4096, оставляем запас

    def __init__(self, bot: Bot, chat_id: int) -> None:
        super().__init__()
        self._bot = bot
        self._chat_id = chat_id
        self._lines: deque[str] = deque(maxlen=self.MAX_LINES)
        self._message_id: int | None = None
        self._dirty = False
        self._task: asyncio.Task | None = None

    # ── public API ───────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Отправляет начальное сообщение и запускает фоновый цикл обновления."""
        msg = await self._bot.send_message(
            self._chat_id,
            "<pre>📋 Логи рассылки...\n</pre>",
            parse_mode="HTML",
        )
        self._message_id = msg.message_id
        self._task = asyncio.create_task(self._update_loop())

    async def stop(self) -> None:
        """Останавливает цикл и делает финальный flush."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self._flush()

    # ── logging.Handler ──────────────────────────────────────────────────────

    def emit(self, record: logging.LogRecord) -> None:
        line = self.format(record)
        self._lines.append(line)
        self._dirty = True

    # ── private ──────────────────────────────────────────────────────────────

    async def _update_loop(self) -> None:
        while True:
            await asyncio.sleep(self.UPDATE_INTERVAL)
            if self._dirty:
                await self._flush()

    async def _flush(self) -> None:
        if self._message_id is None or not self._lines:
            return

        text = self._build_text()
        try:
            await self._bot.edit_message_text(
                chat_id=self._chat_id,
                message_id=self._message_id,
                text=text,
                parse_mode="HTML",
            )
            self._dirty = False
        except Exception:
            # Telegram бросает ошибку если текст не изменился — игнорируем
            pass

    def _build_text(self) -> str:
        # Экранируем HTML-спецсимволы чтобы теги не ломали разметку
        lines = [html.escape(line) for line in self._lines]
        content = "\n".join(lines)

        # Обрезаем с конца если вышли за лимит
        if len(content) > self.MAX_CHARS:
            content = "...\n" + content[-self.MAX_CHARS:]

        return f"<pre>{content}</pre>"
