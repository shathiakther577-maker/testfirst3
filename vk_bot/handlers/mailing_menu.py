import asyncio
import threading
from psycopg2.extras import DictCursor

from schemas.users import UserSchema, UserMenu
from modules.vkontakte.bot import send_message
from modules.databases.users import update_user_menu, update_user_extra_data

from vk_bot.modules.mailing_menu import ExtraMailing, MailingMenu, get_mailing_menu_keyboard, \
    start_mailing
from vk_bot.keyboards.other import back_keyboard
from vk_bot.keyboards.admin_menu import get_admin_menu_keyboard


async def handler_mailing_menu(
        *,
        admin_id: int,
        admin_data: UserSchema,
        message: str,
        original_message: str,
        psql_cursor: DictCursor
) -> None:
    """Обрабатывает сообщение в меню рассылки"""

    extra_data = ExtraMailing(**admin_data.extra_data)

    if extra_data.menu == MailingMenu.ATTACHMENT:

        if message == "назад":
            response = "Админ панель"
            keyboard = get_admin_menu_keyboard()

            update_user_menu(admin_id, UserMenu.ADMIN, psql_cursor)
            update_user_extra_data(admin_id, None, psql_cursor)

        elif message == "пропустить":
            response = "Введи текст рассылки\nНе забудь указать ; в конце!"
            keyboard = back_keyboard

            extra_data.menu = MailingMenu.MESSAGE
            update_user_extra_data(admin_id, extra_data, psql_cursor)

        else:
            response = "Введи текст рассылки\nНе забудь указать ; в конце!"
            keyboard = back_keyboard

            extra_data.menu = MailingMenu.MESSAGE
            extra_data.attachment = original_message
            update_user_extra_data(admin_id, extra_data, psql_cursor)

    elif extra_data.menu == MailingMenu.MESSAGE:

        if message == "назад":
            response = "Введи ссылку на вложение по типу photo-192514282_457381934 или нажми пропустить"
            keyboard = get_mailing_menu_keyboard()
            update_user_extra_data(admin_id, ExtraMailing(), psql_cursor)

        elif message[-1] == ";":
            psql_cursor.execute("""
                SELECT user_id FROM users
                WHERE mailing = TRUE
            """)
            user_ids = [x["user_id"] for x in psql_cursor.fetchall()]

            mailing_message = original_message.rsplit(";", 1)[0]
            threading.Thread(target=asyncio.run, args=[
                start_mailing(
                    admin_id=admin_id, user_ids=user_ids,
                    mailing_message=mailing_message, attachment=extra_data.attachment
                )
            ]).start()

            response = f"Получено {len(user_ids)} диалогов для рассылки"
            keyboard = get_admin_menu_keyboard()

            update_user_menu(admin_id, UserMenu.ADMIN, psql_cursor)
            update_user_extra_data(admin_id, None, psql_cursor)

        else:
            response = "Где ; ?"
            keyboard = back_keyboard

    await send_message(admin_id, response, keyboard)
