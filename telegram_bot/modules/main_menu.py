from schemas.games import Games


def get_link_game_chat(game: Games) -> str:
    """Возвращает текст с инструкцией для добавления бота в чат с игрой"""

    game_name = game.value.replace("_", " ").title()
    
    return f"""
        Для игры в {game_name} добавьте бота в групповой чат и настройте игровой режим.
        
        Команды для владельца чата:
        /game {game.value} - установить игровой режим
        /timer <секунды> - установить таймер игры
        /help - помощь по управлению чатом
    """

