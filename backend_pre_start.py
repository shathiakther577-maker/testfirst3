import os
import asyncio
import threading

from settings import Config
from handlers.telegram_polling import telegram_polling
from background_workers import BackgroundWorkers

# Не трогать, читай BaseGameModel.GAMES_MODEL
from schemas.games import Games

from games.base import BaseGameModel
from games.cups import CupsGameModel
from games.dice import DiceGameModel
from games.wheel import WheelGameModel
from games.double import DoubleGameModel
from games.aviator import AviatorGameModel
from games.mega_dice import MegaDiceGameModel
from games.black_time import BlackTimeGameModel
from games.lucky_coins import LuckyCoinsGameModel
from games.under_7_over import Under7OverGameModel
from games.dream_catcher import DreamCatcherGameModel
# Не трогать, читай BaseGameModel.GAMES_MODEL

from databases.redis import get_redis_cursor
from databases.postgresql import get_postgresql_connection


def init_old_games() -> None:
    """Запускает все действующие игры после рестарта бота"""

    redis_cursor = get_redis_cursor()
    psql_connect, psql_cursor = get_postgresql_connection()

    psql_cursor.execute("""
        SELECT games.game_id, games.game_mode
        FROM games JOIN rates ON games.game_id = rates.game_id
        WHERE games.is_active = TRUE AND
              games.end_datetime IS NULL
        GROUP BY games.game_id
        HAVING COUNT(rates.*) > 0
    """)
    waiting_game = psql_cursor.fetchall()

    psql_cursor.execute("""
        SELECT game_id, game_mode
        FROM games
        WHERE is_active = TRUE AND
              end_datetime IS NOT NULL
    """)
    running_games = psql_cursor.fetchall()

    games = {}
    for game in (waiting_game + running_games):
        games[game["game_id"]] = game
    games = list(games.values())

    for game in games:
        game_mode = Games(game["game_mode"])
        game_model = BaseGameModel.GAMES_MODEL[game_mode]
        game_model.init_game(game["game_id"], psql_cursor, redis_cursor)

    psql_cursor.close()
    psql_connect.close()
    redis_cursor.close()


def when_ready(_):
    """Запускает дополнительные компоненты проекта"""

    if not os.path.exists(Config.TEMP_FOLDER):
        os.mkdir(Config.TEMP_FOLDER)

    if not os.path.exists(Config.BACKUPS_FOLDER):
        os.mkdir(Config.BACKUPS_FOLDER)

    init_old_games()
    threading.Thread(target=asyncio.run, args=[BackgroundWorkers.run_workers()], daemon=True).start()

    if Config.DEVELOPMENT_MODE is True and Config.ON_SERVER is False:
        threading.Thread(target=asyncio.run, args=[telegram_polling()], daemon=True).start()
