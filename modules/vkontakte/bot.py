import json
import random
import vk_api
import aiohttp
import requests
from aiohttp import ClientSession
import concurrent
from settings import VkBotSettings


async def send_message(
        peer_id: int,
        message: str | None = None,
        keyboard: str | None = None,
        attachment: str | None = None,
        sticker_id: int | None = None,
        mention: bool = False  # Упоминать ли пользователя @id(пользователь)
) -> int | dict | None:
    """Отправляет сообщения в вк"""

    if message is None and attachment is None and sticker_id is None:
        return

    async with aiohttp.ClientSession() as session:

        if message is not None:
            # Удаление пробелов в начале каждой строки
            message = message.split("\n")
            new_message = []
            for i in message:
                new_message.append(i.strip())

            message = "\n".join(new_message)
        else:
            message = ""

        payload = {
            "message": message,
            "peer_id": peer_id,
            "random_id": random.randint(-2147483648, 2147483647),
            "access_token": VkBotSettings.GROUP_ACCESS_TOKEN,
            "v": VkBotSettings.API_VERSION
        }

        if len(message) > 4096:
            last_space = message[:4096].rindex(" ")
            payload["message"] = message[:last_space]
        else:
            payload["attachment"] = attachment

        if not mention:
            payload["disable_mentions"] = 1
            # 1 - отключить уведомление об упоминании в сообщении.

        if keyboard is not None:
            payload["keyboard"] = keyboard

        if sticker_id is not None:
            payload["sticker_id"] = sticker_id

        url = "https://api.vk.com/method/messages.send"
        try:
            response = await session.post(url, data=payload)
            response = await response.json()

            if len(message) > 4096:
                return await send_message(peer_id, message[last_space:], attachment=attachment)
            else:
                return response["response"]

        except (concurrent.futures._base.CancelledError):  # noqa
            return {"error": "aiohttp concurrent.futures._base.CancelledError"}

        except:
            return response if "response" in locals() else {"error": "vk is not available"}


async def send_mailing_message(
        *,
        session: ClientSession,
        peer_ids: list[int],
        message: str | None = None,
        keyboard: str | None = None,
        attachment: str | None = None,
) -> None:
    """Отправляет массовые сообщения в вк"""

    try:
        await session.post(
            url="https://api.vk.com/method/messages.send",
            data={
                "peer_ids": ",".join(str(x) for x in peer_ids),
                "message": message,
                "attachment": attachment,
                "keyboard": keyboard,
                "random_id": random.randint(-2147483648, 2147483647),
                "access_token": VkBotSettings.GROUP_ACCESS_TOKEN,
                "v": VkBotSettings.API_VERSION
            }
        )
    except:
        pass


async def delete_message(message_id: int) -> int | None:
    """Удаляет отправленные сообщения"""

    async with aiohttp.ClientSession() as session:
        data = {
            "v": VkBotSettings.API_VERSION,
            "access_token": VkBotSettings.GROUP_ACCESS_TOKEN,
            "delete_for_all": 1,
            "message_ids": message_id
        }

        try:
            response = await session.post(
                url="https://api.vk.com/method/messages.delete",
                data=data
            )
            response = await response.json()
            return response["response"]

        except:
            return None


async def send_keyboard(user_id, keyboard):
    """Отправляет клавиатуру без сообщения"""

    message = "&#13;"
    message_id = await send_message(user_id, message, keyboard)
    await delete_message(message_id=message_id)


async def get_upload_url() -> str:
    """Возвращает адрес сервера для загрузки фотографии вк"""

    async with aiohttp.ClientSession() as session:
        data = {
            "v": VkBotSettings.API_VERSION,
            "group_id": VkBotSettings.GROUP_ID,
            "access_token": VkBotSettings.GROUP_ACCESS_TOKEN
        }
        url = "https://api.vk.com/method/photos.getMessagesUploadServer"

        try:
            response = await session.post(url, data=data)
            response = await response.json()
            return response["response"]["upload_url"]
        except:
            return ""


async def upload_photo_on_server(upload_url: str, photo) -> dict:
    """Загружает фото на сервер вк"""

    async with aiohttp.ClientSession() as session:
        try:
            response = await session.post(upload_url, data={"photo": photo})
            response = await response.read()
            return json.loads(response.decode())
        except:
            return {"server": 0, "photo": "[]", "hash": ""}


async def save_photo(server, photo, hash) -> dict:
    """Сохраняет фотографию в личном сообщении после загрузки на сервер вк"""

    async with aiohttp.ClientSession() as session:
        data = {
            "server": server,
            "photo": photo,
            "hash": hash,
            "v": VkBotSettings.API_VERSION,
            "access_token": VkBotSettings.GROUP_ACCESS_TOKEN
        }
        url = "https://api.vk.com/method/photos.saveMessagesPhoto"

        try:
            response = await session.post(url, data=data)
            response = await response.json()
            return response["response"][0]
        except:
            return {"owner_id": 0, "id": 0, "access_key": ""}


async def upload_photo(photo) -> str:
    """Загружает фото в вк и возвращает путь до фото"""

    upload_url = await get_upload_url()
    upload_data = await upload_photo_on_server(upload_url, photo)
    photo_data = await save_photo(upload_data["server"], upload_data["photo"], upload_data["hash"])

    return f"photo{photo_data['owner_id']}_{photo_data['id']}_{photo_data['access_key']}"


async def get_short_link(url: str) -> str | dict:
    """Возвращает сокращенную ссылку, с помощью vk.cc"""

    async with aiohttp.ClientSession() as session:
        try:
            response = await session.post(
                url="https://api.vk.com/method/utils.getShortLink",
                data={
                    "v": VkBotSettings.API_VERSION,
                    "access_token": VkBotSettings.GROUP_ACCESS_TOKEN,
                    "private": 0,
                    "url": url
                }
            )
            response = await response.json()
            return response["response"]["short_url"]

        except (concurrent.futures._base.CancelledError):
            return {"error": "aiohttp concurrent.futures._base.CancelledError"}

        except:
            return response if "response" in locals() else {"error": "vk is not available"}


async def upload_document(
        document_path: str,
        document_name: str | None = None
) -> str:
    """Загружает документ в вк и возвращает путь до документа"""

    vk_session = vk_api.VkApi(token=VkBotSettings.OWNER_ACCESS_TOKEN)
    vk = vk_session.get_api()

    upload_url = vk.docs.getMessagesUploadServer(type='doc', peer_id=-VkBotSettings.GROUP_ID)['upload_url']
    document = json.loads(requests.post(upload_url, files={'file': open(document_path, 'rb')}).text)
    doc = vk.docs.save(file=document['file'], title=document_name, tags=[])["doc"]

    return f"doc{doc['owner_id']}_{doc['id']}"


async def publish_post(
        message: str,
        attachment: str | None = None
) -> None:
    """Публикует пост на странице сообщества"""

    async with aiohttp.ClientSession() as session:

        await session.post(
            url="https://api.vk.com/method/wall.post",
            data={
                "v": VkBotSettings.API_VERSION,
                "access_token": VkBotSettings.OWNER_ACCESS_TOKEN,
                "from_group": 1,
                "owner_id": -VkBotSettings.GROUP_ID,
                "message": "\n".join([x.strip() for x in message.split("\n")]),
                "attachments": attachment
            }
        )


async def is_user_in_group(user_id: int) -> bool:
    """Проверяет является ли пользователь членом группы"""

    async with aiohttp.ClientSession() as session:
        try:
            response = await session.post(
                url="https://api.vk.com/method/groups.isMember",
                data={
                    "v": VkBotSettings.API_VERSION,
                    "access_token": VkBotSettings.GROUP_ACCESS_TOKEN,
                    "group_id": VkBotSettings.GROUP_ID,
                    "user_id": user_id
                }
            )
            response = await response.json()
            return bool(response["response"])

        except (concurrent.futures._base.CancelledError):
            return {"error": "aiohttp concurrent.futures._base.CancelledError"}

        except:
            return response if "response" in locals() else {"error": "vk is not available"}
