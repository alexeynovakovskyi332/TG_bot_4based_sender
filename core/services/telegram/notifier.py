import logging
from aiogram import types

from core.models.models import SendResult


log = logging.getLogger("4based_bot")


class TelegramNotifier:
    """Всё что касается отправки сообщений в Telegram"""

    def __init__(self, msg: types.Message):
        self._msg = msg

    async def info(self, text: str):
        log.info("TG → %s", text)
        await self._msg.reply(text, parse_mode="Markdown")

    async def proxy_ok(self, idx: int, total: int, email: str, ip: str):
        await self.info(
            f"✅ [{idx}/{total}] `{email}` — прокси работает. IP: `{ip}`"
        )

    async def proxy_fail(self, idx: int, total: int, email: str, reason: str):
        await self.info(
            f"❌ [{idx}/{total}] `{email}` — прокси НЕ работает: `{reason}`"
        )

    async def proxy_summary(self, ok: int, total: int, bad: list[tuple[str, str]]):

        if not bad:
            await self.info(
                f"📊 Все прокси рабочие: ✅ {ok}/{total}"
            )
            return

        lines = [f"• `{e}`: {r}" for e, r in bad[:10]]

        more = (
            f"\n…и ещё {len(bad)-10}"
            if len(bad) > 10 else ""
        )

        await self.info(
            f"📊 Итог прокси:\n"
            f"✅ {ok}/{total} рабочих | "
            f"❌ {len(bad)}/{total} нерабочих\n\n"
            + "\n".join(lines)
            + more
            + "\n\n⚠️ Нерабочие аккаунты могут падать на логине."
        )

    async def worker_done(self, result: SendResult):
        processed = result.success_count + result.skip_count + result.error_count
        total_str = f" из {result.total}" if result.total else ""

        await self.info(
            f"📧 *{result.email}*\n"
            f"✅ Отправлено : *{result.success_count}*\n"
            f"⏭ Пропущено  : {result.skip_count}\n"
            f"❌ Ошибок     : {result.error_count}\n"
            f"📊 Всего      : {processed}{total_str}"
        )

    async def final(
        self,
        stopped: bool,
        total_success: int,
        total_errors: int
    ):

        status = (
            "⛔ Рассылка прервана."
            if stopped else
            "✅ Рассылка завершена."
        )

        await self.info(
            f"{status}\n\n"
            f"📊 Итого отправлено: "
            f"*{total_success}* сообщений"
            + (
                f"\n⚠️ Всего ошибок: {total_errors}"
                if total_errors else ""
            )
        )