import csv
import json
import os
from datetime import datetime, timedelta

import requests

from config import API_URL, URLS


class ScheduleAPI:
    def __init__(self):
        groups_path = os.path.join("jsons", "groups.json")
        with open(groups_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

        self.university = self.data.get("university", {})
        self.specialties = self.university.get("faculties", [])
        self.list_of_facs = [
            i.get("full_name") for i in self.university.get("faculties", [])
        ]
        self.url = API_URL

    def get_specialty(self, specialty_name: str):
        for i in self.specialties:
            db_name = i.get("full_name")
            if specialty_name in db_name:
                yield i.get("directions")

    def get_faculties(self, faculties, faculty_name: str):
        for i in faculties:
            for j in i:
                if faculty_name in j.get("full_name"):
                    return j.get("groups")

    def get_groups(self, groups, name_group: str):
        for i in groups:
            if name_group in i.get("name"):
                return i.get("id")

    def get_csv_schedule_by_day(
        self,
        group_id: int,
        day: str = datetime.now().strftime("%d.%m.%Y"),
        day_end: str = (datetime.now() + timedelta(days=182)).strftime("%d.%m.%Y"),
    ):
        csvs_dir = "csvs"
        os.makedirs(csvs_dir, exist_ok=True)

        schedule_path = os.path.join(csvs_dir, f"schedule_{group_id}.csv")
        if not os.path.exists(schedule_path):
            url = (
                f"https://cist.nure.ua/ias/app/tt/WEB_IAS_TT_GNR_RASP.GEN_GROUP_POTOK_RASP"
                f"?ATypeDoc=3&Aid_group={group_id}&Aid_potok=0"
                f"&ADateStart={day}&ADateEnd={day_end}&AMultiWorkSheet=0"
            )
            self.content = requests.get(url)
            with open(schedule_path, "wb") as f:
                f.write(self.content.content)

    def get_by_date(self, date, group_id: int):
        # Получаем название группы для фильтрации ссылок
        group_name = self._get_group_name(group_id)

        schedule_path = os.path.join("csvs", f"schedule_{group_id}.csv")
        with open(schedule_path, "r", encoding="windows-1251") as f:
            self.table = csv.reader(f, delimiter=",")
            next(self.table)
            self.schedule_list = []

            for row in self.table:
                if len(row) < 12:
                    continue
                if row[1] != date:
                    continue
                subject_full = row[11]
                start_time = row[2]
                end_time = row[4]

                # Обрезаем строку - оставляем только название и тип пары
                # Например: "БЗВП Лк DL ЕЕК-24-1;СТСА-24-1;..." -> "БЗВП Лк DL"
                subject_parts = subject_full.split()
                if len(subject_parts) >= 3:
                    # Берем первые 3 части (название + тип + DL/очно)
                    subject = " ".join(subject_parts[:3])
                elif len(subject_parts) >= 2:
                    # Если нет третьей части, берем первые 2
                    subject = " ".join(subject_parts[:2])
                else:
                    subject = subject_full

                # Формируем текст
                lesson_text = f"🕒 {start_time}-{end_time}\n📚 {subject}"

                # Ищем ссылку для предмета только для группы СТСА-25-1
                if group_name == "СТСА-25-1":
                    link = self._get_lesson_link(subject_full)
                    if link:
                        lesson_text += f"\n🔗 <a href='{link}'>Посилання на пару</a>"

                self.schedule_list.append(lesson_text)

            return self.schedule_list

    def _get_group_name(self, group_id: int):
        """Получает название группы по ее ID"""
        for faculty in self.specialties:
            for direction in faculty.get("directions", []):
                for group in direction.get("groups", []):
                    if group.get("id") == group_id:
                        return group.get("name")
        return None

    def _get_lesson_link(self, subject: str):
        """Получает ссылку на пару из конфига по названию и типу"""
        # Парсим строку типа "АлГе Лк DL ППМ-25-1;СТСА-25-1"
        parts = subject.split()
        if len(parts) < 2:
            return None

        subject_name = parts[0]  # Например, "АлГе"
        lesson_type = parts[1]    # Например, "Лк"

        # Ищем в словаре URLS
        if subject_name in URLS:
            subject_urls = URLS[subject_name]
            if lesson_type in subject_urls:
                return subject_urls[lesson_type]

        return None


if __name__ == "__main__":
    api = ScheduleAPI()
    fac = api.get_specialty("ITM")
    f = api.get_faculties(fac, "СТСА")
    id = api.get_groups(f, "СТСА-25-1")
    api.get_csv_schedule_by_day(id)
    text = api.get_by_date("19.02.2026", id)




