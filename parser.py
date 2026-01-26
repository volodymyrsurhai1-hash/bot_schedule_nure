import requests
from bs4 import BeautifulSoup
from config import URLS

def load_and_parse_schedule():
    """
    1. Скачивает страницу.
    2. Парсит XLSX.
    3. Возвращает словарь { "dd.mm.yyyy": { "time": "lesson" } }
    """
    url = 'https://cist.nure.ua/ias/app/tt/f?p=778:201:3927467815032133:::201:P201_FIRST_DATE,P201_LAST_DATE,P201_GROUP,P201_POTOK:01.09.2025,31.01.2026,11870682,0'

    try:
        html_content = requests.get(url).text
    except Exception as e:
        print(f"Ошибка сети: {e}")
        return {}

    soup = BeautifulSoup(html_content, "html.parser")
    table = soup.find("table", class_="MainTT")

    schedule_map = {}
    current_day_dates = []

    if not table:
        return {}

    rows = table.find_all("tr")

    for row in rows:
        first_cell = row.find("td")
        if not first_cell: continue

        if "date" in first_cell.get("class", []) and first_cell.get("colspan") == "2":
            date_cells = row.find_all("td")[1:]
            current_day_dates = [d.get_text(strip=True) for d in date_cells]
            for date in current_day_dates:
                if date not in schedule_map:
                    schedule_map[date] = {}
            continue

        if "left" in first_cell.get("class", []):
            cells = row.find_all("td")
            if len(cells) < 3: continue

            raw_time = cells[1].get_text(strip=True)
            formatted_time = raw_time.replace(" ", "-") if " " in raw_time else raw_time
            subject_cells = cells[2:]
            current_week_index = 0

            for cell in subject_cells:
                colspan = int(cell.get("colspan", 1))
                content = cell.get_text(" ", strip=True)

                has_lesson = content and content != "&nbsp" and len(content) > 1
                if has_lesson:
                    for i in range(colspan):
                        if (current_week_index + i) < len(current_day_dates):
                            target_date = current_day_dates[current_week_index + i]
                            # Запись в словарь
                            if formatted_time in schedule_map[target_date]:
                                schedule_map[target_date][formatted_time] += f" | {content}"
                            else:
                                schedule_map[target_date][formatted_time] = content

                current_week_index += colspan

    return schedule_map


def get_lessons_by_date(schedule_data, target_date):

    # 1. Проверяем, есть ли такая дата в словаре
    if target_date not in schedule_data:
        return f"📅 На дату {target_date} Розкладу нема (або дата некорректна)."

    lessons = schedule_data[target_date]

    # 2. Проверяем, есть ли уроки внутри этой даты
    if not lessons:
        return f"📅 {target_date}: Пар нема. Відпочивай! 🎉"

    # 3. Формируем красивый вывод
    result_lines = []
    result_lines.append("-" * 30)

    for time, subject in lessons.items():
        subject_name = subject.split(" ")
        if URLS.get(subject_name[0], True).get(subject_name[1], True):
            result_lines.append(f"⏰ {time} | 📚 {subject} - {URLS[subject_name[0]]['Лк']}")
            continue

        result_lines.append(f"⏰ {time} | 📚 {subject} - {URLS[subject_name[0]][subject_name[1]]}")

    return "\n".join(result_lines)


if __name__ == "__main__":
    my_schedule = load_and_parse_schedule()
    print(get_lessons_by_date(my_schedule, "29.12.2025"))



