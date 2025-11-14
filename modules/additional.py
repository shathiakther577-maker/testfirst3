import math
from langid import classify


def strtobool(val: str | None) -> bool:
    """Конвертирует string в bool"""

    if val is None:
        return False

    if val in ("1", "y", "yes", "on", "true", "True"):
        return True

    if val in ("0", "n", "no", "off", "false", "False"):
        return False

    return False  # По умолчанию False, если значение не распознано


def format_number(number: int | float):
    """
    Преобразует числа
    # type int -> 1 000 000
    # type float -> 1 000 000.0
    """

    return f"{number:,}".replace(",", " ")


def convert_number(number: str) -> int | None:
    """Преобразует числа по типу 1кк в 1_000_000"""

    try:
        variants_k = ["к", "К", "k", "K"]
        count_k = sum([number.count(k) for k in variants_k])
        number = number.replace("к", "").replace("К", "")
        number = number.replace("k", "").replace("K", "")
        number = number.replace(" ", "").replace(",", ".")

        return int(float(number) * 1_000 ** count_k)

    except:
        return None


def reduce_number(number: int) -> str:
    """Преобразует числа по типу 1_000_000 в 1кк"""

    if number < 1_000:
        return str(number)

    count_k = int(math.log(number, 1_000))
    number = round(number / 1_000 ** count_k, 2)

    if number % 1 == 0:
        number = int(number)

    number = str(number)
    number += "к" * count_k

    return number


def get_word_case(number: int, words: tuple[str, str, str]) -> str:
    """Возвращает правильное склоненное слово в зависимости от числа"""

    if number % 10 == 1 and number % 100 != 11:
        return words[0]

    elif 2 <= number % 10 <= 4 and (number % 100 < 10 or number % 100 >= 20):
        return words[1]

    return words[2]


def detect_language(text: str) -> str:
    """Возвращает на каком языке написан текст"""

    return classify(text)[0]


def is_arabic_language(text: str) -> bool:
    """Проверяет написан ли текст на арабском"""

    return detect_language(text) == "ar"


def format_seconds_to_text(seconds: int) -> str:
    """Преобразует секунды в текст"""
    # д - дни, ч - часы, м - минту, с - секунды

    days = seconds // 86400
    hours = (seconds - days * 86400) // 3600
    minutes = (seconds - days * 86400 - hours * 3600) // 60
    seconds = seconds - days * 86400 - hours * 3600 - minutes * 60

    return f"""
        {"{:02.0f}д ".format(days) if days else ""} \
        {"{:02.0f}ч ".format(hours) if hours else ""} \
        {"{:02.0f}м ".format(minutes) if minutes else ""} \
        {"{:02.0f}с ".format(seconds) if seconds else ""} \
    """.strip().replace("   ", "")
