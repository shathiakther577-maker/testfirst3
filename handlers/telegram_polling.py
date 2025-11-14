import asyncio
import traceback
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters

from settings import TelegramBotSettings
from telegram_bot.routers.telegram_router import bot_event_router


async def telegram_polling() -> None:
    """Обработка запросов через polling"""

    print("Starting Telegram bot polling...", flush=True)
    application = Application.builder().token(TelegramBotSettings.BOT_TOKEN).build()

    # Обработчик всех сообщений (включая команды и текстовые сообщения)
    async def message_handler(update: Update, context):
        if update.message:
            await bot_event_router(update, from_polling=True)

    # Обработчик callback query (нажатия на кнопки)
    async def callback_query_handler(update: Update, context):
        if update.callback_query:
            await bot_event_router(update, from_polling=True)

    # Обрабатываем все текстовые сообщения (включая команды)
    # В группах обрабатываем все сообщения, не только текстовые
    application.add_handler(MessageHandler(filters.TEXT | filters.COMMAND, message_handler))
    # Обрабатываем все остальные сообщения (фото, стикеры и т.д.) для групп
    application.add_handler(MessageHandler(filters.ALL & ~filters.TEXT & ~filters.COMMAND & ~filters.StatusUpdate.ALL, message_handler))
    # Обрабатываем callback queries
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    # Запуск polling
    print("Initializing application...", flush=True)
    await application.initialize()
    print("Starting application...", flush=True)
    await application.start()
    print("Starting polling...", flush=True)
    await application.updater.start_polling()
    print("Bot is running and waiting for messages...", flush=True)
    
    # Бесконечный цикл
    try:
        # Используем бесконечный цикл вместо Event().wait() для лучшей совместимости с systemd
        while True:
            await asyncio.sleep(3600)  # Спим час, но проверяем каждую секунду через stop_event
    except KeyboardInterrupt:
        print("Stopping bot...", flush=True)
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
    except Exception as e:
        print(f"Error in bot: {e}", flush=True)
        import traceback
        traceback.print_exc()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

