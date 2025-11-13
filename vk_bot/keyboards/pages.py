from vk_api.keyboard import VkKeyboard, VkKeyboardColor


def add_back_page(
        keyboard: VkKeyboard,
        *,
        full_test: bool,
        payload: dict | None
) -> VkKeyboard:
    """Добавляет кнопку предыдущая страница"""

    keyboard.add_button(
        label="⏪ Предыдущая страница" if full_test else "⏪",
        color=VkKeyboardColor.SECONDARY,
        payload=payload
    )

    return keyboard


def add_next_page(
        keyboard: VkKeyboard,
        *,
        full_test: bool,
        payload: dict | None
) -> VkKeyboard:
    """Добавляет кнопку следующая страница"""

    keyboard.add_button(
        label="⏩ Следующая страница" if full_test else "⏩",
        color=VkKeyboardColor.SECONDARY,
        payload=payload
    )

    return keyboard
