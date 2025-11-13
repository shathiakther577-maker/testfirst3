from fastapi import APIRouter

from settings import FastApiSettings
from api.v1.handler import api_v1_router
from handlers.telegram_webhook import telegram_webhook_router

root_router = APIRouter(prefix=FastApiSettings.ROOT_PREFIX)

root_router.include_router(api_v1_router, prefix='/api/v1', tags=['API v1'])
root_router.include_router(telegram_webhook_router, prefix="/telegram", include_in_schema=False)
