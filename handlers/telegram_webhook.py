import json
import traceback
from fastapi import APIRouter, Request, HTTPException
from telegram import Update, Bot

from settings import TelegramBotSettings
from telegram_bot.routers.telegram_router import bot_event_router


telegram_webhook_router = APIRouter()


@telegram_webhook_router.post("/webhook")
async def telegram_webhook_handler(request: Request) -> dict:
    """Обработка webhook от Telegram"""

    try:
        body = await request.json()
        update = Update.de_json(body, Bot(token=TelegramBotSettings.BOT_TOKEN))
        
        if update:
            await bot_event_router(update, from_polling=False)
        
        return {"ok": True}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "error": str(e)}

