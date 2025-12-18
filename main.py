import asyncio
import logging

import config
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.enums import ParseMode
import datetime
import parser
import json
import os
import aiofiles
from contextlib import suppress
from aiogram.exceptions import TelegramBadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz


logging.basicConfig(level=logging.INFO)

CHATS_FILE = "chats.json"

scheduler = AsyncIOScheduler()
schedule = parser.load_and_parse_schedule()
TZ_UKRAINE = pytz.timezone('Europe/Kiev')


TOKEN = config.TOKEN
bot = Bot(token=TOKEN)
dp = Dispatcher()


async def load_chats():
    if not os.path.exists(CHATS_FILE):
        return []
    try:
        with open(CHATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return []


async def save_chat(chat_id):
    current_chats = await load_chats()  # Ждем чтения

    if chat_id not in current_chats:
        current_chats.append(chat_id)
        async with aiofiles.open(CHATS_FILE, mode='w', encoding='utf-8') as f:
            await f.write(json.dumps(current_chats, ensure_ascii=False))
        logging.info(f"Добавлен новый чат: {chat_id}")

async def delete_later(message, time):
    await asyncio.sleep(time)
    with suppress(TelegramBadRequest):
        await message.delete()



def get_commands_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text='📅 На сьогодні')
    builder.button(text='🗓 На тиждень')
    return builder.as_markup(resize_keyboard=True,
        input_field_placeholder="Обери команду")

def get_week_dates():
    now = datetime.datetime.now(TZ_UKRAINE)
    # now.weekday(): 0 = Понедельник, 6 = Воскресенье
    # Отнимаем от текущей даты номер дня недели, чтобы получить Понедельник
    start_of_week = now - datetime.timedelta(days=now.weekday())

    week_dates = []
    for i in range(5):  # 5 дней (Пн-Пт)
        day = start_of_week + datetime.timedelta(days=i)
        week_dates.append(day.strftime("%d.%m.%Y"))

    return week_dates


def get_week_keyboard(current_day_index):
    builder = InlineKeyboardBuilder()
    days_short = ["Пн", "Вт", "Ср", "Чт", "Пт"]

    for i, day_name in enumerate(days_short):
        if i == current_day_index:
            text = f"• {day_name} •"
        else:
            text = day_name

        builder.button(text=text, callback_data=f"week_{i}")

    builder.adjust(5)
    return builder.as_markup()

@dp.message(F.text == '🗓 На тиждень')
@dp.message(Command("week"))
async def cmd_week(message: types.Message):
    week_dates = get_week_dates()

    current_weekday = datetime.datetime.now(TZ_UKRAINE).weekday()

    day_index = 0 if current_weekday > 4 else current_weekday

    date_str = week_dates[day_index]
    lessons = parser.get_lessons_by_date(schedule, date_str)

    text = f"📅 <b>Розклад на тиждень</b>\nДата: {date_str} (День {day_index + 1})\n\n{lessons}"

    await message.answer(
        text,
        reply_markup=get_week_keyboard(day_index),
        parse_mode="HTML"
    )


@dp.callback_query(F.data.startswith("week_"))
async def on_week_click(callback: types.CallbackQuery):
    # Парсим индекс из строки "week_1" -> int(1)
    day_index = int(callback.data.split("_")[1])

    week_dates = get_week_dates()
    date_str = week_dates[day_index]

    lessons = parser.get_lessons_by_date(schedule, date_str)

    new_text = f"📅 <b>Розклад на тиждень</b>\nДата: {date_str}\n\n{lessons}"

    # Пытаемся отредактировать сообщение
    # suppress нужен, если пользователь нажмет на тот же день (Telegram выдаст ошибку, что текст не изменился)
    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            new_text,
            reply_markup=get_week_keyboard(day_index),  # Обновляем кнопки (перемещаем точку)
            parse_mode="HTML"
        )

    # Обязательно отвечаем серверу, чтобы кнопка перестала мигать
    await callback.answer()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    keyboard = get_commands_keyboard()
    await save_chat(message.chat.id)
    if message.chat.type == 'private':
        await message.answer("Привіт! Я бот с розкладом. Додай мене в группу!")
    else:
        await message.answer("Привіт усім! Я тепер у чаті. Пиши /today, щоб дізнатися які сьогодні пари.", reply_markup=keyboard)

@dp.message(F.text == "📅 На сьогодні")
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

    current_chats = await load_chats()

    for id in current_chats:
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
        day_of_week='mon-fri',
        timezone = TZ_UKRAINE
    )

    scheduler.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())