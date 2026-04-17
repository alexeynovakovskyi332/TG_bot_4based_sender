from aiogram import types, F, Router

from bot.events import stop_event_async, stop_event_thread

router = Router()

@router.callback_query(F.data == "stop_spam")
async def stop_spam_handler(callback_query: types.CallbackQuery):

    stop_event_async.set()
    stop_event_thread.set()

    await callback_query.answer("Останавливаю рассылку…")

    try:
        await callback_query.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass