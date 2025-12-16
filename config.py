
import os
from dotenv import load_dotenv
load_dotenv()

#TG token
TOKEN = os.getenv('TOKEN')

#Посилання на пари
URLS = {
    'АлГе' : {'Лк' : 'https://meet.google.com/bux-kjqu-akg',
              'Пз' : 'https://meet.google.com/dzq-xgjk-bmr'},
    'ДМ' : {'Лк' : 'https://meet.google.com/fqg-axtt-kjf',
              'Пз' : 'https://meet.google.com/fqg-axtt-kjf'},
    'ІМ' : {"Лк":'https://meet.google.com/fmn-qhqd-icc',
            "Пз":'https://meet.google.com/fmn-qhqd-icc'},
    'МатАн' : {'Лк' : 'https://meet.google.com/uxs-ygre-yem',
              'Пз' : 'https://meet.google.com/vuz-wcte-rax'},
    'ОІКНІ' : {'Лк' : 'Посилання відсутнє!'},
    'Про' : {'Лк' : 'https://nure-ua.zoom.us/j/83535714828?pwd=J12hBH0WkzGS7IKgzLq4hMroEbcb1U.1',
              'Пз' : 'https://nure-ua.zoom.us/j/85802727920?pwd=kHLAZ2NyYVJybUanWQMYZBLQ0OZn7e.1#success',
              'Лб' : 'https://nure-ua.zoom.us/j/85802727920?pwd=kHLAZ2NyYVJybUanWQMYZBLQ0OZn7e.1#success',
             },
    'УФМ' : {'Лк' : 'https://meet.google.com/ppw-vwqs-baa',
              'Пз' : 'https://meet.google.com/gui-cbks-own'},
    'Фіз' : {'Лк' : 'https://meet.google.com/njk-hgkf-ziq',
            'Пз' : 'https://meet.google.com/njk-hgkf-ziq',
              'Лб' : 'https://meet.google.com/qor-fbgn-kqf'},
    'ФВ' : {"Пз" : 'https://meet.google.com/ydi-wznu-cpb'},
}