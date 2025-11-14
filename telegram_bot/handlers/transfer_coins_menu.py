import json
from psycopg2.extras import DictCursor
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from schemas.users import UserSchema, UserMenu
from schemas.transfer_coins import ExtraTransferCoins, MenuTransferCoins, \
    TransferCoinsError, get_transfer_coins_error_message

from services.transfer_coins import TransferCoinsService

from modules.additional import convert_number, format_number
from modules.databases.users import update_user_menu, update_user_extra_data, \
    get_user_data
from modules.telegram.bot import send_message
from modules.telegram.users import get_user_id

from telegram_bot.template_messages import BACK_MAIN_MENU, THIS_NOT_LINK
from telegram_bot.keyboards.other import back_keyboard
from telegram_bot.keyboards.main_menu import get_main_menu_keyboard


async def handler_transfer_coins_menu(
        *,
        user_id: int,
        user_data: UserSchema,
        message: str,
        psql_cursor: DictCursor
) -> None:
    """Обрабатывает сообщения в меню перевода коинов"""

    extra_data = ExtraTransferCoins(**user_data.extra_data)
    keyboard = back_keyboard

    if extra_data.menu == MenuTransferCoins.RECIPIENT:

        if message == "назад" or message == "меню":
            response = BACK_MAIN_MENU
            reply_keyboard, _ = get_main_menu_keyboard(user_data)
            keyboard = reply_keyboard

            update_user_menu(user_id, UserMenu.MAIN, psql_cursor)
            update_user_extra_data(user_id, None, psql_cursor)

        else:
            # Разделяем сообщение на части (username может быть с суммой)
            message_parts = message.strip().split()
            recipient_link = message_parts[0] if message_parts else message
            
            recipient_id = await get_user_id(recipient_link)
            recipient_data = get_user_data(recipient_id, psql_cursor)

            if recipient_id is None:
                response = THIS_NOT_LINK

            elif recipient_data is None:
                response = get_transfer_coins_error_message(
                    error=TransferCoinsError.UNREGISTERED_RECIPIENT
                )

            elif user_id == recipient_id:
                response = get_transfer_coins_error_message(
                    error=TransferCoinsError.CANT_SEND_COINS_TO_ONESELF
                )

            elif recipient_data.banned is True:
                response = get_transfer_coins_error_message(
                    error=TransferCoinsError.RECIPIENT_BANNED
                )

            else:
                # Адаптируем get_message_warning для Telegram
                status = recipient_data.status
                prefix = recipient_data.user_prefix
                
                if status in [UserStatus.USER]:
                    extra_text = ""
                elif status in [UserStatus.ADMIN, UserStatus.HONEST, UserStatus.MARKET]:
                    extra_text = f"Данный пользователь имеет обозначение {prefix}, что гарантирует честность"
                elif status in [UserStatus.SCAMMER]:
                    extra_text = f"Пользователь имеет обозначение «{prefix}», — замечен в мошенничестве"
                else:
                    extra_text = ""
                
                keyboard_buttons = []
                if prefix != "":
                    # В Telegram нет прямых ссылок в inline кнопках, используем URL кнопки
                    pass  # Можно добавить кнопку позже если нужно
                
                extra_text = f"{extra_text}\n\n" if extra_text else ""
                response = f"{extra_text}Для подтверждения перевода, введите количество"
                keyboard = back_keyboard

                update_user_extra_data(user_id, ExtraTransferCoins(
                    menu=MenuTransferCoins.AMOUNT,
                    recipient_id=recipient_id,
                    recipient_name=recipient_data.full_name
                ), psql_cursor)

    elif extra_data.menu == MenuTransferCoins.AMOUNT:

        if message == "назад":
            response = "Введи @username или ID игрока"
            update_user_extra_data(user_id, ExtraTransferCoins(), psql_cursor)

        elif message == "меню":
            response = BACK_MAIN_MENU
            reply_keyboard, _ = get_main_menu_keyboard(user_data)
            keyboard = reply_keyboard
            update_user_menu(user_id, UserMenu.MAIN, psql_cursor)
            update_user_extra_data(user_id, None, psql_cursor)

        else:
            amount = convert_number(message)

            if amount is not None and isinstance(amount, int) and int(amount) > 0:
                recipient_id = extra_data.recipient_id
                recipient_name = extra_data.recipient_name

                possibility_translation = TransferCoinsService.check_possibility(
                    sender_id=user_id, recipient_id=recipient_id,
                    amount=amount, psql_cursor=psql_cursor
                )

                if possibility_translation.access is True:
                    TransferCoinsService.send_coins(
                        sender_id=user_id, recipient_id=recipient_id,
                        amount=amount, psql_cursor=psql_cursor
                    )
                    response = f"✅ {recipient_name} получил {format_number(amount)} WC"
                    reply_keyboard, _ = get_main_menu_keyboard(user_data)
                    keyboard = reply_keyboard
                    update_user_menu(user_id, UserMenu.MAIN, psql_cursor)
                    update_user_extra_data(user_id, None, psql_cursor)

                else:
                    response = get_transfer_coins_error_message(
                        error=possibility_translation.error
                    )

            else:
                response = "😒 Это не похоже на число"

    await send_message(user_id, response, keyboard)

