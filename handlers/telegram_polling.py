import asyncio
import traceback
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from settings import TelegramBotSettings
from telegram_bot.routers.telegram_router import bot_event_router


async def telegram_polling() -> None:
    """Обработка запросов через polling"""

    application = Application.builder().token(TelegramBotSettings.BOT_TOKEN).build()

    # Обработчик текстовых сообщений
    async def message_handler(update: Update, context):
        if update.message:
            await bot_event_router(update, from_polling=True)

    # Обработчик callback query (нажатия на кнопки)
    async def callback_query_handler(update: Update, context):
        if update.callback_query:
            await bot_event_router(update, from_polling=True)

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_handler(CommandHandler("start", message_handler))
    application.add_handler(CommandHandler("help", message_handler))

    # Запуск polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    # Бесконечный цикл
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

