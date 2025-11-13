import random
import hashlib
from typing import Optional


ALLOWED_CHARACTERS = "abcdefghijklmnopqrstuvwxyz" \
                     "ABCDEFGHIJKLMNOPQRSTUVWXYZ" \
                     "0123456789"
# Допустимые символы при создании секретных ключей


BANNED_CHARACTERS = [
    "'", "\"", "`", "(", ")",
    "[", "]", "{", "}", "\\",
    "/", "\n", "+", "-", "*",
    "=", ":", ";", "⛔", "👑",
    "ㅤ", "　", "",
    "ا", "ب", "ت", "ث", "ج",
    "ح", "خ", "د", "ذ", "ر",
    "ز", "س", "ش", "ص", "ض",
    "ط", "ظ", "ع", "غ", "ف",
    "ق", "ك", "ل", "م", "ن",
    "ه", "و", "ي"
]  # Запрещенные символы в базе данных


class SecurityService:
    """Сервис защиты данных"""

    @staticmethod
    def generate_secret_key(*, length: int) -> str:
        """Возвращает сгенерированный секретный ключ"""

        return "".join(random.choices(ALLOWED_CHARACTERS, k=length))


    @staticmethod
    def signing_data(data: dict, secret_key: str) -> str:
        """Подписывает данные для передачи"""
        items = []

        for key in sorted(data.keys()):
            items.append(f"{key}={data[key]}")

        result = "&".join(items) + f"&{secret_key}"

        return hashlib.md5(result.encode()).hexdigest()


    @staticmethod
    def validate_data(data: dict, secret: str) -> bool:
        """Проверяет подлинность данных"""

        if data.get("sign"):
            signature = data["sign"]
            del data["sign"]

            return signature == SecurityService.signing_data(data, secret)

        return False


    @staticmethod
    def check_banned_symbols(string: str) -> list[Optional[str]]:
        """Возвращает запрещенные символы в строке если они есть"""

        banned_symbols = []

        for symbol in BANNED_CHARACTERS:
            if symbol in string:
                banned_symbols.append(symbol)

        return banned_symbols


    @staticmethod
    def replace_banned_symbols(string: str):
        """Возвращает строку без запрещенных символов"""

        for symbol in BANNED_CHARACTERS:
            string = string.replace(symbol, "")

        return string
