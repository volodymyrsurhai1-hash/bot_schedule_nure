import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import requests

from config import API_URL

# CSV column indices
CSV_COL_DATE = 1
CSV_COL_START_TIME = 2
CSV_COL_END_TIME = 4
CSV_COL_SUBJECT = 11
CSV_MIN_COLUMNS = 12

CSV_ENCODING = "windows-1251"
GROUPS_JSON_PATH = Path("jsons") / "groups.json"
CSV_DIR = Path("csvs")


@dataclass
class Lesson:
    start_time: str
    end_time: str
    subject: str

    def __str__(self) -> str:
        return f"🕒 {self.start_time}-{self.end_time}\n📚 {self.subject}"

    # Залишаємо для сумісності зі старим кодом
    def to_text(self) -> str:
        return str(self)


class GroupRepository:
    """Відповідає за читання JSON-файлу груп та пошук group_id."""

    def __init__(self, groups_path: Path = GROUPS_JSON_PATH) -> None:
        if not groups_path.exists():
            raise RuntimeError(f"Файл груп не знайдено: {groups_path}")

        with open(groups_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        university = data.get("university", {})
        self.specialties = university.get("faculties", [])
        self.list_of_facs = [
            faculty.get("full_name") for faculty in self.specialties
        ]

    def get_group_id(
        self, specialty_name: str, faculty_name: str, name_group: str
    ) -> int | None:
        return next(
            (
                group.get("id", "")
                for specialty in self.specialties
                if specialty_name in specialty.get("full_name", "")
                for direction in specialty.get("directions", [])
                if faculty_name in direction.get("full_name", "")
                for group in direction.get("groups", [])
                if name_group in group.get("name", "")
            ),
            None,
        )


class ScheduleDownloader:
    """Відповідає за завантаження CSV-розкладу з сервера NURE."""

    def download(self,
        group_id: int,
        day: str | None = None,
        day_end: str | None = None,
    ) -> None:
        """Завантажує CSV якщо він ще не існує локально."""
        if day is None:
            day = datetime.now().strftime("%d.%m.%Y")
        if day_end is None:
            day_end = (datetime.now() + timedelta(days=182)).strftime("%d.%m.%Y")

        CSV_DIR.mkdir(exist_ok=True)
        schedule_path = CSV_DIR / f"schedule_{group_id}.csv"

        if schedule_path.exists():
            # Если файл обновлялся сегодня, не скачиваем
            mtime = schedule_path.stat().st_mtime
            modified_date = datetime.fromtimestamp(mtime).date()
            if modified_date == datetime.now().date():
                return

        url = API_URL.format(group_id, day, day_end)
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Таймаут при завантаженні розкладу для групи {group_id}")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"Помилка HTTP при завантаженні розкладу: {e}")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Помилка мережі: {e}")

        with open(schedule_path, "wb") as f:
            f.write(response.content)


class ScheduleParser:
    """Відповідає за парсинг CSV та повернення списку уроків."""

    @staticmethod
    def get_by_date(date: str, group_id: int) -> list[Lesson]:
        schedule_path = CSV_DIR / f"schedule_{group_id}.csv"

        if not schedule_path.exists():
            raise RuntimeError(
                f"CSV-файл розкладу не знайдено: {schedule_path}. "
                "Спочатку викличте ScheduleDownloader.download()."
            )

        lessons: list[Lesson] = []

        with open(schedule_path, "r", encoding=CSV_ENCODING) as f:
            table = csv.reader(f, delimiter=",")
            next(table)  # пропускаємо заголовок

            for row in table:
                if len(row) < CSV_MIN_COLUMNS:
                    continue
                if row[CSV_COL_DATE] != date:
                    continue

                subject_full = row[CSV_COL_SUBJECT]
                start_time = row[CSV_COL_START_TIME]
                end_time = row[CSV_COL_END_TIME]

                # Обрізаємо рядок — залишаємо лише назву і тип пари
                # Наприклад: "БЗВП Лк DL ЕЕК-24-1;..." → "БЗВП Лк DL"
                subject_parts = subject_full.split()
                if len(subject_parts) >= 3:
                    subject = " ".join(subject_parts[:3])
                elif len(subject_parts) >= 2:
                    subject = " ".join(subject_parts[:2])
                else:
                    subject = subject_full

                lessons.append(Lesson(start_time, end_time, subject))

        return lessons


# Фасад для зворотної сумісності зі старим кодом
class ScheduleAPI:
    """Зберігається для зворотної сумісності. Делегує роботу спеціалізованим класам."""

    def __init__(
        self,
        repo: GroupRepository | None = None,
        downloader: ScheduleDownloader | None = None,
        parser: ScheduleParser | None = None,
    ) -> None:
        self._repo = repo or GroupRepository()
        self._downloader = downloader or ScheduleDownloader()
        self._parser = parser or ScheduleParser()
        self.specialties = self._repo.specialties
        self.list_of_facs = self._repo.list_of_facs

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

    def get_group_id(
        self, specialty_name: str, faculty_name: str, name_group: str
    ) -> int | None:
        return self._repo.get_group_id(specialty_name, faculty_name, name_group)

    def get_csv_schedule_by_day(
        self,
        group_id: int,
        day: str | None = None,
        day_end: str | None = None,
    ) -> None:
        self._downloader.download(group_id, day, day_end)

    def get_by_date(self, date: str, group_id: int) -> list[Lesson]:
        return self._parser.get_by_date(date, group_id)


if __name__ == "__main__":
    api = ScheduleAPI()
    group_id = api.get_group_id("ITM", "СТСА", "СТСА-25-1")
    api.get_csv_schedule_by_day(group_id)
    lessons = api.get_by_date("1.09.2026", group_id)

    for lesson in lessons:
        print(lesson)
