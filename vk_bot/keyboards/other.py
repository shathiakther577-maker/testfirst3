from vk_api.keyboard import VkKeyboard, VkKeyboardColor


empty_keyboard = VkKeyboard().get_empty_keyboard()

back_keyboard = VkKeyboard(one_time=False, inline=False)
back_keyboard.add_button(label="Назад", color=VkKeyboardColor.NEGATIVE)
back_keyboard = back_keyboard.get_keyboard()

repeat_chat_subscription_keyboard = VkKeyboard(one_time=False, inline=True)
repeat_chat_subscription_keyboard.add_button(
    label="Повторить подписку",
    color=VkKeyboardColor.POSITIVE,
    payload={"event": "repeat_chat_subscription"}
)
repeat_chat_subscription_keyboard = repeat_chat_subscription_keyboard.get_keyboard()


def get_disabled_sub_chat_notif_keyboard(chat_id: int) -> str:
    """Возвращает клавиатуру для отключение уведомление об окончании подписки на чат"""

    keyboard = VkKeyboard(one_time=False, inline=True)

    keyboard.add_button(
        label="Отключить оповещения",
        color=VkKeyboardColor.NEGATIVE,
        payload={
            "handler": "processing_menus",
            "event": "disabled_sub_chat_notif",
            "chat_id": chat_id
        }
    )

    return keyboard.get_keyboard()
