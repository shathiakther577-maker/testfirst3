import asyncio
import threading
from redis.client import Redis
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from psycopg2.extras import DictCursor

from settings import PointsLimit, NotifyChats
from databases.redis import get_redis_cursor
from databases.postgresql import get_postgresql_connection

from schemas.users import UserSchema, UserStatus
from schemas.redis import RedisKeys
from schemas.transfer_coins import TransferCoinsSchema, TransferCoinsType, \
    AccessTransferCoins, TransferCoinsError, get_transfer_coins_error_message

from services.security import SecurityService
from services.callback_api import CallbackService
from services.notification import NotificationsService
from services.reset_user_data import ResetUserServices

from modules.additional import strtobool, format_number, convert_number
from modules.databases.users import get_user_data, give_coins, take_coins
from modules.telegram.bot import send_message
from modules.telegram.users import get_user_id

from vk_bot.template_messages import DATA_OUTDATED, SOMETHING_WENT_WRONG


class TransferWhiteListService:
    """Белый список отправителей переводов"""

    @classmethod
    def insert_user(
            cls,
            user_id: int,
            psql_cursor: DictCursor
    ) -> None:
        """Добавляет пользователя в белый список"""

        psql_cursor.execute("""
            INSERT INTO transfer_white_list (user_id)
            VALUES (%s)
        """, [user_id])


    @classmethod
    def delete_user(
            cls,
            user_id: int,
            psql_cursor: DictCursor
    ) -> None:
        """Удаляет пользователя из белого списка"""

        psql_cursor.execute("""
            DELETE FROM transfer_white_list
            WHERE user_id = %s
        """, [user_id])


    @classmethod
    def search(
            cls,
            user_id: int,
            psql_cursor: DictCursor
    ) -> bool:
        """Проверяет есть ли пользователь в белом списке"""

        psql_cursor.execute("""
            SELECT * FROM transfer_white_list
            WHERE user_id = %s
        """, [user_id])

        return bool(psql_cursor.fetchone())


class TransferCoinsService:
    """Сервис переводов"""

    @classmethod
    def check_possibility(
            cls,
            sender_id: int,
            recipient_id: int,
            amount: int,
            psql_cursor: DictCursor
    ) -> AccessTransferCoins:
        """Проверяет возможность перевода коинов"""

        try:

            if sender_id == recipient_id:
                return AccessTransferCoins(error=TransferCoinsError.CANT_SEND_COINS_TO_ONESELF)

            if not isinstance(amount, int) or 0 >= amount:
                return AccessTransferCoins(error=TransferCoinsError.INCORRECT_AMOUNT)

            sender_data = get_user_data(sender_id, psql_cursor)

            if sender_data is None:
                return AccessTransferCoins(error=TransferCoinsError.YOU_UNREGISTERED)

            if sender_data.banned is True:
                return AccessTransferCoins(error=TransferCoinsError.YOU_BANNED)

            # Переводы доступны всем без ограничений по рейтингу
            # if sender_data.all_win < PointsLimit.TRANSFER_COINS and sender_data.status != UserStatus.ADMIN:
            #     return AccessTransferCoins(error=TransferCoinsError.NOT_ENOUGH_POINTS)

            if sender_data.banned_transfer is True:
                return AccessTransferCoins(error=TransferCoinsError.TRANSFERS_BANNED)

            if sender_data.coins < amount or sender_data.coins <= 0:
                return AccessTransferCoins(error=TransferCoinsError.NOT_ENOUGH_COINS)

            recipient_data = get_user_data(recipient_id, psql_cursor)

            if recipient_data is None:
                return AccessTransferCoins(error=TransferCoinsError.UNREGISTERED_RECIPIENT)

            if recipient_data.banned is True:
                return AccessTransferCoins(error=TransferCoinsError.RECIPIENT_BANNED)

            return AccessTransferCoins(access=True, error=TransferCoinsError.NO)

        except:
            return AccessTransferCoins()


    @staticmethod
    def update_banned_transfer(
            user_id: int,
            value: bool,
            psql_cursor: DictCursor
    ) -> None:
        """Выдает или снимает запрет на перевод"""

        psql_cursor.execute("""
            UPDATE users
            SET banned_transfer = %(value)s
            WHERE user_id = %(user_id)s
        """, {
            "user_id": user_id,
            "value": value
        })


    @classmethod
    def _create_transaction(
            cls,
            sender_id: int,
            recipient_id: int,
            amount: int,
            psql_cursor: DictCursor
    ) -> TransferCoinsSchema:
        """Добавляет и возвращает данные о переводе"""

        psql_cursor.execute("""
            INSERT INTO transfer_coins (sender_id, recipient_id, amount)
            VALUES (%(sender_id)s, %(recipient_id)s, %(amount)s)
            RETURNING *
        """, {
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "amount": amount
        })
        transaction_data = TransferCoinsSchema(**psql_cursor.fetchone())

        return transaction_data


    @classmethod
    async def _send_notifi_recipient(
            cls,
            *,
            sender_name: str,
            recipient_id: int,
            format_amount: int
    ) -> None:
        """Отправляет уведомление получателю о переводе"""

        try:
            await send_message(
                recipient_id, f"✅ Получено {format_amount} WC от {sender_name}"
            )
        except Exception as e:
            # Если пользователь заблокировал бота или не найден - это нормально
            print(f"[TRANSFER] Не удалось отправить уведомление пользователю {recipient_id}: {e}", flush=True)


    @classmethod
    async def _send_notifi_admins(
            cls,
            sender_name: str,
            recipient_name: str,
            format_amount: str,
            transfer_amount: int
    ) -> None:
        """Отправляет уведомление администратором"""

        message = f"🔄 {sender_name} перевел {recipient_name} {format_amount} WC"
        await NotificationsService.send_notification(
            chat=NotifyChats.TRANSFER_COINS,
            message=message
        )


    @classmethod
    async def _send_callback(
            cls,
            recipient_id: int,
            transaction_data: TransferCoinsSchema,
            psql_cursor: DictCursor,
            redis_cursor: Redis
    ) -> None:
        """Отправляет callback на сервер получателя"""

        callback_data = CallbackService.get_user_callback(recipient_id, psql_cursor)

        if (
            callback_data is not None and
            callback_data.callback_url is not None and
            callback_data.callback_secret is not None and
            strtobool(redis_cursor.get(RedisKeys.API_WORK.value) or "1")
        ):
            request = dict(transaction_data)
            request["created_at"] = str(request["created_at"])

            request["sign"] = SecurityService.signing_data(
                data=request,
                secret_key=callback_data.callback_secret
            )

            await CallbackService.send_callback_message(
                callback_url=callback_data.callback_url,
                message=request
            )


    @classmethod
    async def _transfer_security(
            cls,
            sender_data: UserSchema,
            transaction_data: TransferCoinsSchema,
            psql_cursor: DictCursor
    ) -> None:
        """Дополнительная логика для безопасности переводов """

        sender_id = transaction_data.sender_id

        psql_cursor.execute("""
            SELECT COALESCE(COUNT(*), 0) as sender_send_count
            FROM transfer_coins
            WHERE sender_id = %(sender_id)s AND
                  created_at >= NOW() - INTERVAL '10 MINUTES'
        """, {
            "sender_id": sender_id
        })
        sender_send_count = psql_cursor.fetchone()["sender_send_count"]

        if (
            sender_send_count >= 50 and
            not TransferWhiteListService.search(sender_id, psql_cursor)
        ):
            cls.update_banned_transfer(sender_id, True, psql_cursor)

            await NotificationsService.send_notification(
                chat=NotifyChats.TRANSFER_COINS,
                message=f"{sender_data.vk_name} больше не может переводить (много переводов)"
            )
            await send_message(sender_id, "❌ Вы больше не можете переводить по причине подозрительных переводов")


    @classmethod
    async def _additional_logics(
            cls,
            transaction_data: TransferCoinsSchema
    ) -> None:
        """Выполняет дополнительную логику после перевода"""

        try:
            redis_cursor = get_redis_cursor()
            psql_connection, psql_cursor = get_postgresql_connection()

            amount = transaction_data.amount
            format_amount = format_number(amount)

            sender_id = transaction_data.sender_id
            sender_data = get_user_data(sender_id, psql_cursor)
            sender_name = sender_data.vk_name

            recipient_id = transaction_data.recipient_id
            recipient_data = get_user_data(recipient_id, psql_cursor)
            recipient_name = recipient_data.vk_name

            await cls._send_notifi_recipient(
                sender_name=sender_name,
                recipient_id=recipient_id,
                format_amount=format_amount
            )
            await cls._send_notifi_admins(
                sender_name=sender_name,
                recipient_name=recipient_name,
                format_amount=format_amount,
                transfer_amount=amount
            )
            await cls._send_callback(
                recipient_id=recipient_id,
                transaction_data=transaction_data,
                psql_cursor=psql_cursor,
                redis_cursor=redis_cursor
            )
            await cls._transfer_security(
                sender_data=sender_data,
                transaction_data=transaction_data,
                psql_cursor=psql_cursor
            )

        finally:
            psql_cursor.close()
            psql_connection.close()
            redis_cursor.close()


    @classmethod
    def send_coins(
            cls,
            *,
            sender_id: int,
            recipient_id: int,
            amount: int,
            psql_cursor: DictCursor
    ) -> TransferCoinsSchema:
        """Переводит коины другому пользователю"""
        
        # Проверка что amount положительный
        if amount <= 0:
            raise ValueError(f"Cannot transfer non-positive amount: {amount}")
        
        # Проверяем баланс отправителя перед переводом
        sender_data = get_user_data(sender_id, psql_cursor)
        if sender_data is None:
            raise ValueError(f"Sender {sender_id} not found")
        
        if sender_data.coins < amount:
            raise ValueError(f"Insufficient balance: {sender_data.coins} < {amount}")

        # Используем транзакцию для атомарности операции
        # take_coins и give_coins уже имеют проверки баланса
        try:
            take_coins(sender_id, amount, psql_cursor)
            give_coins(recipient_id, amount, psql_cursor)
            transaction_data = cls._create_transaction(
                sender_id, recipient_id, amount, psql_cursor
            )

            threading.Thread(
                target=asyncio.run,
                args=(cls._additional_logics(transaction_data),),
                daemon=True
            ).start()

            return transaction_data
        except Exception as e:
            # Если произошла ошибка, транзакция должна быть откачена на уровне выше
            print(f"[TRANSFER ERROR] Failed to transfer {amount} from {sender_id} to {recipient_id}: {e}", flush=True)
            raise


    @staticmethod
    def get_user_transfers(
            user_id: int,
            type: TransferCoinsType,
            offset: int,
            limit: int,
            psql_cursor: DictCursor,
            *,
            convert_type: bool = True  # Конвертирует в TransferCoinsSchema
    ) -> list[TransferCoinsSchema | dict | None]:
        """Возвращает переводы пользователя"""

        in_flag = type in [TransferCoinsType.IN, TransferCoinsType.ALL]
        out_flag = type in [TransferCoinsType.OUT, TransferCoinsType.ALL]

        psql_cursor.execute("""
            SELECT *, created_at::text as created_at
            FROM transfer_coins
            WHERE (
                %(in_flag)s AND recipient_id = %(user_id)s
                OR
                %(out_flag)s AND sender_id = %(user_id)s
            ) AND id > %(offset)s
            ORDER BY id DESC
            LIMIT %(limit)s
        """, {
            "user_id": user_id,
            "in_flag": in_flag,
            "out_flag": out_flag,
            "offset": offset,
            "limit": limit
        })
        transfers = psql_cursor.fetchall()

        if convert_type:
            transfers = [TransferCoinsSchema(**x) for x in transfers]

        return transfers


    @classmethod
    def get_message_warning(
            cls,
            recipient_data: UserSchema,
            keyboard: VkKeyboard
    ) -> str:
        """
            Возвращает дополнительный текст для сообщения и
                добавляет кнопку ссылкой на статью
            Предупреждение о мошенниках
        """

        status = recipient_data.status
        prefix = recipient_data.user_prefix

        if status in [UserStatus.USER]:
            extra_text = ""

        elif status in [UserStatus.ADMIN, UserStatus.HONEST, UserStatus.MARKET]:
            extra_text = f"Данный пользователь имеет обозначение {prefix}, что гарантирует честность"

        elif status in [UserStatus.SCAMMER]:
            extra_text = f"Пользователь имеет обозначение «{prefix}», — замечен в мошенничестве"

        else:
            extra_text = ""

        # VK ссылки удалены

        return extra_text


    @classmethod
    async def transfer_coins_in_message(
            cls,
            *,
            sender_data: UserSchema,
            split_message: list,
            fwd_messages: list | None,
            psql_cursor: DictCursor,
            redis_cursor: Redis
    ) -> tuple[str, str | None]:
        """Возвращает сообщение и клавиатуру (перевод внутри чата)"""

        sender_id = sender_data.user_id
        len_split_message = len(split_message)

        if len_split_message == 2 and len(fwd_messages) == 1:
            amount = convert_number(split_message[1])
            recipient_id = fwd_messages[0]["from_id"]

        elif len_split_message == 3:
            amount = convert_number(split_message[2])
            recipient_id = await get_user_id(split_message[1])

        else:
            return SOMETHING_WENT_WRONG, None

        transfer = cls.check_possibility(
            sender_id, recipient_id, amount, psql_cursor
        )

        if transfer.access is False:
            return get_transfer_coins_error_message(transfer.error), None

        keyboard = VkKeyboard(one_time=False, inline=True)
        keyboard.add_button(
            label="Да",
            color=VkKeyboardColor.POSITIVE,
            payload={
                "event": RedisKeys.TRANSFERS_IN_CHAT.value,
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "amount": amount,
                "confirm": True
            }
        )
        keyboard.add_button(
            label="Нет",
            color=VkKeyboardColor.NEGATIVE,
            payload={
                "event": RedisKeys.TRANSFERS_IN_CHAT.value,
                "sender_id": sender_id,
                "recipient_id": recipient_id,
                "amount": amount,
                "confirm": False
            }
        )
        keyboard.add_line()

        recipient_data = get_user_data(recipient_id, psql_cursor)
        extra_text = cls.get_message_warning(recipient_data, keyboard)
        extra_text = f"\n{extra_text}\n\n" if extra_text else ""

        response = f"""
            {sender_data.vk_name} вы уверены, что хотите перевести {format_number(amount)} WC {recipient_data.vk_name}
            {extra_text}⚠ Подтвердите перевод в течениe 1 минуты
        """

        redis_cursor.setex(
            name=f"{RedisKeys.TRANSFERS_IN_CHAT.value}:{sender_id}:{recipient_id}:{amount}",
            value=1,
            time=60
        )

        return response, keyboard.get_keyboard()


    @classmethod
    def handler_transfer_coins_in_message(
            cls,
            *,
            sender_id: int,
            payload: dict,
            psql_cursor: DictCursor,
            redis_cursor: Redis
    ) -> str:
        """Возвращает сообщение (подтверждает или отклоняет перевод в чате)"""

        recipient_id = payload.get("recipient_id")
        amount = payload.get("amount")

        redis_key = f"{RedisKeys.TRANSFERS_IN_CHAT.value}:{sender_id}:{recipient_id}:{amount}"
        if redis_cursor.get(redis_key) is None:
            return DATA_OUTDATED

        try:
            if payload.get("confirm") is True:

                transfer = cls.check_possibility(
                    sender_id, recipient_id, amount, psql_cursor
                )

                if transfer.access is True:
                    # Используем транзакцию для атомарности
                    from databases.postgresql import get_postgresql_connection
                    transfer_psql_connection, transfer_psql_cursor = get_postgresql_connection()
                    try:
                        transfer_psql_connection.autocommit = False
                        cls.send_coins(
                            sender_id=sender_id, recipient_id=recipient_id,
                            amount=amount, psql_cursor=transfer_psql_cursor
                        )
                        transfer_psql_connection.commit()
                        recipient_data = get_user_data(recipient_id, transfer_psql_cursor)
                        return f"✅ {recipient_data.vk_name} получил {format_number(amount)} WC"
                    except Exception as e:
                        transfer_psql_connection.rollback()
                        print(f"[TRANSFER ERROR] Transaction rolled back: {e}", flush=True)
                        return get_transfer_coins_error_message(TransferCoinsError.NOT_ENOUGH_COINS)
                    finally:
                        transfer_psql_connection.autocommit = True
                        transfer_psql_cursor.close()
                        transfer_psql_connection.close()
                else:
                    return get_transfer_coins_error_message(transfer.error)

            else:
                sender_data = get_user_data(sender_id, psql_cursor)
                return f"{sender_data.vk_name} перевод отменен"

        finally:
            redis_cursor.delete(redis_key)
