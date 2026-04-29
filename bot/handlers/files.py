import os
import asyncio
import logging

from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.bot import bot
from bot.events import create_session, remove_session
from bot.states.bot_states import BotStates

from core.models.models import Account
from core.services.telegram.notifier import TelegramNotifier
from core.services.telegram.live_logger import TelegramLiveLogger
from core.parser.account_file_parser import AccountFileParser
from core.services.proxy.proxy_parser import ProxyParser
from core.services.proxy.proxy_checker import ProxyChecker
from core.orchestrator.spam_orchestrator import SpamOrchestrator
from core.di.container import build_worker

router = Router()

proxy_parser_global = ProxyParser()
proxy_checker_global = ProxyChecker()
file_parser_global = AccountFileParser(proxy_parser_global)
orchestrator_global = SpamOrchestrator(build_worker)


@router.message(BotStates.waiting_first_file)
async def first_file_handler(message: types.Message, state: FSMContext):

    if not (message.document and message.document.mime_type == "text/plain"):
        return await message.reply("Загрузите .txt файл!")

    user_id = message.from_user.id
    tg_file = await bot.get_file(message.document.file_id)
    file_path = f"{user_id}_{message.document.file_name}"

    await bot.download_file(tg_file.file_path, file_path)

    accounts = file_parser_global.parse(file_path)

    os.remove(file_path)

    if not accounts:
        return await message.reply("Файл пуст")

    notifier = TelegramNotifier(message)

    await notifier.info("🔎 Проверяю прокси...")

    ok_count = 0
    bad = []

    for idx, acc in enumerate(accounts, 1):

        ok, result = proxy_checker_global.check(acc.proxy_url)

        if ok:
            ok_count += 1
            await notifier.proxy_ok(idx, len(accounts), acc.email, result)
        else:
            bad.append((acc.email, result))
            await notifier.proxy_fail(idx, len(accounts), acc.email, result)

    await notifier.proxy_summary(ok_count, len(accounts), bad)

    await state.update_data(
        accounts=[
            (a.email, a.password, a.message_text, a.proxy_url)
            for a in accounts
        ]
    )

    await state.set_state(BotStates.waiting_second_file)

    await notifier.info("📂 Теперь загрузите второй файл")


@router.message(BotStates.waiting_second_file)
async def second_file_handler(message: types.Message, state: FSMContext):

    if not (message.document and message.document.mime_type == "text/plain"):
        return await message.reply("Загрузите .txt файл!")

    user_id = message.from_user.id
    tg_file = await bot.get_file(message.document.file_id)
    file_path = f"{user_id}_{message.document.file_name}"

    await bot.download_file(tg_file.file_path, file_path)

    with open(file_path, encoding="utf-8") as f:
        profiles = [l.strip() for l in f if l.strip()]

    os.remove(file_path)

    data = await state.get_data()

    accounts = [
        Account(e, p, m, px)
        for e, p, m, px in data["accounts"]
    ]

    await state.clear()

    stop_async, stop_thread = create_session(user_id)

    stop_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⛔ Остановить рассылку",
                    callback_data="stop_spam"
                )
            ]
        ]
    )

    await message.reply(
        f"✍ Рассылка запущена\n"
        f"Аккаунтов: {len(accounts)}\n"
        f"Профилей: {len(profiles)}",
        reply_markup=stop_kb
    )

    notifier = TelegramNotifier(message)

    # Создаём живой логгер — одно сообщение в Telegram, которое редактируется
    bot_logger = logging.getLogger("4based_bot")
    live_log = TelegramLiveLogger(bot, message.chat.id)
    live_log.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
    bot_logger.addHandler(live_log)
    await live_log.start()

    try:
        await orchestrator_global.run(
            accounts,
            profiles,
            notifier,
            stop_async,
            stop_thread
        )
    finally:
        bot_logger.removeHandler(live_log)
        await live_log.stop()
        remove_session(user_id)
