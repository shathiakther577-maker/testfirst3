import os
import math
import random
import asyncio
import threading
from pathlib import Path
from redis.client import Redis
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from settings import Config

from painter import Painter
from schemas.redis import RedisKeys
from services.security import SecurityService
# upload_photo будет реализован в modules.telegram.bot при необходимости


class CaptchaService:

    @staticmethod
    def generate_captcha_name() -> str:
        """Генерирует текст для капчи"""

        return SecurityService.generate_secret_key(length=8)


    @staticmethod
    def generate_similar_strings(original_str: str) -> str:
        """Создает похожие строки на 50 = 0.5 %"""

        first_char, rest = original_str[0], list(original_str[1:])
        random.shuffle(rest)

        num_chars_to_change = int(len(original_str) * 0.5)
        for i in range(num_chars_to_change):
            index = random.randint(1, len(original_str) - 2)
            rest[index], rest[i] = rest[i], rest[index]

        return first_char + ''.join(rest)


    @staticmethod
    def generate_captcha_args(captcha_name: str) -> dict["str", list[dict]]:
        """Генерирует значение для создания фото капчи"""

        symbols = {"parts": []}

        for symbol in captcha_name:

            rgb = [
                random.randint(0, 50),
                random.randint(77, 177),
                random.randint(200, 255)
            ]
            random.shuffle(rgb)  # Перемешанный цвет символа

            translate_y = random.randint(-225, 250)  # Поднимает или опускает символ
            rotate = random.randint(-359, 359)  # Угол поворота символа
            skew = (
                random.randint(-10, 10),
                random.randint(-10, 10)
            )  # Искажение символа в 2D
            scale = (
                round(random.uniform(1.0, 1.3), 3),
                round(random.uniform(1.0, 1.3), 3)
            )  # Увеличение масштаба символа по X и Y

            symbols["parts"].append({
                "name": symbol,
                "rgb": rgb,
                "translateY": translate_y,
                "rotate": rotate,
                "skew": skew,
                "scale": scale
            })

        return symbols


    @classmethod
    async def _create_captcha(cls) -> tuple[str, str]:
        """Создает капчу возвращает текст и путь до фото капчи"""

        captcha_name = cls.generate_captcha_name()
        img_path = await Painter.draw_image(
            width=1080, height=1080,
            template_path=Path(Config.PROJECT_ROOT, "painter", "captcha", "template.html"),
            jinja_args=cls.generate_captcha_args(captcha_name)
        )
        return captcha_name, img_path


    @classmethod
    async def create_captcha_photos(cls) -> None:
        """Создает заданное количество фотографий капч не больше 35"""

        while True:
            if len([x for x in os.listdir(Config.TEMP_FOLDER) if x.startswith("captcha_")]) < 100:
                captcha_name, img_path = await cls._create_captcha()
                os.replace(img_path, Path(Config.TEMP_FOLDER, f"captcha_{captcha_name}.png"))
            else:
                break


    @classmethod
    async def get_captcha(cls) -> None:
        """Возвращает текста и attachment капчи"""

        files = [x for x in os.listdir(Config.TEMP_FOLDER) if x.startswith("captcha_")]
        files_len = len(files)

        if files_len <= 30:
            threading.Thread(
                target=asyncio.run, args=[cls.create_captcha_photos()], daemon=True
            ).start()

        if files_len > 0:
            captcha = random.choice(files)
            captcha_name = captcha[8:-4]
            captcha_path = Path(Config.TEMP_FOLDER, captcha)
        else:
            captcha_name, captcha_path = await cls._create_captcha()

        attachment = await upload_photo(open(captcha_path, "rb"))
        try:
            os.remove(captcha_path)
        except:
            pass

        return captcha_name, attachment


    @classmethod
    def create_captcha_keyboard(cls, captcha_name: str) -> str:
        """Создает и возвращает клавиатуру с выбором капчи"""

        keyboard = VkKeyboard(one_time=False, inline=False)

        captcha_names = [
            captcha_name,
            cls.generate_similar_strings(captcha_name),
            cls.generate_similar_strings(captcha_name),
            cls.generate_similar_strings(captcha_name),
            cls.generate_similar_strings(captcha_name),
            cls.generate_similar_strings(captcha_name)
        ]
        random.shuffle(captcha_names)

        for index, name in enumerate(captcha_names):

            if 0 < index < 6 and index % 2 == 0:
                keyboard.add_line()

            keyboard.add_button(
                label=name,
                color=VkKeyboardColor.PRIMARY,
                payload={"captcha_name": name}
            )

        keyboard.add_line()
        keyboard.add_button(
            label="Назад",
            color=VkKeyboardColor.NEGATIVE
        )

        return keyboard.get_keyboard()


    @staticmethod
    def get_captcha_attempts(
            user_id: int,
            redis_key: RedisKeys,
            redis_cursor: Redis
    ) -> int:
        """Возвращает количество попыток ввода капчи"""

        response = redis_cursor.get(f"{redis_key.value}:{user_id}")
        return int(response) if response else 0


    @staticmethod
    def set_captcha_attempts(
            user_id: int,
            redis_key: RedisKeys,
            redis_value: int,
            redis_cursor: Redis
    ) -> int:
        """Устанавливает количество попыток ввода капчи"""

        redis_cursor.set(f"{redis_key.value}:{user_id}", redis_value, ex=3_600)


    @staticmethod
    def del_captcha_attempts(
            user_id: int,
            redis_key: RedisKeys,
            redis_cursor: Redis
    ) -> None:
        """Удаляет количество прохождения капчи"""

        redis_cursor.delete(f"{redis_key.value}:{user_id}")


    @staticmethod
    def ban_service_access(
        user_id: int,
        redis_key: RedisKeys,
        redis_cursor: Redis
    ) -> None:
        """Запрещает доступ к сервису из за провала капчи"""

        redis_cursor.set(f"{redis_key.value}:{user_id}", 1, ex=600)


    @staticmethod
    def is_service_access(
        user_id: int,
        redis_key: RedisKeys,
        redis_cursor: Redis
    ) -> bool:
        """Проверяет есть ли у пользователя доступ к сервису"""

        return not bool(redis_cursor.get(f"{redis_key.value}:{user_id}"))


    @staticmethod
    def get_minutes_ban_access_services(
        user_id: int,
        redis_key: RedisKeys,
        redis_cursor: Redis
    ) -> int | None:
        """Возвращает на сколько минут пользователь отстранен от сервиса"""

        response = redis_cursor.ttl(f"{redis_key.value}:{user_id}")
        return math.ceil(int(response) / 60) if response else None
