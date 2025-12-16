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
from apscheduler.schedulers.asyncio import AsyncIOScheduler


logging.basicConfig(level=logging.INFO)

scheduler = AsyncIOScheduler()
schedule = parser.load_and_parse_schedule()

TOKEN = config.TOKEN
bot = Bot(token=TOKEN)
dp = Dispatcher()

chat_ids= []

async def delete_later(message, time):
    await asyncio.sleep(time)
    with suppress(TelegramBadRequest):
        await message.delete()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    chat_ids.append(message.chat.id)
    if message.chat.type == 'private':
        await message.answer("Привіт! Я бот с розкладом. Додай мене в группу!")
    else:
        await message.answer("Привіт усім! Я тепер у чаті. Пиши /today, щоб дізнатися які сьогодні пари.")


@dp.message(Command("today"), F.chat.type.in_({'group', 'supergroup'}))
async def cmd_today_group(message: types.Message):
    data = datetime.datetime.now()
    lessons = parser.get_lessons_by_date(schedule, data.strftime("%d.%m.%Y"))
    response_text = f"📅 <b>Розклад на сьогодні:</b>\n\n{lessons}"
    message_bot = await message.reply(response_text, parse_mode=ParseMode.HTML)
    asyncio.create_task(delete_later(message_bot, 120))
    asyncio.create_task(delete_later(message, 120))


async def send_morning_schedule():
    now = datetime.datetime.now()
    date_str = now.strftime("%d.%m.%Y")

    lessons = parser.get_lessons_by_date(schedule, date_str)

    if "Розкладу нема" in lessons or 'Пар нема' in lessons:
        return
    for id in chat_ids:
        await bot.send_message(chat_id=id,
            text=f"☀️ Доброго ранку! <b>Розклад на сьогодні:</b>\n\n{lessons}",
            parse_mode="HTML")

async def main():
    print("Бот запущений...")
    scheduler.add_job(
        send_morning_schedule,
        trigger='cron',
        hour=9,
        minute=0,
        day_of_week='mon-fri'
    )

    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())