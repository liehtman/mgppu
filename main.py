import telebot
import os
import config
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request
from datetime import datetime, date, timedelta
from telebot import types

bot = telebot.TeleBot(config.token)
server = Flask(__name__)
scope = ['https://spreadsheets.google.com/feeds']
credentials = ServiceAccountCredentials.from_json_keyfile_name(config.json_keyfile, scope)
gc = gspread.authorize(credentials)
base = gc.open("Студенты").sheet1
session = gc.open("Сессия")
logs = gc.open("Логи МГППУ").sheet1

@bot.message_handler(commands=['start'])
def start(message):
	set_id(message)
	markup = types.ReplyKeyboardMarkup()
	for course in config.courses: markup.add(course)
	bot.send_message(message.chat.id, "Привет. Выбери свой курс", reply_markup = markup)
@bot.message_handler(commands=['iseven'])
def even_or_odd(message):
	if isEven(): bot.send_message(config.creator_id, 'Сегодня ЧЕТНАЯ неделя')
	else: bot.send_message(config.creator_id, 'Сегодня НЕЧЕТНАЯ неделя')
@bot.message_handler(commands=['cleanlogs'])
def cleanlogs(message):
	if message.chat.id == config.creator_id:
		clean_logs()
		bot.send_message(message.chat.id, 'Логи очищены')
	else: bot.send_message(message.chat.id, 'Эта функция не для Вас, уважаемый:)')
@bot.message_handler(commands=['showlogs'])
def showlogs(message):
	if message.chat.id == config.creator_id: bot.send_message(message.chat.id, get_logs())
	else: bot.send_message(message.chat.id, 'Эта функция не для Вас, уважаемый:)')
@bot.message_handler(commands=['getid'])
def get_id(message):
	bot.send_message(message.chat.id, str(message.chat.id))

@bot.message_handler(func=lambda message: True, content_types=['text'])
def reply_course(message):

	if message.text=='Расписание на завтра':
		course_num, specialization = get_stud_info(message)
		table_name = course_num + ' курс ' + specialization
		bot.send_message(message.chat.id, 'Подожди, смотрю...')
		answer = parse_tomorrow(gc.open(table_name))
		bot.send_message(message.chat.id, answer)

	elif message.text in config.ses_queries:  	 # СЕССИЯ
		bot.send_message(message.chat.id, 'Подожди, смотрю...')
		answer = parse_session(message.text)
		bot.send_message(message.chat.id, answer)

	elif message.text in config.courses:  		 # ВЫБОР КУРСА
		set_stud_course(message)
		course_num, specialization = get_stud_info(message)
		table_name = course_num + ' курс ' + specialization
		markup = types.ReplyKeyboardMarkup()
		for spec in config.specializations: markup.add(spec)
		bot.send_message(message.chat.id, 'Выбери направление', reply_markup = markup)
	
	elif message.text in config.specializations: # ВЫБОР СПЕЦИАЛЬНОСТИ
		set_stud_spec(message)
		course_num, specialization = get_stud_info(message)
		table_name = course_num + ' курс ' + specialization
		markup = types.ReplyKeyboardMarkup()
		for query in config.main_queries: markup.add(query)
		bot.send_message(message.chat.id, 'Что хочешь знать?', reply_markup = markup)
	
	else: bot.send_message(message.chat.id, 'Юзай кнопки!')
	
	if message.chat.id != config.creator_id: track(message)

@server.route("/bot", methods=['POST'])
def getMessage():
	bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
	return "!", 200

@server.route("/")
def webhook():
	bot.remove_webhook()
	bot.set_webhook(url="https://mgppu.herokuapp.com/bot")
	return "!", 200		

def parse_tomorrow(table):
	if isEven(): 
		table = table.worksheet('Четная')
	else: table = table.worksheet('Нечетная')
	tomorrow = (datetime.now() + timedelta(days=1)).isoweekday()  # ЗАВТРА
	da_tomorrow = None    							 # ПОСЛЕЗАВТРА
	stud_days = [val for val in table.col_values(1) if val]
	if tomorrow == 7: return 'Пляши, завтра выходной!' # _f = table.find('1') 
	elif tomorrow == 6:
		if '6' not in stud_days:
			return 'Пляши, завтра выходной!'
		else: da_tomorrow = table.find('EOW')
	else:
		da_tomorrow = table.find(str(tomorrow + 1))
	cell_num = table.find(str(tomorrow))
	values_list = []
	msg = 'Итак, завтра у тебя:\n'
	for i in range(int(cell_num.row), int(da_tomorrow.row)):
		t = table.range('B'+str(i)+':F'+str(i))
		values_list.append([elem.value for elem in t])
	for i, vals in enumerate(values_list):
		if vals[1][-1] == 'а':
			vals[1] = vals[:-1] + 'ой'
		else: vals[1] = vals[1] + 'а'
		string = '{0}){1} у {2} в аудитории {3} в {4} ({5}) \n'.format(i+1, vals[0], vals[1], vals[2], vals[4], vals[3])
		msg += string
	return msg

def parse_session(query):
	msg = ''
	values = []
	row_vals = True
	i = 2
	if query == 'Зачеты':
		while row_vals:
			row_vals = session.worksheet('Зачеты').row_values(i)
			row_vals = [val for val in row_vals if val]
			values.append(row_vals)
			i += 1
		values = values[:-1]
		for i, val in enumerate(values):
			msg += '{0}){1} {2} в {3}\n'.format(i+1, val[0], val[1], val[2])
	elif query == 'Экзамены':
		while row_vals:
			row_vals = session.worksheet('Экзамены').row_values(i)
			row_vals = [val for val in row_vals if val]
			values.append(row_vals)
			i += 1
		values = values[:-1]
		for i, val in enumerate(values):
			msg += '{0}){1} {2} в {3}\n'.format(i+1, val[0], val[1], val[2])		
	elif query == 'Консультации':
		while row_vals:
			row_vals = session.worksheet('Экзамены').row_values(i)
			row_vals = [val for val in row_vals if val]
			values.append(row_vals)
			i += 1
		values = values[:-1]
		for i, val in enumerate(values):
			msg += '{0}){1} {2} в {3}\n'.format(i+1, val[0], val[3], val[4])
	return msg		


def isEven(today = date.today() + timedelta(days=1), first = config.first_date):
	first = first.split('-')
	first = date(int(first[0]), int(first[1]), int(first[2]))
	cc = today - first
	dd = str(cc).split()[0]
	if round(int(dd)/7) % 2 == 0:
		return False # четная
	else:
		return True  # нечетная

def track(message):
	time = datetime.now().replace(microsecond=0)
	i = 1
	row = True
	while row:
		i += 1
		row = [val for val in logs.row_values(i) if val]

	vals = [message.chat.first_name, message.chat.last_name, message.text, time]
	cell_list = logs.range('A{0}:D{0}'.format(i))
	
	for i in range(len(cell_list)): cell_list[i].value = vals[i]
	logs.update_cells(cell_list)
	bot.send_message(config.creator_id, 'Новые логи!')

def get_logs():
	msg = ''
	i = 1
	rows = []
	row = True
	while row:
		i += 1
		row = [val for val in logs.row_values(i) if val]		
		rows.append(row)

	rows = rows[:-1]
	for row in rows:
		string = '{0} {1}: {2} ({3})\n'.format(row[0], row[1], row[2], row[3])
		msg += string
	return msg

def clean_logs():
	i = 1
	row = True
	while row:
		i += 1
		row = [val for val in logs.row_values(i) if val]

	cell_list = logs.range('A2:D{0}'.format(i))
	for cell in cell_list: cell.value = ''
	logs.update_cells(cell_list)

def set_id(message):
	id_list = [val for val in base.col_values(1) if val][1:]
	if str(message.chat.id) not in id_list:
		ind = len(id_list) + 2
		base.update_acell('A'+str(ind), message.chat.id)

def set_stud_course(message):
	id_list = [val for val in base.col_values(1) if val][1:]
	if str(message.chat.id) in id_list:
		ind = id_list.index(str(message.chat.id)) + 2
		base.update_acell('B'+str(ind), message.text.split()[0])

def set_stud_spec(message):
	id_list = [val for val in base.col_values(1) if val][1:]
	if str(message.chat.id) in id_list:
		ind = id_list.index(str(message.chat.id)) + 2
		base.update_acell('C'+str(ind), message.text.lower())


def get_stud_info(message):
	id_list = [val for val in base.col_values(1) if val][1:]
	ind = id_list.index(str(message.chat.id)) + 2
	course = base.acell('B'+str(ind)).value
	spec = base.acell('C'+str(ind)).value
	return course, spec

server.run(host="0.0.0.0", port=os.environ.get('PORT', 5000))
server = Flask(__name__)
# bot.pooling(non_stop=True)
