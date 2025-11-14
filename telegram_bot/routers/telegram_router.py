from telegram import Update

from telegram_bot.routers.handler_messages import handler_messages


async def bot_event_router(update: Update, from_polling: bool = False):
    """Направляет event на обработку"""

    try:
        print(f"[ROUTER] Update received: message={update.message is not None}, callback={update.callback_query is not None}", flush=True)
        if update.message:
            await handler_messages(update)
        elif update.callback_query:
            await handler_messages(update)
        print(f"[ROUTER] handler_messages completed", flush=True)
    except Exception as e:
        print(f"[ROUTER ERROR] {e}", flush=True)
        import traceback
        traceback.print_exc()

