import telebot
import config
import psycopg2
import pandas as pd
import datetime
import numpy as np
import logging
import time
from geopy.geocoders import Nominatim, GoogleV3
from geopy.distance import distance
from telebot import apihelper, types
# from flask import Flask, request, abort

telebot.logger.setLevel(logging.INFO) # Outputs debug messages to console.
logger = telebot.logger
bot = telebot.TeleBot(config.token)  # авторизация
geolocator = GoogleV3()             # геокодер
# server = Flask(__name__)

# apihelper.proxy = {'https': 'socks5://47.75.31.98:1080'}
apihelper.proxy = {'https': 'socks5://telegram:telegram@ajzet.teletype.live:443'}

@bot.message_handler(commands = ['start'])
def start(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    greetings = 'Привет, я чат-бот Лето Лаундж! Поделись своим номером, чтобы я мог тебя опознать.'
    button_getContact = types.KeyboardButton(text='Поделиться номером', request_contact=True)
    keyboard.add(button_getContact)
    msg = bot.send_message(message.chat.id, greetings, reply_markup=keyboard)
    bot.register_next_step_handler(msg, identificate)

@bot.message_handler(content_types = ['contact'])
def identificate(message):
    phone = message.contact.phone_number
    name, position = '', ''
    empls = pd.read_excel('Phones.xlsx')
    found = False
    print(phone)
    for i, row in empls.iterrows():
        if str(row['Phone']) == phone or str(row['Phone']) == phone[1:]:
            name = row['Name']
            position = row['Position']
            found = True
            break

    if found:
        conn, cur = get_cursor()
        cur.execute('''SELECT ID FROM EMPLOYEES;''')
        ids = [val[0] for val in cur.fetchall()]
        if message.chat.id not in ids:
            cur.execute('''INSERT INTO EMPLOYEES VALUES ({0}, '{1}', '{2}', '{3}', Null, Null, Null);'''.format(message.chat.id, phone, name, position))
        conn.commit()
        conn.close()

        keyboard = get_main_keyboard(position)
        msg = bot.send_message(message.chat.id, 'Вы - {0}\nДолжность:{1}\nТелефон:{2}'.format(name, position, phone), reply_markup=keyboard)
        bot.register_next_step_handler(msg, main_job)

    else:
        bot.send_message(message.chat.id, 'Извините, ваш телефон не найден в базе сотрудников заведения')
        #TODO

@bot.message_handler(func = lambda message: message.text in config.main_buttons, content_types = ['text'])
def main_job(message):
    conn, cur = get_cursor()
    cur.execute('''SELECT position from EMPLOYEES WHERE ID = {0};'''.format(message.chat.id))
    position = cur.fetchone()[0]
    conn.close()
    if message.text == 'Пришел на работу':
        bot.send_photo(message.chat.id, open('location.png', 'rb'), caption='Окей, отправь мне свой live location')
        # bot.register_next_step_handler(msg, share_geo_came)
    elif message.text == 'Ухожу с работы':
        pass
        # msg = bot.send_message(message.chat.id, 'Ок, поделись гео')
        # bot.register_next_step_handler(msg, ????)
    elif message.text == 'Чек-лист':
        keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        button_task1 = types.KeyboardButton(text=config.check_list_buttons[0])
        button_task2 = types.KeyboardButton(text=config.check_list_buttons[1])
        button_task3 = types.KeyboardButton(text=config.check_list_buttons[2])
        button_back = types.KeyboardButton(text='Назад')
        keyboard.add(button_task1, button_task2, button_task3, button_back)
        bot.send_message(message.chat.id, 'Твои задачи:', reply_markup=keyboard)
        # bot.register_next_step_handler(message, ????)
    elif message.text == 'Отчет':
        keyboard = get_report_keyboard()
        msg = bot.send_message(message.chat.id, 'Выбери вариант', reply_markup=keyboard)
        bot.register_next_step_handler(message, report_job)

@bot.message_handler(func = lambda message: message.text in config.report_buttons, content_types = ['text'])
def report_job(message):
    conn, cur = get_cursor()
    if message.text == 'На смене':
        cur.execute('''SELECT * FROM EMPLOYEES WHERE on_turn = True''')
        string = get_report(cur)
        bot.send_message(message.chat.id, string)
    elif message.text == 'Не на смене':
        cur.execute('''SELECT * FROM EMPLOYEES WHERE on_turn = False''')
        string = get_report(cur)
        bot.send_message(message.chat.id, string)
    elif message.text == 'По всем':
        cur.execute('''SELECT * FROM EMPLOYEES''')
        string = get_report(cur)
        bot.send_message(message.chat.id, string)
    elif message.text == 'Назад':
        back(message)
    conn.close()

@bot.message_handler(func = lambda message: message.text == 'Назад', content_types = ['text'])
def back(message):
    conn, cur = get_cursor()
    cur.execute('''SELECT position from EMPLOYEES WHERE ID = {0};'''.format(message.chat.id))
    position = cur.fetchone()[0]
    conn.close()
    keyboard = get_main_keyboard(position=position)
    msg = bot.send_message(message.chat.id, 'Меню', reply_markup=keyboard)
    bot.register_next_step_handler(msg, main_job)

@bot.edited_message_handler(content_types=['location'])
def change_location(message):
    date = datetime.datetime.fromtimestamp(message.edit_date).strftime('%Y-%m-%d %H:%M:%S')
    nearest_hookah, min_dist = share_geo(message)
    print('DATE: ', date)
    print('LOCATION: ', message.location)
    print('Min dist: ', min_dist)
    print('---------------')
    conn, cur = get_cursor()
    if min_dist < 100:
        cur.execute('''UPDATE employees SET on_turn = True WHERE ID = {0};'''.format(message.chat.id))
        cur.execute('''UPDATE employees SET location = '{1}' WHERE ID = {0};'''.format(message.chat.id, nearest_hookah))
        cur.execute('''UPDATE employees SET update_date = '{1}' WHERE ID = {0};'''.format(message.chat.id, date))
    else:
        cur.execute('''UPDATE employees SET on_turn = False WHERE ID = {0};'''.format(message.chat.id))
        cur.execute('''UPDATE employees SET location = 'OUT OF PLACE' WHERE ID = {0};'''.format(message.chat.id))
        cur.execute('''UPDATE employees SET update_date = '{1}' WHERE ID = {0};'''.format(message.chat.id, date))
    conn.commit()
    conn.close()

def share_geo(message):
    cur_coords = (message.location.latitude, message.location.longitude)
    distances = np.array([distance(cur_coords, coords).m for coords in config.addresses.values()])
    min_dist = min(distances)
    nearest_hookah = list(config.addresses.keys())[np.argmin(distances)]
    return nearest_hookah, min_dist

def get_cursor():
    conn = psycopg2.connect(database="LetoLoungeDB", user="postgres", password="alexkonst", host="localhost", port=5432)
    cur = conn.cursor()
    return conn, cur

def get_main_keyboard(position):
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button_came = types.KeyboardButton(text=config.main_buttons[0])
    button_exit = types.KeyboardButton(text=config.main_buttons[1])
    button_checkList = types.KeyboardButton(text=config.main_buttons[2])
    button_report = types.KeyboardButton(text=config.main_buttons[3])
    keyboard.add(button_came, button_exit)
    if position == 'Старший':
        keyboard.add(button_checkList)
    if position == 'Админ':
        keyboard.add(button_checkList, button_report)
    return keyboard

def get_report_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    button_report_all = types.KeyboardButton(text=config.report_buttons[0])
    button_report_onTurn = types.KeyboardButton(text=config.report_buttons[1])
    button_report_notOnTurn = types.KeyboardButton(text=config.report_buttons[2])
    button_report_back = types.KeyboardButton(text=config.report_buttons[3])
    keyboard.add(button_report_all, button_report_onTurn, button_report_notOnTurn, button_report_back)
    return keyboard

def get_report(cur):
    data = cur.fetchall()
    string = ''
    locs = set([tup[4] for tup in data])
    for l in locs:
        i = 0
        for tup in data:
            if tup[4] == l:
                i += 1
                string += '{0}\n{1}. {2}\n{3}\n{4}\n'.format(l, i, tup[2], tup[3], tup[1])
    if string == '':
        string = 'Таких сотрудников в данный момент нет'
    return string

# @server.route("/bot", methods = ['GET','POST'])
# def getMessage():
#     try:
#         new_updates = [telebot.types.Update.de_json(request.stream.read().decode("utf-8"))]
#         bot.process_new_updates(new_updates)
#     except:
#         bot.send_message(config.creator_id, 'Я сломался')
#     return "ok", 200

# @server.route("/")
# def webhook():
#     bot.remove_webhook()
#     bot.set_webhook(url = "https://letolounge.herokuapp.com/bot")
#     return "ok", 200

# server.run(host = "0.0.0.0", port = os.environ.get('PORT', 5000))
# server = Flask(__name__)

if __name__ == '__main__':
    bot.polling(none_stop=True)



# @bot.message_handler(content_types = ['location'])
# def share_geo_came(message):
#     msg = bot.send_message(message.chat.id, 'Ок, ближайшая к тебе кальянная - {0}. До нее примерно {1}м.'.format(nearest_hookah, int(min_dist)))
#     bot.register_next_step_handler(msg, main_job)

# @bot.message_handler(content_types = ['location'])
# def share_geo_exit(message):
#     nearest_hookah, min_dist = share_geo(message)
#     msg = bot.send_message(message.chat.id, 'Ок, хорошего дня!')
#     bot.register_next_step_handler(msg, main_job)



# TODO:
# Проверить, не продублируется ли запись в бд при идентификации
# На смене/не на смене - пустое сообщение - ошибка
#


# ---------------
# DATE:  2018-07-04 21:23:34
# LOCATION:  {'longitude': 37.582469, 'latitude': 55.725145}
# Min dist:  6.41302183381
# ---------------
# DATE:  2018-07-04 21:27:40
# LOCATION:  {'longitude': 37.732262, 'latitude': 55.780429}
# Min dist:  3571.0363829
