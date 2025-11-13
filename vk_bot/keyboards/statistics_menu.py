from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def get_statistics_menu_keyboard() -> str:
    """Возвращает клавиатуру для меню статистики"""

    keyboard = VkKeyboard(one_time=False, inline=False)

    keyboard.add_button(
        label="🔝 Топ",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "get_bet_balance_message"}
    )
    keyboard.add_button(
        label="♻ Переводы",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "get_transfers_statistics_message"}
    )
    keyboard.add_line()

    keyboard.add_button(
        label="Назад",
        color=VkKeyboardColor.NEGATIVE
    )

    return keyboard.get_keyboard()
