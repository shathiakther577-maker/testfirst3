from settings import NotifyChats
from modules.telegram.bot import send_message


class NotificationsService:
    """Сервис отправление логов администратором проекта"""

    @staticmethod
    async def send_notification(
            chat: NotifyChats,
            message: str
    ) -> None:
        """Отправить уведомление"""

        await send_message(chat.value, message)
