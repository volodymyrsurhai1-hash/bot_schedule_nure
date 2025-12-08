import asyncio
import logging
import config
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
import datetime
import parser
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest

# Твой токен
TOKEN = config.TOKEN

logging.basicConfig(level=logging.INFO)


bot = Bot(token=TOKEN)
dp = Dispatcher()

schedule = parser.load_and_parse_schedule()

# функція таймеру видалення для повідомлень
async def delete_later(message, time):
    await asyncio.sleep(time)
    with suppress(TelegramBadRequest):
        await message.delete()

# /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.chat.type == 'private':
        await message.answer("Привет! Я бот с расписанием. Добавь меня в группу своей группы!")
    else:
        await message.answer("Привет всем! Я теперь в чате. Пишите /today, чтобы узнать пары.")

# /today -- Пари на сьогодні
@dp.message(Command("today"), F.chat.type.in_({'group', 'supergroup'}))
async def cmd_today_group(message: types.Message):
    data = datetime.datetime.now()
    lessons = parser.get_lessons_by_date(schedule, data.strftime("%d.%m.%Y"))
    response_text = f"📅 <b>Расписание на сегодня:</b>\n\n{lessons}"
    message_bot = await message.reply(response_text, parse_mode=ParseMode.HTML)
    asyncio.create_task(delete_later(message_bot, 120))
    asyncio.create_task(delete_later(message, 120))

async def main():
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())