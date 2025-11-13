from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from schemas.users import UserSchema


def get_settings_menu_keyboard(user_data: UserSchema) -> str:
    """Возвращает клавиатуру для меню настроек"""

    keyboard = VkKeyboard(one_time=False, inline=False)

    keyboard.add_button(
        label="Показывать баланс",
        color=VkKeyboardColor.POSITIVE if user_data.show_balance else VkKeyboardColor.NEGATIVE
    )
    keyboard.add_button(
        label="Рассылка",
        color=VkKeyboardColor.POSITIVE if user_data.mailing else VkKeyboardColor.NEGATIVE
    )
    keyboard.add_line()

    keyboard.add_button(
        label="Получить ключ api",
        color=VkKeyboardColor.SECONDARY
    )
    keyboard.add_button(
        label="Обновить ключ api",
        color=VkKeyboardColor.SECONDARY
    )
    keyboard.add_line()

    keyboard.add_button(
        label="Ник",
        color=VkKeyboardColor.POSITIVE
    )
    keyboard.add_button(
        label="Тег клана",
        color=VkKeyboardColor.POSITIVE if user_data.show_clan_tag else VkKeyboardColor.NEGATIVE
    )
    keyboard.add_line()

    keyboard.add_button(
        label="Назад",
        color=VkKeyboardColor.NEGATIVE
    )

    return keyboard.get_keyboard()
