import aiohttp
import xmltodict
import concurrent
from datetime import datetime

from settings import VkBotSettings


async def get_user_data(user: int | str) -> list | dict:
    """Возвращает данные пользователя по ссылке из vk
       :param user: идентификатор пользователя или короткое имя
    """

    async with aiohttp.ClientSession() as session:
        try:
            response = await session.post(
                url="https://api.vk.com/method/users.get",
                data={
                    "v": VkBotSettings.API_VERSION,
                    "access_token": VkBotSettings.GROUP_ACCESS_TOKEN,
                    "user_ids": user,
                    "fields": "followers_count"
                }
            )
            response = await response.json()
            return response["response"]

        except (concurrent.futures._base.CancelledError):
            return {"error": "aiohttp concurrent.futures._base.CancelledError"}

        except:
            return response if "response" in locals() else {"error": "vk is not available"}


async def get_user_name(user_id: int) -> tuple[str, str, str]:
    """Возвращает (имя, фамилию, полное имя) пользователя в вк"""

    user_data = (await get_user_data(user_id))[0]

    first_name = user_data["first_name"]
    last_name = user_data["last_name"]
    full_name = f"{first_name} {last_name}"

    return first_name, last_name, full_name


def get_user_from_link(link: str | int) -> str:
    """Возвращает идентификатора или имени пользователя из ссылки"""

    if isinstance(link, int):
        return link

    last_value = link.split("/")[-1]
    search_id = "id" in last_value

    if search_id and "|" in last_value:
        last_value = last_value.split("|")[0][1:]
        return last_value.replace("@", "", 1).replace("id", "", 1)

    elif search_id and last_value[2:].isnumeric():
        return last_value[2:]

    return last_value


async def get_user_id(link: str) -> int | None:
    """Возвращает идентификатора пользователя по ссылке"""

    response = await get_user_data(
        user=get_user_from_link(link)
    )

    if type(response) is list and len(response) != 0:
        return response[0].get("id")

    return None


async def get_user_friends(user_id: int) -> list[int | None]:
    """Возвращает индификаторы друзей"""

    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                url="https://api.vk.com/method/friends.get",
                data={
                    "v": VkBotSettings.API_VERSION,
                    "access_token": VkBotSettings.MINI_APPS_TOKEN,
                    "user_id": user_id
                }
            )
            response = await response.json()
            return response["response"]["items"]

    except:
        return []


async def get_friends_amount(user_id: int) -> int:
    """Возвращает количество друзей пользователя"""

    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                url="https://api.vk.com/method/friends.get",
                data={
                    "v": VkBotSettings.API_VERSION,
                    "access_token": VkBotSettings.MINI_APPS_TOKEN,
                    "user_id": user_id
                }
            )
            response = await response.json()
            return response["response"]["count"]

    except:
        return 0


async def get_followers_amount(user_id: int) -> int:
    """Возвращает количество подписчиков пользователя"""

    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                url="https://api.vk.com/method/users.get",
                data={
                    "v": VkBotSettings.API_VERSION,
                    "access_token": VkBotSettings.GROUP_ACCESS_TOKEN,
                    "user_ids": user_id,
                    "fields": "followers_count"
                }
            )
            response = await response.json()
            return response["response"][0]["followers_count"]

    except:
        return 0


async def get_registration_date(user_id: int) -> datetime:
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://vk.com/foaf.php?id={user_id}"

            response = await session.get(url)
            response = await response.text()
            response = response.replace("&", "")  # Чтобы не ругался xmltodict, на работу не влияет
            parsed_response = xmltodict.parse(response)
            registration_date = parsed_response["rdf:RDF"]["foaf:Person"]["ya:created"]["@dc:date"]
            registration_date = datetime.strptime(registration_date[:19], "%Y-%m-%dT%H:%M:%S")
            return registration_date

    except:
        return datetime.today()


async def kick_user_from_chat(
        user_id: int,
        chat_id: int
) -> None:
    """Исключает пользователя из чата"""

    async with aiohttp.ClientSession() as session:
        try:
            response = await session.post(
                url="https://api.vk.com/method/messages.removeChatUser",
                data={
                    "v": VkBotSettings.API_VERSION,
                    "access_token": VkBotSettings.GROUP_ACCESS_TOKEN,
                    "user_id": user_id,
                    "chat_id": chat_id
                }
            )
            response = await response.json()

        except (concurrent.futures._base.CancelledError):
            return {"error": "aiohttp concurrent.futures._base.CancelledError"}

        except:
            return response if "response" in locals() else {"error": "vk is not available"}
