from aiogram import types, F, Router

from bot.events import get_session

router = Router()


@router.callback_query(F.data == "stop_spam")
async def stop_spam_handler(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    session = get_session(user_id)

    if session is None:
        await callback_query.answer("Нет активной рассылки.")
        return

    stop_async, stop_thread = session
    stop_async.set()
    stop_thread.set()

    await callback_query.answer("Останавливаю рассылку…")

    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
