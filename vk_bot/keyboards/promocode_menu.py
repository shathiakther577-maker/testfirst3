from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def get_promocode_menu_keyboard() -> str:
    """Возвращает клавиатуру для меню промокодов"""

    keyboard = VkKeyboard(one_time=False, inline=False)

    keyboard.add_button(label="Активировать промокод", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()

    keyboard.add_button(label="Создать промокод", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()

    keyboard.add_button(label="Информация о промокодах", color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()

    keyboard.add_button(label="Назад", color=VkKeyboardColor.NEGATIVE)

    return keyboard.get_keyboard()
