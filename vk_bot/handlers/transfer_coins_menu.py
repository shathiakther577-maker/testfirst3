from vk_api.keyboard import VkKeyboard
from psycopg2.extras import DictCursor

from schemas.users import UserSchema, UserMenu
from schemas.transfer_coins import ExtraTransferCoins, MenuTransferCoins, \
    TransferCoinsError, get_transfer_coins_error_message

from services.transfer_coins import TransferCoinsService

from modules.additional import convert_number, format_number
from modules.databases.users import update_user_menu, update_user_extra_data, \
    get_user_data
from modules.vkontakte.bot import send_message
from modules.vkontakte.users import get_user_id

from vk_bot.template_messages import BACK_MAIN_MENU, THIS_NOT_LINK
from vk_bot.keyboards.other import back_keyboard
from vk_bot.keyboards.main_menu import get_main_menu_keyboard


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
            keyboard = get_main_menu_keyboard(user_data)

            update_user_menu(user_id, UserMenu.MAIN, psql_cursor)
            update_user_extra_data(user_id, None, psql_cursor)

        else:
            recipient_id = await get_user_id(message)
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
                keyboard = VkKeyboard(one_time=False, inline=True)

                extra_text = TransferCoinsService.get_message_warning(recipient_data, keyboard)
                extra_text = f"{extra_text}\n\n" if extra_text else ""

                response = f"{extra_text}Для подтверждения перевода, введите количество"
                keyboard = keyboard.get_keyboard()

                update_user_extra_data(user_id, ExtraTransferCoins(
                    menu=MenuTransferCoins.AMOUNT,
                    recipient_id=recipient_id,
                    recipient_name=recipient_data.vk_name
                ), psql_cursor)

    elif extra_data.menu == MenuTransferCoins.AMOUNT:

        if message == "назад":
            response = "Введи ссылку на игрока"
            update_user_extra_data(user_id, ExtraTransferCoins(), psql_cursor)

        elif message == "меню":
            response = BACK_MAIN_MENU
            keyboard = get_main_menu_keyboard(user_data)
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
                    response = f"✅ {recipient_name} получил {format_number(amount)} BC"
                    keyboard = get_main_menu_keyboard(user_data)
                    update_user_menu(user_id, UserMenu.MAIN, psql_cursor)
                    update_user_extra_data(user_id, None, psql_cursor)

                else:
                    response = get_transfer_coins_error_message(
                        error=possibility_translation.error
                    )

            else:
                response = "😒 Это не похоже на число"

    await send_message(user_id, response, keyboard)
