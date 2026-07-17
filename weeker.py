import psycopg2
import socket
import telebot
import os
import re
from datetime import datetime, timezone
import time
import threading
import random

TOKEN = os.environ.get('BOT_TOKEN')
DATA_BASE = os.environ.get('DATABASE_URL')
bot = telebot.TeleBot(TOKEN)

MESSAGES = [
    "Недель прошло: {weeks}\n Поздравляем. Так держать.",
    "Прошла неделя номер {weeks}\n Неплохо держитесь.",
    "Прошла {weeks} неделя\n Продолжайте в том же духе.",
    "Недель прошло: {weeks}\n Неплохо держитесь.",
    "Прошла неделя номер {weeks}\n Поздравляем. Так держать."
]

def connect_db():
    try:
        old_getaddrinfo = socket.getaddrinfo
        
        def new_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            return old_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
        
        socket.getaddrinfo = new_getaddrinfo
        conn = psycopg2.connect(
            DATA_BASE,
            sslmode='require',
            connect_timeout=30,
            keepalives_idle=5,
            keepalives_interval=2,
            keepalives_count=2
        )
        return conn
    except Exception as e:
        print(f"Ошибка базы данных: {e}")
        return None

def cr_table():
    connectdb = connect_db()
    if connectdb is None:
        return
    try:
        cur = connectdb.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_dates (
            user_id TEXT PRIMARY KEY,
            date_str TEXT NOT NULL,
            timezone_offset INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW()
            );           
        """)
        connectdb.commit()
        cur.close()
        connectdb.close()
    except Exception as e:
        print(f"Ошибка создания таблицы {e}")

def save_date(user_id, date_str):
    user_id = str(user_id)
    connectdb = connect_db()
    if connectdb is None:
        return False
    try:
        cur = connectdb.cursor()
        cur.execute("""
            INSERT INTO user_dates (user_id, date_str, timezone_offset)
            VALUES (%s, %s, COALESCE((SELECT timezone_offset FROM user_dates WHERE user_id = %s), 0))
            ON CONFLICT (user_id) DO UPDATE SET date_str = EXCLUDED.date_str;        
        """, (user_id, date_str, user_id))
        connectdb.commit()
        cur.close()
        connectdb.close()
        return True
    except Exception as e:
        print(f"Ошибка сохранения даты {e}")
        return False

def load_date(user_id):
    user_id = str(user_id)
    connectdb = connect_db()
    if connectdb is None:
        return None
    try:
        cur = connectdb.cursor()
        cur.execute("SELECT date_str FROM user_dates WHERE user_id = %s;", (user_id,))
        res = cur.fetchone()
        cur.close()
        connectdb.close()
        return res[0] if res else None
    except Exception as e:
        print(f"Ошибка загрузки даты {e}")
        return None

def load_timezone(user_id):
    connectdb = connect_db()
    if connectdb is None:
        return 0
    try:
        cur = connectdb.cursor()
        cur.execute("SELECT timezone_offset FROM user_dates WHERE user_id = %s;", (user_id,))
        res = cur.fetchone()
        cur.close()
        connectdb.close()
        return res[0] if res else 0
    except Exception as e:
        print(f"Ошибка загрузки часового пояса {e}")
        return 0

def save_timezone(user_id, offset):
    connectdb = connect_db()
    if connectdb is None:
        return False
    try:
        cur = connectdb.cursor()
        cur.execute("""
                INSERT INTO user_dates (user_id, date_str, timezone_offset)
                VALUES (%s, '', %s)
                ON CONFLICT (user_id) DO UPDATE SET timezone_offset = EXCLUDED.timezone_offset;        
            """, (user_id, offset))
        connectdb.commit()
        cur.close()
        connectdb.close()
        return True
    except Exception as e:
        print(f"Ошибка сохранения timezone {e}")
        return False

def get_users():
    connectdb = connect_db()
    if connectdb is None:
        return {}
    try:
        cur = connectdb.cursor()
        cur.execute("SELECT user_id, date_str, timezone_offset FROM user_dates;")
        res = cur.fetchall()
        cur.close()
        connectdb.close()
        return {row[0]: (row[1], row[2]) for row in res}
    except Exception as e:
        print(f"Ошибка загрузки пользоватлей {e}")
        return {}

def delete_data(user_id):
    connectdb = connect_db()
    if connectdb is None:
        return False
    try:
        cur = connectdb.cursor()
        cur.execute("DELETE FROM user_dates WHERE user_id = %s;", (user_id,))
        connectdb.commit()
        cur.close()
        connectdb.close()
        return True
    except Exception as e:
        print(f"Ошибка удаления пользователя {e}")
        return False


def make_data(text):
    pattern = r'\b(\d{2})\.(\d{2})\.(\d{4})\b'
    match = re.search(pattern, text)
    if match:
        day, month, year = match.groups()
        try:
            date_obj = datetime.strptime(f"{day}.{month}.{year}", "%d.%m.%Y")
            return date_obj
        except ValueError:
            return None
    return None

def get_week(date_str):
    try:
        user_date = datetime.strptime(date_str, "%d.%m.%Y")
        today = datetime.now()
        if user_date > today:
            return None
        delta = today - user_date
        return delta.days // 7
    except ValueError:
        return None

def random_massege(weeks):
    return random.choice(MESSAGES).format(
        weeks = weeks
    )

def send_report(chat_id, date_str):
    weeks = get_week(date_str)
    if weeks is None:
        bot.send_message(chat_id, "Ошибкa. Установите новую дату.")
        return
    msg = random_massege(weeks)
    bot.send_message(chat_id, msg)

def make_timezone():
    users = get_users()
    if not users:
        return
    now_utc = datetime.now(timezone.utc)
    if now_utc.weekday() != 6:
        return 
    for user_id, (date_str, offset) in users.items():
        if not date_str:
            continue
        hour = (now_utc.hour + offset) % 24
        if hour == 22 and now_utc.minute == 0:
            try:
                send_report(user_id, date_str)
            except Exception as e:
                print(f"Ошибка {user_id}: {e}")

def plan():
    while True:
        make_timezone()
        time.sleep(60)



@bot.message_handler(commands = ['start'])
def start(message):
    uid = str(message.chat.id)
    date = load_date(uid)
    if date:
        weeks = get_week(date)
        if weeks is not None:
            bot.send_message(uid, "Что бы перезаписать дату используйте /deletedate")
        else:
            bot.send_message(uid, "Ошибка с датой. Отправьте новую.")
    else:
        bot.send_message(uid, "Приветствуем.\n\nЭтот бот будет еженедельно по воскресеньям в 10 вечера присылать вам отчет о количестве прожитых вами недель.\n\n\n"
                              "Для начала отправьте дату своего рождения в формате ДД.ММ.ГГГГ, а затем используйте '/timezone UTC+/-N' для указания вашего часового пояса относительно Гринвича.")

@bot.message_handler(commands = ['timezone'])
def get_time(message):
    uid = str(message.chat.id)
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(uid, "Используйте '/timezone UTC+/-N'.")
            return
        del_utc = parts[1].upper().replace('UTC', '')
        utc_int = int(del_utc)
        if not (-12 <= utc_int <= 14):
            bot.send_message(uid, 'Часовой пояс должен быть от UTC-12 до UTC+14.')
            return
        if save_timezone(uid, utc_int):
            bot.send_message(uid, "Часовой пояс установлен.")
            bot.send_message(uid, "Авторизация прошла успешно. Ожидайте воскресенья.")
        else:
            bot.send_message(uid, "Ошибка сохранения.")
    except:
        bot.send_message(uid, "Используйте '/timezone UTC+/-N'.")

@bot.message_handler(commands = ['deletedate'])
def del_date(message):
    uid = str(message.chat.id)
    if delete_data(uid):
        bot.send_message(uid, "Текущая дата удалена.")
    else:
        bot.send_message(uid, "Ошибка удаления даты.")

@bot.message_handler(commands = ['check'])
def chek_date(message):
    uid = str(message.chat.id)
    date = load_date(uid)
    if not date:
        bot.send_message(uid, "Установите дату.")
        return
    weeks = get_week(date)
    if weeks is None:
         bot.send_message(uid, "Установите новую дату.")
         return
    else:
        bot.send_message(uid, f"прошло {weeks}")

@bot.message_handler(func = lambda m: True)
def serch_date(message):
    uid = str(message.chat.id)
    obj = make_data(message.text)
    if obj:
        date_str = obj.strftime("%d.%m.%Y")
        if obj > datetime.now():
            bot.send_message(uid, f"Дата {date_str} еще не наступила.")
            return
        if save_date(uid, date_str):
            bot.send_message(uid, "Дата сохранена.")
        else:
            bot.send_message(uid, "Ошибка сохранения даты.")
    else:
        bot.send_message(uid, "Сообщение некореектно или не распознано.")





cr_table()
threading.Thread(target=plan, daemon=True).start()
bot.polling(non_stop=True)

