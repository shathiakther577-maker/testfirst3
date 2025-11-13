from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def get_services_menu_keyboard() -> str:
    """Возвращает клавиатуру для меню сервисов"""

    keyboard = VkKeyboard(one_time=False, inline=False)

    keyboard.add_button(label="Промокоды", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button(label="Кланы", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()

    keyboard.add_button(label="Мои чаты", color=VkKeyboardColor.POSITIVE)
    keyboard.add_button(label="Статистика", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()

    keyboard.add_button(label="Назад", color=VkKeyboardColor.NEGATIVE)

    return keyboard.get_keyboard()
