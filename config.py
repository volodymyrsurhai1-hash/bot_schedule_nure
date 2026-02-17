import os

from dotenv import load_dotenv

load_dotenv()

# TG token
TOKEN = os.getenv("TOKEN")


API_URL = "https://cist.nure.ua/ias/app/tt/WEB_IAS_TT_GNR_RASP.GEN_GROUP_POTOK_RASP?ATypeDoc=3&Aid_group={}&Aid_potok=0&ADateStart={}&ADateEnd={}&AMultiWorkSheet=0"

# Время удаления сообщений (в секундах)
DELETE_MESSAGE_TIMEOUT = 100