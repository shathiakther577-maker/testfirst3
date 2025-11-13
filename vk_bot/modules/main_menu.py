from schemas.games import Games


def get_link_game_chat(game: Games) -> str:
    """Возвращает текст ссылкой на чат с игрой"""

    match game:

        case Games.AVIATOR:
            rooms = """
                Беседа #1
                https://vk.me/join/AJQ1d/5OXCHJdZFm_VVFkcZh
            """

        case Games.UNDER_7_OVER:
            rooms = """
                Беседа #1
                https://vk.me/join/AJQ1d/N7Qh05SQbwgH2OO7iR
            """

        case Games.DICE:
            rooms = """
                Беседа #1
                https://vk.me/join/AJQ1dyQ3Qh2V6VkEmjh3x3hS
            """

        case Games.MEGA_DICE:
            rooms = """
                Беседа #1
                https://vk.me/join/AJQ1d6Hq7x0OypJJNvXCCxwV
            """

        case Games.BLACK_TIME:
            rooms = """
                Беседа #1
                https://vk.me/join/AJQ1d/EiRyFpNQybzrk8wgU3
            """

        case Games.WHEEL:
            rooms = """
                Беседа #1
                https://vk.me/join/AJQ1d7sGOx2PFjGKLtfgiwzJ
            """

        case Games.DOUBLE:
            rooms = """
                Беседа #1
                https://vk.me/join/AJQ1d/SPSh1ffWaBuuOFk5i0
            """

        case Games.DREAM_CATCHER:
            rooms = """
                Беседа #1
                https://vk.me/join/AJQ1d3CYPR3cYLSx8jq45lPK
            """

        case Games.CUPS:
            rooms = """
                https://vk.me/join/fs5ySzlh74dl_RI8OyVP_xcwx3jrM26iXcU=
            """

        case Games.LUCKY_COINS:
            rooms = """
                Беседа #1
                https://vk.me/join/AJQ1d7bm2R0Pbi/N5fORSR6t
            """

        case _:
            rooms = "Не получилось найти чат"

    return f"Присоединяйся: \n\n{rooms}"
