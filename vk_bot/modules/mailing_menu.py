import time
import aiohttp
from enum import Enum
from pydantic import BaseModel
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from modules.vkontakte.bot import send_message, send_mailing_message


class MailingMenu(Enum):
    """Дополнительные меню для рассылки """

    ATTACHMENT = "attachment"  # Меню выбора фото
    MESSAGE = "message"  # Меню написания текста


class ExtraMailing(BaseModel):
    """Дополнительные данные для меню рассылки"""

    menu: MailingMenu = MailingMenu.ATTACHMENT
    attachment: str | None = None  # хранит фото


def get_mailing_menu_keyboard() -> str:
    """Возвращает клавиатуру для меню рассылки """

    keyboard = VkKeyboard(one_time=False, inline=False)

    keyboard.add_button(
        label="Пропустить",
        color=VkKeyboardColor.POSITIVE
    )
    keyboard.add_line()

    keyboard.add_button(
        label="Назад",
        color=VkKeyboardColor.NEGATIVE
    )

    return keyboard.get_keyboard()


def get_mailing_keyboard() -> str:
    """Возвращает клавиатуру которая будет отправлена с текстом рассылки"""

    keyboard = VkKeyboard(one_time=False, inline=True)

    keyboard.add_button(
        label="Играть",
        color=VkKeyboardColor.POSITIVE,
        payload={
            "handler": "processing_menus",
            "event": "start_play_game"
        }
    )
    keyboard.add_line()

    keyboard.add_button(
        label="Отключить рассылку",
        color=VkKeyboardColor.POSITIVE,
        payload={
            "handler": "processing_menus",
            "event": "switch_mailing"
        }
    )

    return keyboard.get_keyboard()


async def start_mailing(
        *,
        admin_id: int,
        user_ids: list[int | None],
        mailing_message: str,
        attachment: str | None
) -> None:
    """Запускает рассылку"""

    start_time = time.time()
    slice_user_ids = [user_ids[x:x+100] for x in range(0, len(user_ids), 100)]

    async with aiohttp.ClientSession() as session:
        mailing_keyboard = get_mailing_keyboard()

        for slice_users in slice_user_ids:
            await send_mailing_message(
                session=session, peer_ids=slice_users,
                message=mailing_message, keyboard=mailing_keyboard,
                attachment=attachment
            )

    work_time = round(time.time() - start_time)
    await send_message(
        peer_id=admin_id,
        message=f"""
            Рассылка закончена
            Бот отправил {len(user_ids)} сообщений за {work_time} сек. ({round(len(user_ids) / work_time)} в секунду)
        """
    )
