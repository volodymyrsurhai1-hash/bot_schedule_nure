import asyncio
import datetime
import logging
from contextlib import suppress

import pytz
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
from config import DELETE_MESSAGE_TIMEOUT
import parse_csv
from json_storage import ChatStorage

logging.basicConfig(level=logging.INFO)

scheduler = AsyncIOScheduler()
TZ_UKRAINE = pytz.timezone("Europe/Kiev")

api = parse_csv.ScheduleAPI()
storage = ChatStorage()

form_router = Router()
reminder_router = Router()

TOKEN = config.TOKEN
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Классы для состояний опроса
class Form(StatesGroup):
    faculty = State()
    speciality = State()
    group = State()

class Reminder(StatesGroup):
    text = State()
    date = State()


@form_router.message(CommandStart())
async def command_start(message: types.Message, state: FSMContext):
    """Початок отримання інформації про групу, через стани"""
    await state.set_state(Form.faculty)

    keyboard = get_keyboard(api.list_of_facs, 5)

    if message.chat.type == "private":
        message_bot = await message.answer(
            "Привіт! Я бот с розкладом. Додай мене в группу!",
            parse_mode=ParseMode.HTML,
        )
    else:
        message_bot = await message.answer(
            "Привіт усім! Я тепер у чаті. Треба пройти короткий квіз знизу!.",
            reply_markup=keyboard,
        )

    await delete_later(message_bot, DELETE_MESSAGE_TIMEOUT)
    await delete_later(message, DELETE_MESSAGE_TIMEOUT)

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
        parse_mode=ParseMode.HTML,
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
        parse_mode=ParseMode.HTML,
    )

@form_router.callback_query(Form.group)
async def get_group_id(callback: types.CallbackQuery, state: FSMContext):
    data = callback.data

    content = await state.get_data()
    group_id = api.get_groups(content.get("speciality"), data)

    # Зберігаємо id від API у формі {CHAT_ID : API_ID}
    await storage.save_chat_group(callback.message.chat.id, group_id)

    # Скачиваем расписание для этой группы
    api.get_csv_schedule_by_day(group_id)

    # Основні кнопки
    builder = ReplyKeyboardBuilder()
    builder.button(text="📅 На сьогодні")
    builder.button(text="🗓 На тиждень")
    builder.button(text='🔔 Нагадування')
    keyboard = builder.as_markup(
        resize_keyboard=True, input_field_placeholder="Обери команду"
    )

    message_frombot = await callback.message.edit_text(
        text="<b>Готово!</b>\n\n Тепер ви можете користуватися усіма функціями бота, наприклад: /today, /week, /reminder",
        parse_mode=ParseMode.HTML,
    )
    message_keyboard = await callback.message.reply(
        "Або ж скористуватись кнопками", reply_markup=keyboard
    )

    await delete_later(message_frombot, DELETE_MESSAGE_TIMEOUT)
    await delete_later(message_keyboard, DELETE_MESSAGE_TIMEOUT)


"""Обробка основних команд бота"""
@dp.message(F.text == "📅 На сьогодні")
@dp.message(Command("today"), F.chat.type.in_({"group", "supergroup"}))
async def cmd_today_group(message: types.Message):
    group_id = await storage.get_group_id(message.chat.id)
    date = datetime.datetime.now().strftime("%d.%m.%Y")
    lessons = api.get_by_date(date, group_id)

    if not lessons:
        response_text = "Пар нема!"
    else:
        lessons_text = "\n\n".join(lessons)
        response_text = f"📅 <b>Розклад на сьогодні:</b>\n\n{lessons_text}"

    message_bot = await message.reply(response_text, parse_mode=ParseMode.HTML)

    asyncio.create_task(delete_later(message_bot, DELETE_MESSAGE_TIMEOUT))
    asyncio.create_task(delete_later(message, DELETE_MESSAGE_TIMEOUT))

@reminder_router.message(F.text == '🔔 Нагадування')
@reminder_router.message(Command("reminder"))
async def cmd_reminder(message: types.Message, state: FSMContext):
    """Первое состоянее опроса для напоминания"""
    message_text = await message.reply("Напишіть текст нагадування!")
    await state.set_state(Reminder.text)
    asyncio.create_task(delete_later(message_text, DELETE_MESSAGE_TIMEOUT))
    asyncio.create_task(delete_later(message, DELETE_MESSAGE_TIMEOUT))


@reminder_router.message(Reminder.text)
async def get_reminder_text(message: types.Message, state: FSMContext):
    await state.update_data(reminder_text=message.text)
    calendar = SimpleCalendar()

    message_bot = await message.answer(
        "📅 <b>Оберіть дату:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=await calendar.start_calendar()
    )

    await state.set_state(Reminder.date)
    asyncio.create_task(delete_later(message_bot, DELETE_MESSAGE_TIMEOUT))
    asyncio.create_task(delete_later(message, DELETE_MESSAGE_TIMEOUT))


@reminder_router.callback_query(SimpleCalendarCallback.filter(), Reminder.date)
async def process_calendar_date(callback: types.CallbackQuery, callback_data: dict, state: FSMContext):
    calendar = SimpleCalendar()

    selected, date_obj = await calendar.process_selection(callback, callback_data)

    if selected:
        data = await state.get_data()
        text = data.get("reminder_text")

        default_time = datetime.time(hour=9, minute=0)

        run_date = datetime.datetime.combine(date_obj.date(), default_time)

        now = datetime.datetime.now()
        if run_date < now:
            if run_date.date() == now.date():
                run_date = now + datetime.timedelta(minutes=1)
                message_bot1 = await callback.message.answer("⚠️ Час 09:00 вже пройшов, нагадаю через хвилину!")
                asyncio.create_task(delete_later(message_bot1, DELETE_MESSAGE_TIMEOUT))
            else:
                message_bot2 = await callback.message.answer("⚠️ Ви обрали дату в минулому! Спробуйте заново /reminder")
                asyncio.create_task(delete_later(message_bot2, DELETE_MESSAGE_TIMEOUT))
                return

        scheduler.add_job(
            send_reminder_job,
            trigger="date",
            run_date=run_date,
            kwargs={"chat_id": callback.message.chat.id, "text": text},
            timezone=TZ_UKRAINE
        )

        message_bot = await callback.message.edit_text(
            f"✅ <b>Готово!</b>\n"
            f"Нагадаю: {run_date.strftime('%d.%m.%Y в %H:%M')}\n"
            f"Текст: {text}",
            parse_mode="HTML"
        )

        await state.clear()

        asyncio.create_task(delete_later(message_bot, DELETE_MESSAGE_TIMEOUT))



async def send_reminder_job(chat_id: int, text: str):
    try:
        message_bot = await bot.send_message(
            chat_id=chat_id,
            text=f"🔔 <b>НАГАДУВАННЯ:</b>\n\n{text}",
            parse_mode="HTML"
        )
        asyncio.create_task(delete_later(message_bot, DELETE_MESSAGE_TIMEOUT))

    except Exception as e:
        print(f"Ошибка отправки напоминания: {e}")




@dp.message(F.text == "🗓 На тиждень")
@dp.message(Command("week"))
async def cmd_week(message: types.Message):
    week_dates = get_week_dates()

    current_weekday = datetime.datetime.now(TZ_UKRAINE).weekday()

    day_index = 0 if current_weekday > 4 else current_weekday

    date_str = week_dates[day_index]
    lessons = api.get_by_date(date_str, await storage.get_group_id(message.chat.id))

    if not lessons:
        lessons_text = "Пар нема!"
    else:
        lessons_text = "\n\n".join(lessons)

    text = f"📅 <b>Розклад на тиждень</b>\nДата: {date_str} (День {day_index + 1})\n\n{lessons_text}"

    message_bot = await message.answer(
        text, reply_markup=get_week_keyboard(day_index), parse_mode="HTML"
    )
    asyncio.create_task(delete_later(message_bot, DELETE_MESSAGE_TIMEOUT))
    asyncio.create_task(delete_later(message, DELETE_MESSAGE_TIMEOUT))


@dp.callback_query(F.data.startswith("week_"))
async def on_week_click(callback: types.CallbackQuery):
    day_index = int(callback.data.split("_")[1])

    week_dates = get_week_dates()
    date_str = week_dates[day_index]

    lessons = api.get_by_date(
        date_str, await storage.get_group_id(callback.message.chat.id)
    )

    if not lessons:
        lessons_text = "Пар нема!"
    else:
        lessons_text = "\n\n".join(lessons)

    new_text = f"📅 <b>Розклад на тиждень</b>\nДата: {date_str}\n\n{lessons_text}"

    with suppress(TelegramBadRequest):
        await callback.message.edit_text(
            new_text, reply_markup=get_week_keyboard(day_index), parse_mode="HTML"
        )

    await callback.answer()


"""Допоміжні функції"""


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


def get_week_dates():
    now = datetime.datetime.now(TZ_UKRAINE)
    start_of_week = now - datetime.timedelta(days=now.weekday())

    week_dates = []
    for i in range(5):
        day = start_of_week + datetime.timedelta(days=i)
        week_dates.append(day.strftime("%d.%m.%Y"))

    return week_dates

async def update_all_schedules():
    """Обновляет расписание для всех групп"""
    current_chats = await storage.get_all_chats()
    for chat_id in current_chats:
        group_id = await storage.get_group_id(chat_id)
        if group_id:
            api.get_csv_schedule_by_day(group_id)


async def send_morning_schedule():
    """Отправляет утреннее расписание во все чаты"""
    current_chats = await storage.get_all_chats()
    for chat_id in current_chats:
        group_id = await storage.get_group_id(chat_id)
        if not group_id:
            continue

        date = datetime.datetime.now().strftime("%d.%m.%Y")
        lessons = api.get_by_date(date, group_id)
        if not lessons:
            continue

        lessons_text = "\n\n".join(lessons)
        message_bot = await bot.send_message(
            chat_id=int(chat_id),
            text=f"☀️  <b> Доброго ранку! Розклад на сьогодні:</b>\n\n{lessons_text}",
            parse_mode="HTML",
        )

        # Закрепляем сообщение
        with suppress(TelegramBadRequest):
            await bot.pin_chat_message(
                chat_id=int(chat_id),
                message_id=message_bot.message_id,
                disable_notification=True
            )

        # Удаляем в конце дня
        asyncio.create_task(delete_at_end_of_day(message_bot))


async def delete_later(message, time):
    await asyncio.sleep(time)
    with suppress(TelegramBadRequest):
        await message.delete()


async def delete_at_end_of_day(message):
    """Удаляет сообщение в конце дня (23:59)"""
    now = datetime.datetime.now(TZ_UKRAINE)
    end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)

    # Если уже поздно, удаляем завтра
    if now >= end_of_day:
        end_of_day += datetime.timedelta(days=1)

    sleep_seconds = (end_of_day - now).total_seconds()
    await asyncio.sleep(sleep_seconds)

    with suppress(TelegramBadRequest):
        await message.delete()


def get_keyboard(list, adj):
    builder = InlineKeyboardBuilder()

    for i in list:
        builder.button(text=i, callback_data=i)
    builder.adjust(adj)
    return builder.as_markup()

async def main():
    print("Бот запущений...")

    # Обновление расписания каждый день в 6:00
    scheduler.add_job(
        update_all_schedules,
        trigger="cron",
        hour=6,
        minute=0,
        timezone=TZ_UKRAINE,
    )

    # Отправка утреннего расписания в 7:00
    scheduler.add_job(
        send_morning_schedule,
        trigger="cron",
        hour=9,
        minute=0,
        timezone=TZ_UKRAINE,
    )

    # Обновление расписания при запуске бота
    await update_all_schedules()

    scheduler.start()
    dp.include_router(reminder_router)
    dp.include_router(form_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())