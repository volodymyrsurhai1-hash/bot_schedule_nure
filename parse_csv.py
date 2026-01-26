from datetime import datetime, timedelta
import json
import csv
from config import API_URL
import requests
import os

class ScheduleAPI:
    def __init__(self):
        with open("jsons\\groups.json", "r", encoding="utf-8") as f:
            self.data = json.load(f)

        self.university = self.data.get("university", {})
        self.specialties = self.university.get("faculties", [])

        self.list_of_facs = [i.get("full_name") for i in self.university.get('faculties', [])]

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

    def get_groups(self, groups, name_group: str ):
        for i in groups:
            if name_group in i.get("name"):
                return i.get("id")

    def get_csv_schedule_by_day(self, group_id: int, day: str = datetime.now().strftime('%d.%m.%Y'), day_end: str = (datetime.now() + timedelta(days=182)).strftime('%d.%m.%Y') ):
        if os.path.exists(f"csvs\\schedule_{group_id}_{day}.csv") == False:
            self.content = requests.get(f'https://cist.nure.ua/ias/app/tt/WEB_IAS_TT_GNR_RASP.GEN_GROUP_POTOK_RASP?ATypeDoc=3&Aid_group={group_id}&Aid_potok=0&ADateStart={day}&ADateEnd={day_end}&AMultiWorkSheet=0')
            with open(f"csvs\\schedule_{group_id}.csv", "wb") as f:
                f.write(self.content.content)

    def get_by_date(self, date: str, group_id: int):
        with open(f"csvs\\schedule_{group_id}.csv", 'r', encoding='windows-1251') as f:
            self.table = csv.reader(f, delimiter=',')
            next(self.table)
            self.schedule_list = []

            for row in self.table:
                if len(row) < 12:
                    continue
                if row[1] != date:
                    continue
                subject = row[11]
                start_time = row[2]
                end_time = row[4]

                self.schedule_list.append(f"🕒 {start_time}-{end_time}\n📚 {subject}")

            return self.schedule_list

#
if __name__ == "__main__":
    api = ScheduleAPI()
    fac = api.get_specialty("ITM")
    f = api.get_faculties(fac, 'СТСА')
    id = api.get_groups(f, 'СТСА-25-1')
    api.get_csv_schedule_by_day(id)
    text = api.get_by_date("19.02.2026", id)




