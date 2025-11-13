import random
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from schemas.chats import ChatType, INCOME_CHAT_TYPE, CHAT_TYPE_COST
from schemas.games import ALL_GAMES, GAME_NAMES
from modules.additional import reduce_number


def get_keyboard_select_game_mode() -> str:
    """Возвращает клавиатуру выбора игрового режима"""

    MAX_ROW = 3  # Максимальное количество элементов строке
    MAX_BUTTONS = 9  # Максимальное количество кнопок (vk api 10)

    games = random.sample(ALL_GAMES, k=MAX_BUTTONS)
    keyboard = VkKeyboard(one_time=False, inline=False)

    for index, game in enumerate(games):

        if 0 < index < len(games) and index % MAX_ROW == 0:
            keyboard.add_line()

        keyboard.add_button(
            label=GAME_NAMES[game],
            color=VkKeyboardColor.POSITIVE,
            payload={
                "event": "select_game",
                "game": game.value
            }
        )

    if len(games) > 0:
        keyboard.add_line()

    keyboard.add_button(
        label="Обновить список",
        color=VkKeyboardColor.PRIMARY,
        payload={"event": "update_select_game"}
    )

    keyboard = keyboard.get_keyboard()

    return keyboard


def get_keyboard_select_chat_type() -> str:
    """Возвращает клавиатуру для выбора типа беседы"""

    keyboard = VkKeyboard(one_time=False, inline=False)

    for index, chat_type in enumerate(ChatType):

        if 0 < index < len(ChatType):
            keyboard.add_line()

        chat_type_name = chat_type.value
        chat_income = INCOME_CHAT_TYPE[chat_type]
        chat_costr = CHAT_TYPE_COST[chat_type]

        keyboard.add_button(
            label=f"{chat_type_name} {chat_income}% ({reduce_number(chat_costr)})",
            color=VkKeyboardColor.POSITIVE,
            payload={
                "event": "set_chat_type",
                "chat_type": chat_type
            }
        )

    if len(ChatType) > 0:
        keyboard.add_line()

    keyboard.add_button(
        label="Назад к выбору режима",
        color=VkKeyboardColor.NEGATIVE,
        payload={"event": "update_select_game"}
    )

    keyboard = keyboard.get_keyboard()

    return keyboard
