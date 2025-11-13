from telegram import Update

from telegram_bot.routers.handler_messages import handler_messages


async def bot_event_router(update: Update, from_polling: bool = False):
    """Направляет event на обработку"""

    if update.message:
        await handler_messages(update)
    elif update.callback_query:
        await handler_messages(update)

