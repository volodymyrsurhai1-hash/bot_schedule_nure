import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.exceptions import TelegramBadRequest

# --- КОНФИГУРАЦИЯ ---
BOT_TOKEN = 'ТВОЙ_ТОКЕН_ЗДЕСЬ'
GROUP_ID = -100123456789  # ID группы, куда кидать ссылки
DELETE_DELAY = 15 * 60  # Время жизни сообщения в секундах (15 минут)

# Словарь расписания (в реальности заполняется парсером)
# Формат: "HH:MM": {"lesson": "Название", "url": "Ссылка"}
schedule_db = {
    "09:00": {"lesson": "Математический анализ", "url": "https://zoom.us/j/12345"},
    "10:45": {"lesson": "Программирование Python", "url": "https://meet.google.com/abc-def"},
}

# --- ИНИЦИАЛИЗАЦИЯ ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()


# --- ФУНКЦИЯ ПАРСИНГА (ЗАГЛУШКА) ---
async def update_schedule():
    """
    Сюда нужно вставить логику aiohttp + beautifulsoup.
    Функция должна обновлять глобальную переменную schedule_db.
    """
    logging.info("Парсинг данных с сайта университета...")
    # await parse_site_and_update_db()
    pass


# --- ЛОГИКА ОТПРАВКИ И УДАЛЕНИЯ ---
async def send_class_link(lesson_name: str, lesson_url: str):
    try:
        text = f"🔔 **Начинается пара:** {lesson_name}\n🔗 **Ссылка:** {lesson_url}\n\n⚠️ _Сообщение удалится через 15 минут!_"

        # Отправляем сообщение
        sent_message = await bot.send_message(chat_id=GROUP_ID, text=text, parse_mode="Markdown")
        logging.info(f"Отправлена ссылка на {lesson_name}")

        # Запускаем таймер на удаление (фоновая задача)
        asyncio.create_task(delete_message_later(sent_message.chat.id, sent_message.message_id))

    except Exception as e:
        logging.error(f"Ошибка при отправке: {e}")


async def delete_message_later(chat_id: int, message_id: int):
    """Ждет указанное время и удаляет сообщение"""
    await asyncio.sleep(DELETE_DELAY)
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        logging.info(f"Сообщение {message_id} удалено по таймеру.")
    except TelegramBadRequest:
        logging.warning("Сообщение уже удалено или не может быть удалено.")


# --- ЗАДАЧА ПРОВЕРКИ ВРЕМЕНИ ---
async def check_schedule():
    """Запускается каждую минуту и сверяет время"""
    now = datetime.now().strftime("%H:%M")

    if now in schedule_db:
        lesson = schedule_db[now]
        # Отправляем ссылку
        await send_class_link(lesson['lesson'], lesson['url'])


# --- ЗАПУСК ---
async def main():
    logging.basicConfig(level=logging.INFO)

    # 1. Добавляем задачи в планировщик
    # Проверять расписание каждую минуту
    scheduler.add_job(check_schedule, "cron", second=0)

    # Обновлять базу расписания раз в день (например, в 6 утра)
    scheduler.add_job(update_schedule, "cron", hour=6, minute=0)

    # 2. Запускаем планировщик
    scheduler.start()

    # 3. Запускаем бота (polling)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())