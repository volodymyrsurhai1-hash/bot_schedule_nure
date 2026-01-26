import asyncio
import aiofiles

from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.default import DefaultBotProperties
from contextlib import suppress

from apscheduler.schedulers.asyncio import AsyncIOScheduler

import datetime
import pytz
import logging
import json
import os

import config
import parse_csv

logging.basicConfig(level=logging.INFO)

CHATS_FILE = "jsons\\chats.json"
GROUPS_FILE = "jsons\\groups.json"

scheduler = AsyncIOScheduler()
TZ_UKRAINE = pytz.timezone('Europe/Kiev')

api = parse_csv.ScheduleAPI()

form_router = Router()
TOKEN = config.TOKEN
bot = Bot(token=TOKEN)
dp = Dispatcher()


class Form(StatesGroup):
    faculty = State()
    speciality = State()
    group = State()

@form_router.message(CommandStart())
async def command_start(message: types.Message, state: FSMContext):
    """Початок отримання інформації про групу, через стани"""
    await state.set_state(Form.faculty)

    keyboard = get_keyboard(api.list_of_facs, 5)

    if message.chat.type == 'private':
        message_bot = await message.answer("Привіт! Я бот с розкладом. Додай мене в группу!", parse_mode=ParseMode.HTML)
    else:
        message_bot = await message.answer("Привіт усім! Я тепер у чаті. Треба пройти короткий квіз знизу!.", reply_markup=keyboard)

    await delete_later(message_bot, 400)

@form_router.callback_query(Form.faculty)
async def get_specialty(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data
    facs = api.get_specialty(data)
    await state.update_data(faculty=facs)
    await state.set_state(Form.speciality)


    # Додаємо дані для клавіатури, для цього створюємо додатковий обєкт
    names = api.get_specialty(data)
    list_of_specs = []
    for i in names:
        for j in i:
            list_of_specs.append(j.get("full_name"))


    keyboard = get_keyboard(list_of_specs, 3)

    await callback.message.edit_text(
        text=f"Ти обрав факультет: <b>{data}</b>.\nТепер обери спеціальність:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

@form_router.callback_query(Form.speciality)
async def get_group(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data

    content = await state.get_data()
    groups = api.get_faculties(content.get("faculty"), data)

    await state.update_data(speciality=groups)
    await state.set_state(Form.group)

    names = list(groups)
    list_of_groups = []
    for i in names:
        list_of_groups.append(i.get("name"))

    keyboard = get_keyboard(list_of_groups, 3)
    await callback.message.edit_text(
        text=f"Ти обрав Групу: <b>{data}</b>.\nТепер обери спеціальність:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

@form_router.callback_query(Form.group)
async def get_group_id(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data

    content = await state.get_data()
    group_id = api.get_groups(content.get("speciality"), data)

    # Зберігаємо id від API у формі {CHAT_ID : API_ID}
    await save_id(callback.message.chat.id, group_id)

    # Основні кнопки
    builder = ReplyKeyboardBuilder()
    builder.button(text='📅 На сьогодні')
    builder.button(text='🗓 На тиждень')
    keyboard = builder.as_markup(resize_keyboard=True,
                             input_field_placeholder="Обери команду")

    message_frombot = await callback.message.edit_text(
        text=f"<b>Готово!</b>\n\n Тепер ви можете користуватися усіма функціями бота, наприклад: /today, /week",
        parse_mode=ParseMode.HTML
    )
    message_keyboard = await callback.message.reply('Або ж скористуватись кнопками', reply_markup=keyboard)


    await delete_later(message_frombot, 160)
    await delete_later(message_keyboard, 160)


"""Обробка основних команд бота"""
@dp.message(F.text == "📅 На сьогодні")
@dp.message(Command("today"), F.chat.type.in_({'group', 'supergroup'}))
async def cmd_today_group(message: types.Message):
    id = await get_chat_group_id(message.chat.id)
    print(id)
    print(message.chat.id)
    api.get_csv_schedule_by_day(id)
    lessons = api.get_by_date(datetime.datetime.now(), id)



    response_text = f"📅 <b>Розклад на сьогодні:</b>\n\n{lessons}"

    if lessons == []:
        response_text = "Пар нема!"

    message_bot = await message.reply(response_text, parse_mode=ParseMode.HTML)

    asyncio.create_task(delete_later(message_bot, 100))
    asyncio.create_task(delete_later(message, 100))

"""Допоміжні функції"""
async def send_morning_schedule():
    current_chats = await get_all_chats()
    for id in current_chats:
        api.get_csv_schedule_by_day(await get_chat_group_id(id))
        lessons = api.get_by_date(datetime.datetime.now(), await get_chat_group_id(id))
        if lessons is None:
            break
        message_bot = await bot.send_message(chat_id=id,
            text=f"☀️  <b> Доброго ранку! Розклад на сьогодні:</b>\n\n{lessons}",
            parse_mode="HTML")
        asyncio.create_task(delete_later(message_bot, 100))


async def delete_later(message, time):
    await asyncio.sleep(time)
    with suppress(TelegramBadRequest):
        await message.delete()

def get_keyboard(list, adj):
    builder = InlineKeyboardBuilder()

    for i in list:
        builder.button(text=i, callback_data=i)
    builder.adjust(adj)
    return builder.as_markup()

async def save_id(chat_id, group_id):
    # Створюємо папку, якщо її немає
    os.makedirs(os.path.dirname(CHATS_FILE), exist_ok=True)

    chats = {}
    # Читаємо існуючий файл
    if os.path.exists(CHATS_FILE):
        try:
            async with aiofiles.open(CHATS_FILE, "r", encoding="utf-8") as f:
                chats = json.loads(await f.read())
        except Exception:
            pass # Якщо файл битий, почнемо з чистого аркуша

    # Оновлюємо або додаємо запис
    chats[str(chat_id)] = group_id

    # Асинхронно записуємо назад
    async with aiofiles.open(CHATS_FILE, "w", encoding="utf-8") as f:
        await f.write(json.dumps(chats, indent=4, ensure_ascii=False))


async def get_chat_group_id(chat_id):
    if not os.path.exists(CHATS_FILE):
        return None

    try:
        async with aiofiles.open(CHATS_FILE, "r", encoding="utf-8") as f:
            content = await f.read()
            chats = json.loads(content)

        return chats.get(str(chat_id))

    except (FileNotFoundError, json.JSONDecodeError):
        return None

async def get_all_chats():
    """
    Возвращает словарь всех подписок: {"chat_id": group_id}
    """
    if not os.path.exists(CHATS_FILE):
        return {}

    try:
        async with aiofiles.open(CHATS_FILE, "r", encoding="utf-8") as f:
            content = await f.read()
            chats = json.loads(content)
            return chats
    except Exception:
        return {}

async def main():
    print("Бот запущений...")
    scheduler.add_job(
        send_morning_schedule,
        trigger='cron',
        hour=21,
        minute=38,
        timezone = TZ_UKRAINE
    )

    scheduler.start()
    dp.include_router(form_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())