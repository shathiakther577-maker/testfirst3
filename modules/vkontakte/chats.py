import aiohttp
from settings import VkBotSettings


async def get_chat_owner_id(
        chat_id: int
) -> int | None:
    """Возвращает идентификатор создателя чата"""

    try:
        async with aiohttp.ClientSession() as session:
            response = await session.post(
                url="https://api.vk.com/method/messages.getConversationMembers",
                data={
                    "v": VkBotSettings.API_VERSION,
                    "access_token": VkBotSettings.GROUP_ACCESS_TOKEN,
                    "fields": "occupation",
                    "peer_id": chat_id
                }
            )
            response = (await response.json())["response"]["items"]
            owner_id = [x["member_id"] for x in response if x.get("is_owner")][0]
            return owner_id

    except:
        return None
