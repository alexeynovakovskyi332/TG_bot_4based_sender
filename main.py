import asyncio
import logging
import sys

# ── ЛОГИ: настраиваем ДО любых других импортов ──────────────────────────────
# force=True (Python 3.8+) сбрасывает любые обработчики, которые уже успел
# добавить aiogram или другие библиотеки, и ставит наш.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
# Убираем шум от сторонних библиотек
for _name in ("aiogram", "asyncio", "playwright", "aiohttp"):
    logging.getLogger(_name).setLevel(logging.WARNING)

# ── Импортируем бота ПОСЛЕ настройки логов ───────────────────────────────────
from bot.bot import dp, bot  # noqa: E402


async def main():
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())