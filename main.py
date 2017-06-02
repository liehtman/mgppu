import telebot
import os
import config
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask import Flask, request
from datetime import datetime
from telebot import types

bot = telebot.TeleBot(config.token)
server = Flask(__name__)
scope = ['https://spreadsheets.google.com/feeds']
credentials = ServiceAccountCredentials.from_json_keyfile_name(config.json_keyfile, scope)

gc = gspread.authorize(credentials)
table = gc.open("Расписание").sheet1
session = gc.open("Сессия")
logs = gc.open("Логи МГППУ").sheet1

@bot.message_handler(commands=['cleanlogs'])
def cleanlogs(message):
	clean_logs()
	bot.send_message(message.chat.id, 'Логи очищены')

@bot.message_handler(commands=['showlogs'])
def showlogs(message):
	if message.chat.id == config.creator_id:
		msg = get_logs()
		bot.send_message(message.chat.id, msg)
	else: bot.send_message(message.chat.id, 'Эта функция не для Вас, уважаемый:)')

@bot.message_handler(commands=['getid'])
def get_id(message):
	bot.send_message(message.chat.id, str(message.chat.id))

@bot.message_handler(commands=['start'])
def start(message):
	markup = types.ReplyKeyboardMarkup()
	for course in config.courses:
		markup.add(course)
	bot.send_message(message.chat.id, "Привет. Выбери свой курс", reply_markup = markup)

@bot.message_handler(func=lambda message: True, content_types=['text'])
def reply_message(message):
	if message.text=='Расписание на завтра':
		bot.send_message(message.chat.id, 'Подожди, смотрю...')
		answer = parse_tomorrow()
		bot.send_message(message.chat.id, answer)
	elif message.text in config.ses_queries:
		bot.send_message(message.chat.id, 'Подожди, смотрю...')
		answer = parse_session(message.text)
		bot.send_message(message.chat.id, answer)
	elif message.text in config.courses:        
		markup = types.ReplyKeyboardMarkup()
		for spec in config.specializations:
			markup.add(spec)
		bot.send_message(message.chat.id, 'Выбери направление', reply_markup = markup)
	elif message.text in config.specializations:
		markup = types.ReplyKeyboardMarkup()
		for query in config.main_queries:
			markup.add(query)
		bot.send_message(message.chat.id, 'Что хочешь знать?', reply_markup = markup)
	else: bot.send_message(message.chat.id, 'Юзай кнопки!')
	if message.chat.id != config.creator_id:
		track(message)

@server.route("/bot", methods=['POST'])
def getMessage():
	bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
	return "!", 200

@server.route("/")
def webhook():
	bot.remove_webhook()
	bot.set_webhook(url="https://mgppu.herokuapp.com/bot")
	return "!", 200		

def parse_tomorrow():
	day = datetime.now().isoweekday() + 1
	tomorrow = None
	if day == 5: tomorrow = table.find('EOW')
	elif day in [6, 7]:
		return 'Пляши, завтра выходной!'
	else: tomorrow = table.find(str(day + 1))
	cell_num = table.find(str(day))
	r = cell_num.row
	c = cell_num.col
	tr = tomorrow.row
	tc = tomorrow.col
	values_list = []
	msg = 'Итак, завтра у тебя:\n'
	for i in range(int(r), int(tr)):
		t = table.range('B'+str(i)+':F'+str(i))
		values_list.append([elem.value for elem in t])
	for i in range(len(values_list)):
		msg += '{0}){1} у {2}а в аудитории {3} в {4} ({5}) \n'.format(i+1, values_list[i][0], values_list[i][1], values_list[i][2], values_list[i][4], values_list[i][3])
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
		for i in range(len(values)):
			msg += '{0}){1} {2} в {3}\n'.format(i+1, values[i][0], values[i][1], values[i][2])
	elif query == 'Экзамены':
		while row_vals:
			row_vals = session.worksheet('Экзамены').row_values(i)
			row_vals = [val for val in row_vals if val]
			values.append(row_vals)
			i += 1
		values = values[:-1]
		for i in range(len(values)):
			msg += '{0}){1} {2} в {3}\n'.format(i+1, values[i][0], values[i][1], values[i][2])		
	elif query == 'Консультации':
		while row_vals:
			row_vals = session.worksheet('Экзамены').row_values(i)
			row_vals = [val for val in row_vals if val]
			values.append(row_vals)
			i += 1
		values = values[:-1]
		for i in range(len(values)):
			msg += '{0}){1} {2} в {3}\n'.format(i+1, values[i][0], values[i][3], values[i][4])
	return msg		

def track(message):
	time = datetime.now().replace(microsecond=0)
	i = 1
	row = True
	while row:
		i += 1
		row = [val for val in logs.row_values(i) if val]

	vals = [message.chat.first_name, message.chat.last_name, message.text, time]
	cell_list = logs.range('A{0}:D{0}'.format(i))
	
	for i in range(len(cell_list)):
		cell_list[i].value = vals[i]
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
	for i, row in enumerate(rows):
		string = '{0} {1}: {2} ({3}) \n'.format(row[0], row[1], row[2], row[3])
		msg += string
	return msg

def clean_logs():
	i = 1
	row = True
	while row:
		i += 1
		row = [val for val in logs.row_values(i) if val]

	cell_list = logs.range('A2:D{0}'.format(i))
	for cell in cell_list:
		cell.value = ''
	logs.update_cells(cell_list)

server.run(host="0.0.0.0", port=os.environ.get('PORT', 5000))
server = Flask(__name__)