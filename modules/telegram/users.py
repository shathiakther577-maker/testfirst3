from typing import Optional
from telegram import Bot
from settings import TelegramBotSettings


async def get_user_data(user_id: int) -> dict | None:
    """Возвращает данные пользователя по ID из Telegram"""

    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        user = await bot.get_chat(user_id)
        return {
            "id": user.id,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "username": user.username,
            "full_name": f"{user.first_name or ''} {user.last_name or ''}".strip()
        }
    except:
        return None


async def get_user_name(user_id: int) -> tuple[str, str, str]:
    """Возвращает (имя, фамилию, полное имя) пользователя в Telegram"""

    user_data = await get_user_data(user_id)
    if not user_data:
        return "", "", ""

    first_name = user_data.get("first_name", "")
    last_name = user_data.get("last_name", "")
    full_name = user_data.get("full_name", f"{first_name} {last_name}".strip())

    return first_name, last_name, full_name


def get_user_from_link(link: str | int) -> str:
    """Возвращает идентификатор или username пользователя из ссылки"""

    if isinstance(link, int):
        return str(link)

    # Убираем @ если есть
    link = link.replace("@", "").strip()
    
    # Если это числовой ID
    if link.isdigit():
        return link
    
    # Если это username
    return link


async def get_user_id(link: str) -> int | None:
    """Возвращает идентификатор пользователя по ссылке или username"""

    try:
        from telegram import Bot
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        
        # Если это числовой ID
        if link.strip().isdigit():
            user_id = int(link.strip())
            # Синхронизируем username для этого пользователя
            try:
                await sync_user_data(user_id)
            except:
                pass
            return user_id
        
        # Если это username (с @ или без)
        username = link.replace("@", "").strip()
        if username:
            try:
                # Пытаемся получить пользователя из Telegram API
            user = await bot.get_chat(f"@{username}")
                user_id = user.id
                
                # Синхронизируем данные пользователя с БД
                try:
                    await sync_user_data(user_id)
                except Exception as sync_error:
                    print(f"[DEBUG] Failed to sync user data for {user_id}: {sync_error}", flush=True)
                
                return user_id
            except Exception as e:
                print(f"[DEBUG] Failed to get user by username @{username} from Telegram API: {e}", flush=True)
                # Пробуем найти в БД по username
                from databases.postgresql import get_postgresql_connection
                conn, cur = get_postgresql_connection()
                try:
                    # Сначала ищем по telegram_username (самый точный способ)
                    cur.execute("""
                        SELECT user_id FROM users 
                        WHERE LOWER(telegram_username) = LOWER(%s)
                        LIMIT 1
                    """, (username,))
                    result = cur.fetchone()
                    if result:
                        user_id = result["user_id"]
                        print(f"[DEBUG] Found user by telegram_username: {user_id}", flush=True)
                        # Пытаемся синхронизировать данные
                        try:
                            await sync_user_data(user_id)
                        except:
                            pass
                        return user_id
                    
                    # Если не нашли, ищем по full_name (точное совпадение)
                    cur.execute("""
                        SELECT user_id FROM users 
                        WHERE LOWER(full_name) = LOWER(%s)
                        LIMIT 1
                    """, (username,))
                    result = cur.fetchone()
                    if result:
                        user_id = result["user_id"]
                        print(f"[DEBUG] Found user by full_name (exact): {user_id}", flush=True)
                        # Пытаемся синхронизировать данные
                        try:
                            await sync_user_data(user_id)
                        except:
                            pass
                        return user_id
                    
                    # Если не нашли, пробуем частичное совпадение по full_name
                    cur.execute("""
                        SELECT user_id FROM users 
                        WHERE LOWER(full_name) LIKE LOWER(%s)
                        LIMIT 1
                    """, (f"%{username}%",))
                    result = cur.fetchone()
                    if result:
                        user_id = result["user_id"]
                        print(f"[DEBUG] Found user by full_name (partial): {user_id}", flush=True)
                        try:
                            await sync_user_data(user_id)
                        except:
                            pass
                        return user_id
                    
                    print(f"[DEBUG] User not found in database: {username}", flush=True)
                finally:
                    cur.close()
                    conn.close()
        
        return None
    except Exception as e:
        print(f"[DEBUG] Error in get_user_id for '{link}': {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None


async def sync_user_data(user_id: int) -> bool:
    """Синхронизирует данные пользователя с Telegram API"""
    
    try:
        from telegram import Bot
        from databases.postgresql import get_postgresql_connection
        
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        
        # Получаем актуальные данные из Telegram
        user = await bot.get_chat(user_id)
        
        # Обновляем в БД
        conn, cur = get_postgresql_connection()
        try:
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            if not full_name:
                full_name = user.username or f"User {user_id}"
            
            telegram_username = user.username or None
            
            cur.execute("""
                UPDATE users
                SET full_name = %s,
                    telegram_username = %s
                WHERE user_id = %s
            """, (full_name, telegram_username, user_id))
            conn.commit()
            
            print(f"[SYNC] Updated user {user_id} data: full_name={full_name}", flush=True)
            return True
        finally:
            cur.close()
            conn.close()
    except Exception as e:
        print(f"[SYNC ERROR] Failed to sync user {user_id}: {e}", flush=True)
        return False


async def get_user_friends(user_id: int) -> list[int]:
    """Возвращает список друзей (в Telegram это не поддерживается напрямую)"""
    # В Telegram нет прямого API для получения друзей
    # Возвращаем пустой список
    return []


async def get_friends_amount(user_id: int) -> int:
    """Возвращает количество друзей (в Telegram не поддерживается)"""
    return 0


async def get_followers_amount(user_id: int) -> int:
    """Возвращает количество подписчиков (в Telegram не поддерживается напрямую)"""
    return 0


async def get_registration_date(user_id: int):
    """Возвращает дату регистрации (в Telegram не поддерживается напрямую)"""
    from datetime import datetime
    return datetime.today()


async def kick_user_from_chat(
        user_id: int,
        chat_id: int
) -> bool:
    """Исключает пользователя из чата"""

    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        await bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
        await bot.unban_chat_member(chat_id=chat_id, user_id=user_id)
        return True
    except:
        return False


async def is_user_subscribed_to_channel(user_id: int, channel_id: int) -> bool:
    """Проверяет, подписан ли пользователь на канал"""
    
    try:
        bot = Bot(token=TelegramBotSettings.BOT_TOKEN)
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        # member.status может быть: 'member', 'administrator', 'creator', 'left', 'kicked', 'restricted'
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

