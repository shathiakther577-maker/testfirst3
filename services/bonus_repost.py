import os
import asyncio
import traceback
from pathlib import Path
from psycopg2.extras import DictCursor

from settings import VkBotSettings, NotifyChats, Config
from databases.postgresql import get_postgresql_connection

from schemas.bonus_repost import BonusPostSchema
from services.notification import NotificationsService

from modules.additional import format_number
from modules.vkontakte.bot import publish_post, upload_document


class BonusRepostService:

    @staticmethod
    def get_bonus_post(
            post_id: int,
            psql_cursor: DictCursor
    ) -> BonusPostSchema | None:
        """Возвращает данные о бонусном посте"""

        psql_cursor.execute("SELECT * FROM bonus_posts WHERE post_id = %s", [post_id])
        psql_response = psql_cursor.fetchone()

        return BonusPostSchema(**psql_response) if psql_response else None


    @staticmethod
    def get_bonus_posts(
            psql_cursor: DictCursor
    ) -> list[BonusPostSchema | None]:
        """Возвращает бонусные посты"""

        psql_cursor.execute("SELECT * FROM bonus_posts")
        bonus_posts = [BonusPostSchema(**x) for x in psql_cursor.fetchall()]

        return bonus_posts


    @staticmethod
    def decrement_activation(
            post_id: int,
            psql_cursor: DictCursor
    ) -> None:
        """Уменьшает количество активаций"""

        psql_cursor.execute("""
            UPDATE bonus_posts
            SET activations = activations - 1
            WHERE post_id = %s
        """, [post_id])


    @staticmethod
    def create_bonus_posts(
            post_id: int,
            reward: int,
            sub_reward: int,
            activations: int,
            life_seconds: int,
            psql_cursor: DictCursor
    ) -> BonusPostSchema:
        """Создает бонусный пост"""

        bonus_post = BonusPostSchema(
            post_id=post_id, reward=reward, sub_reward=sub_reward,
            activations=activations
        )

        psql_cursor.execute("""
            INSERT INTO bonus_posts (
                post_id, reward, sub_reward, activations, life_datetime
            )
            VALUES (
                %(post_id)s, %(reward)s, %(sub_reward)s, %(activations)s,
                NOW() + INTERVAL '%(life_seconds)s SECONDS'
            )
            RETURNING *
        """, {
            **bonus_post.dict(),
            "life_seconds": life_seconds
        })
        psql_response = psql_cursor.fetchone()

        return BonusPostSchema(**psql_response)


    @staticmethod
    def get_repost_logs(
            post_id: int,
            psql_cursor: DictCursor
    ) -> list[int | None]:
        """Возвращает данные пользователя которые сделали репост поста"""

        psql_cursor.execute("""
            SELECT user_id, reward
            FROM bonus_repost_logs
            WHERE post_id = %s
        """, [post_id])
        psql_response = psql_cursor.fetchall()

        return psql_response


    @staticmethod
    def insert_bonus_repost_logs(
            user_id: int,
            post_id: int,
            reward: int,
            psql_cursor: DictCursor
    ) -> None:
        """Добавляет пользователя в bonus_repost_logs"""

        psql_cursor.execute("""
            INSERT INTO bonus_repost_logs (user_id, post_id, reward)
            VALUES (%(user_id)s, %(post_id)s, %(reward)s)
        """, {"user_id": user_id, "post_id": post_id, "reward": reward})


    @staticmethod
    def delete_post(
            post_id: int,
            psql_cursor: DictCursor
    ) -> None:
        """Удаляет бонусный пост"""

        psql_cursor.execute("DELETE FROM bonus_posts WHERE post_id = %s", [post_id])
        psql_cursor.execute("DELETE FROM bonus_repost_logs WHERE post_id = %s", [post_id])


    @staticmethod
    def user_active_post(
            user_id: int,
            post_id: int,
            psql_cursor: DictCursor
    ) -> bool:
        """Возвращает активировал ли пользователь бонус за пост"""

        psql_cursor.execute("""
            SELECT active_at FROM bonus_repost_logs
            WHERE user_id = %(user_id)s AND
                  post_id = %(post_id)s
        """, {
            "user_id": user_id,
            "post_id": post_id
        })

        return bool(psql_cursor.fetchone())


    @classmethod
    def format_bonus_post_message(
            cls,
            bonus_post: BonusPostSchema
    ) -> str:
        """Формируют сообщение о бонусе за репост"""

        return f"""
            💬 vk.com/wall-{VkBotSettings.GROUP_ID}_{bonus_post.post_id}
            💰 Бонус: {format_number(bonus_post.reward)}
            💰 Дополнительный бонус: {format_number(bonus_post.sub_reward)}
            📊 Осталось: {format_number(bonus_post.activations)}
            🕒 Активно до: {bonus_post.life_datetime}
        """


    @classmethod
    def get_active_bonus_response_message(
            cls,
            psql_cursor: DictCursor
    ) -> str:
        """Возвращает сообщение об активных бонусных постах"""

        psql_cursor.execute("""
            SELECT * FROM bonus_posts
            WHERE life_datetime > NOW() AND
                  activations > 0
        """)
        bonus_posts = [BonusPostSchema(**x) for x in psql_cursor.fetchall()]

        response = ["👑 Активные бонусы за репост"]
        for post in bonus_posts:
            response.append(cls.format_bonus_post_message(post))

        return "\n".join(response)


    @classmethod
    def _create_document(
            cls,
            post_id: int,
            psql_cursor: DictCursor
    ) -> str:
        """Создает документ кто получил бонус за репост и возвращает путь до файла"""

        repost_log = cls.get_repost_logs(post_id, psql_cursor)
        file_path = str(Path(Config.TEMP_FOLDER, f"final_wall_{post_id}.txt"))

        with open(file_path, "w") as file:
            file_text = "\n".join([
                f"Id{repost['user_id']} — {format_number(repost['reward'])} WC"
                for repost in repost_log
            ])
            file.write(file_text if bool(file_text) else "Нет участников")

        return file_path


    @classmethod
    async def publish_post_end_bonus(cls) -> None:
        """Публикует пост об окончании бонуса"""

        while True:
            psql_connect, psql_cursor = get_postgresql_connection()

            try:
                psql_cursor.execute("""
                    SELECT post_id FROM bonus_posts
                    WHERE NOW() >= life_datetime and on_wall = FALSE
                """)
                post_ids = [x["post_id"] for x in psql_cursor.fetchall()]

                for post_id in post_ids:
                    try:
                        post_link = f"https://vk.com/wall-{VkBotSettings.GROUP_ID}_{post_id}"

                        document_path = cls._create_document(post_id, psql_cursor)
                        doc_attachment = await upload_document(document_path, "Победители")
                        os.remove(document_path)

                        await publish_post(
                            message=f"""
                                ⌛Время проведения акции - {post_link} подошло к концу
                                ✅ Все участники получили призы
                            """,
                            attachment=doc_attachment
                        )
                        psql_cursor.execute("""
                            UPDATE bonus_posts
                            SET on_wall = TRUE
                            WHERE post_id = %s
                        """, [post_id])
                        cls.delete_post(post_id, psql_cursor)

                    except:
                        await NotificationsService.send_notification(
                            chat=NotifyChats.MAIN,
                            message=f"""
                                Пост {post_link} не получилось опубликовать
                                Через несколько минут попробую еще раз
                                Ошибка: {traceback.format_exc()}
                            """
                        )
                        await asyncio.sleep(10)

                await asyncio.sleep(60)

            except:
                await asyncio.sleep(30)

            finally:
                psql_cursor.close()
                psql_connect.close()
