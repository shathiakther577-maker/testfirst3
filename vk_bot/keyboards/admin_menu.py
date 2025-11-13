from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def get_admin_menu_keyboard() -> str:
    """Возвращает клавиатуру для меню администраторов"""

    keyboard = VkKeyboard(one_time=False, inline=False)

    keyboard.add_button(
        label="Прибыль",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "incomes"}
    )
    keyboard.add_button(
        label="Cтатистика",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "statistics"}
    )
    keyboard.add_button(
        label="Актив",
        color=VkKeyboardColor.POSITIVE,
        payload={"event": "active"}
    )
    keyboard.add_line()

    keyboard.add_button(
        label="Топ",
        color=VkKeyboardColor.SECONDARY,
        payload={"event": "top_users"}
    )
    keyboard.add_button(
        label="Помощь",
        color=VkKeyboardColor.SECONDARY,
        payload={"event": "help"}
    )
    keyboard.add_button(
        label="Рассылка",
        color=VkKeyboardColor.SECONDARY,
        payload={"event": "mailing"}
    )
    keyboard.add_line()

    keyboard.add_button(
        label="Везунчики",
        color=VkKeyboardColor.SECONDARY,
        payload={"event": "luckys"}
    )
    keyboard.add_button(
        label="Лузеры",
        color=VkKeyboardColor.SECONDARY,
        payload={"event": "lusers"}
    )
    keyboard.add_line()

    keyboard.add_button(
        label="Меню",
        color=VkKeyboardColor.NEGATIVE,
        payload={"event": "go_main_menu"}
    )

    return keyboard.get_keyboard()
