import os
import telebot
import config
import gspread
import time, threading
from flask import Flask, request
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, date, timedelta
from datetime import time as d_time
from telebot import types
from student import Student

bot = telebot.TeleBot(config.token)
server = Flask(__name__)
scope = ['https://spreadsheets.google.com/feeds']
credentials = ServiceAccountCredentials.from_json_keyfile_name(config.json_keyfile, scope)
gc = gspread.authorize(credentials)
base = gc.open("Студенты").sheet1
logs = gc.open("Логи МГППУ").sheet1

@bot.message_handler(commands=['start'])
def start(message):
	set_id(message)
	markup = types.ReplyKeyboardMarkup()
	if message.chat.id not in config.privileged_id:
		for course in config.courses:
			markup.add(course)
	else:
		for group in config.tables:
			markup.add(group) 
	bot.send_message(message.chat.id, "Привет. Выбери свой курс", reply_markup = markup)
	if message.chat.id != config.creator_id: track(message)

@bot.message_handler(commands=['announce'])
def announce(message):
	if message.chat.id == config.creator_id:
		msg = 'Привет! Появилось расписание для всех групп!'
		try: update_news(msg)
		except: bot.send_message(config.creator_id, 'Что-то пошло не так')
		finally: bot.send_message(config.creator_id, 'Оповещения отправлены')
	else: bot.send_message(message.chat.id, 'Эта функция не для Вас, уважаемый:)')

@bot.message_handler(commands=['iseven'])
def even_or_odd(message):
	if isEven(): bot.send_message(message.chat.id, 'Сегодня *четная* неделя', parse_mode = "Markdown")
	else: bot.send_message(message.chat.id, 'Сегодня *нечетная* неделя', parse_mode = "Markdown")
	if message.chat.id != config.creator_id: track(message)

@bot.message_handler(commands=['cleanlogs'])
def cleanlogs(message):
	if message.chat.id == config.creator_id:
		clean_logs()
		bot.send_message(message.chat.id, 'Логи очищены')
	else: bot.send_message(message.chat.id, 'Эта функция не для Вас, уважаемый:)')
	if message.chat.id != config.creator_id: track(message)

@bot.message_handler(commands=['showlogs'])
def showlogs(message):
	if message.chat.id == config.creator_id:
		log = get_logs() 
		if log: bot.send_message(message.chat.id, log)
		else: bot.send_message(message.chat.id, 'Логи пусты')
	else: 
		bot.send_message(message.chat.id, 'Эта функция не для Вас, уважаемый:)')
		track(message)

@bot.message_handler(commands=['getid'])
def get_id(message):
	bot.send_message(message.chat.id, str(message.chat.id))
	if message.chat.id != config.creator_id: track(message)

@bot.message_handler(commands=['help'])
def help(message):
	bot.send_message(message.chat.id, 'Помощи нет.')
	if message.chat.id != config.creator_id: track(message)

@bot.message_handler(func=lambda message: True, content_types=['text'])
def main_reply(message):
	if message.text=='Расписание на завтра':
		course_num, specialization = get_stud_info(message)
		table_name = course_num + ' курс ' + specialization
		bot.send_message(message.chat.id, 'Подожди, смотрю...')
		try:
			answer = parse_tomorrow(gc.open(table_name))
			bot.send_message(message.chat.id, answer, parse_mode = "Markdown")
		except:
			bot.send_message(message.chat.id, 'Упс... Что-то пошло не так:(')

	elif message.text == 'Расписание на сегодня':
		course_num, specialization = get_stud_info(message)
		table_name = course_num + ' курс ' + specialization
		bot.send_message(message.chat.id, 'Подожди, смотрю...')
		try:
			answer = parse_today(gc.open(table_name))
			bot.send_message(message.chat.id, answer, parse_mode = "Markdown")
		except:
			bot.send_message(message.chat.id, 'Упс... Что-то пошло не так:(')		

	elif message.text in config.ses_queries:
		bot.send_message(message.chat.id, 'Расписания сессии пока нет')
		# bot.send_message(message.chat.id, 'Подожди, смотрю...')
		# course_num, specialization = get_stud_info(message)
		# table_name = 'Сессия {0} {1}'.format(course_num, specialization)
		# try:
		# 	answer = parse_session(gc.open(table_name), message.text)
		# 	bot.send_message(message.chat.id, answer)
		# except:
		# 	bot.send_message(message.chat.id, 'Упс... Что-то пошло не так:(')

	elif message.text in config.courses:
		set_stud_course(message)
		course_num, specialization = get_stud_info(message)
		table_name = course_num + ' курс ' + specialization
		markup = types.ReplyKeyboardMarkup()
		for spec in config.specializations: markup.add(spec)
		bot.send_message(message.chat.id, 'Выбери направление', reply_markup = markup)
	
	elif message.text in config.specializations or message.text == 'В меню':
		if message.text in config.specializations:
			set_stud_spec(message)
		course_num, specialization = get_stud_info(message)
		table_name = course_num + ' курс ' + specialization
		markup = types.ReplyKeyboardMarkup(resize_keyboard = True)
		markup.row(config.main_queries[0], config.main_queries[1])
		markup.row(config.main_queries[2], config.main_queries[3])
		markup.row(config.main_queries[4])
		markup.row(config.main_queries[5])
		markup.row(config.main_queries[6])
		markup.row(config.main_queries[7])
		markup.row('Назад')
		bot.send_message(message.chat.id, 'Что хочешь знать?', reply_markup = markup)

	elif message.text == 'Назад': start(message)

	elif message.text == 'Четная неделя':
		markup = types.ReplyKeyboardMarkup(resize_keyboard = True)
		markup.row(config.days_even[0])
		markup.row(config.days_even[1]) 
		markup.row(config.days_even[2])
		markup.row(config.days_even[3])
		markup.row(config.days_even[4])
		markup.row(config.days_even[5])
		markup.row('В меню')
		bot.send_message(message.chat.id, 'Выбери день', reply_markup = markup)

	elif message.text == 'Нечетная неделя':
		markup = types.ReplyKeyboardMarkup(resize_keyboard = True)
		markup.row(config.days_odd[0])
		markup.row(config.days_odd[1]) 
		markup.row(config.days_odd[2])
		markup.row(config.days_odd[3])
		markup.row(config.days_odd[4])
		markup.row(config.days_odd[5])
		markup.row('В меню')
		bot.send_message(message.chat.id, 'Выбери день', reply_markup = markup)

	elif message.text in config.days_even:  # Четная
		bot.send_message(message.chat.id, 'Подожди, смотрю...')
		msg = ''
		course_num, specialization = get_stud_info(message)
		table_name = course_num + ' курс ' + specialization
		day_name = message.text.split(' ')[0]
		parsing_result = parse_any_day(gc.open(table_name).worksheet('Четная'), day_name)
		if parsing_result != 'Это выходной':
			msg = 'Расписание на {0}:\n'.format(day_name.lower())
		msg += parsing_result
		bot.send_message(message.chat.id, msg, parse_mode = "Markdown")

	elif message.text in config.days_odd:  # Нечетная
		bot.send_message(message.chat.id, 'Подожди, смотрю...')
		msg = ''
		course_num, specialization = get_stud_info(message)
		table_name = course_num + ' курс ' + specialization
		day_name = message.text.split(' ')[0]
		parsing_result = parse_any_day(gc.open(table_name).worksheet('Нечетная'), day_name)
		if parsing_result != 'Это выходной': 
			msg = 'Расписание на {0}:\n'.format(day_name.lower())
		msg += parsing_result
		bot.send_message(message.chat.id, msg, parse_mode = "Markdown")

	elif message.text == 'Найти преподавателя':
		bot.send_message(message.chat.id, 'Введи его фамилию, выделив ее в звездочки. Например, *Иванов*')

	elif message.text[0] == '*' and message.text[-1] == '*':
		bot.send_message(message.chat.id, 'Подожди, ищу...')
		name = message.text[1:-1]
		msg = search_lecturer(name)
		bot.send_message(message.chat.id, msg, parse_mode = "Markdown")

	else: bot.send_message(message.chat.id, 'Юзай кнопки!')
	
	if message.chat.id != config.creator_id: track(message)

def parse(table, start, end):
	values_list = []
	msg = ''
	for i in range(int(start.row), int(end.row)):
		t = table.range('B'+str(i)+':F'+str(i))
		values_list.append([elem.value for elem in t])
	for i, vals in enumerate(values_list):
		if ',' in vals[1]:
			vals[1] = vals[1].split(',')
			vals[1][0] = decline_name(vals[1][0])
			vals[1][1] = decline_name(vals[1][1])
			vals[1] = vals[1][0] + '/' + vals[1][1][1:]
		else: vals[1] = decline_name(vals[1])
		string = '{0})_{1}_ у {2} в аудитории *{3}* в *{4}* ({5}) \n'.format(i+1, vals[0], vals[1], vals[2], vals[4], vals[3])
		msg += string
	return msg

def decline_name(name):
	if name[-1] == 'а':
		name = list(name)
		name[-1] = 'ой'
		name = ''.join(name)
	elif name[-1] == 'й':
		name = list(name[:-2])
		name[-1] = 'ого'
		name = ''.join(name)
	else: 
		name = list(name)
		name.append('а')
		name = ''.join(name)
	return name

def parse_any_day(table, day):
	stud_days = [val for val in table.col_values(1) if val]
	d = {
			'Понедельник':'1',
			'Вторник':'2',
			'Среда':'3',
			'Четверг':'4',
			'Пятница':'5',
			'Суббота':'6'
		}

	def check(D):
		if day in D.keys():
			if D[day] not in stud_days:
				return 'Это выходной'
			else:
				start = table.find(D[day])
				end = table.find(stud_days[stud_days.index(D[day]) + 1])
				return parse(table, start, end)
		else: return 'Упс... Что-то пошло не так :('
	
	return check(d)
	
def parse_today(table):
	if isEven(): table = table.worksheet('Четная')
	else: table = table.worksheet('Нечетная')
	today = str(datetime.now().isoweekday()) # Сегодня
	tomorrow = None
	stud_days = [val for val in table.col_values(1) if val]
	if today not in stud_days: return 'Сегодня выходной!'
	else: tomorrow = table.find(stud_days[stud_days.index(today) + 1])
	cell_num = table.find(today)
	msg = 'Итак, сегодня у тебя:\n'
	return msg + parse(table, cell_num, tomorrow)
	
def parse_tomorrow(table):
	if isEven(): table = table.worksheet('Четная')
	else: table = table.worksheet('Нечетная')
	tomorrow = str((datetime.now() + timedelta(days=1)).isoweekday())  	# ЗАВТРА
	da_tomorrow = None    							 				# ПОСЛЕЗАВТРА
	stud_days = [val for val in table.col_values(1) if val]
	if tomorrow not in stud_days: return 'Завтра выходной'
	else: da_tomorrow = table.find(stud_days[stud_days.index(str(tomorrow)) + 1])
	cell_num = table.find(tomorrow)
	msg = 'Итак, завтра у тебя:\n'
	return msg + parse(table, cell_num, da_tomorrow)

def parse_session(table, query):
	msg, values = '', []
	i, row_vals = 2, True
	if query == 'Зачеты':
		while row_vals:
			row_vals = [val for val in table.worksheet('Зачеты').row_values(i) if val]
			values.append(row_vals)
			i += 1
		values = values[:-1]
		for i, val in enumerate(values):
			msg += '{0}){1} {2} в {3} в аудитории {4}\n'.format(i+1, val[0], val[1], val[2], val[3])
	elif query == 'Экзамены':
		while row_vals:
			row_vals = [val for val in table.worksheet('Экзамены').row_values(i) if val]
			values.append(row_vals)
			i += 1
		values = values[:-1]
		for i, val in enumerate(values):
			msg += '{0}){1} {2} в {3} в аудитории {4}\n'.format(i+1, val[0], val[1], val[2], val[3])		
	elif query == 'Консультации':
		while row_vals:
			row_vals = [val for val in table.worksheet('Экзамены').row_values(i) if val]
			values.append(row_vals)
			i += 1
		values = values[:-1]
		for i, val in enumerate(values):
			msg += '{0}){1} {2} в {3} в аудитории {4}\n'.format(i+1, val[0], val[4], val[5], val[3])
	return msg

def search_lecturer(name):
	tables = [gc.open(table) for table in config.tables]
	days, places, times = [], [], []
	D = {
			'1':'понедельник',
			'2':'вторник',
			'3':'среда',
			'4':'четверг',
			'5':'пятница',
			'6':'суббота'
		}

	find_time  = lambda sheet,cell: sheet.acell('F' + str(cell.row)).value
	find_place = lambda sheet,cell: sheet.acell('D' + str(cell.row)).value

	def find_day(sheet, cell):
		i = cell.row
		day = None
		while not day:
			day = sheet.acell('A' + str(i)).value
			i -= 1
		if sheet.title == 'Четная': day += 'even'
		elif sheet.title == 'Нечетная': day += 'odd'
		return day

	for table in tables:
		for sheet in table.worksheets():
			try:
				cells = sheet.findall(name)
				for i, cell in enumerate(cells):
					days.append(find_day(sheet, cell))
					times.append(find_time(sheet, cell))
					places.append(find_place(sheet, cell))
			except: continue
	if days == [] or times == []:
		return 'Что-то я не могу найти этого преподавателя :('

	T = set(list(zip(places, times, days)))
	T = sorted(T, key=lambda x: x[2])
	msg = ''
	for tup in T:
		if 'even' in tup[2]:
			msg += '{0} бывает в аудитории *{1}* в *{2}* в {3} на четной неделе.\n'.format(name, tup[0], tup[1], D[str(tup[2][0])])
		elif 'odd' in tup[2]:
			msg += '{0} бывает в аудитории *{1}* в *{2}* в {3} на нечетной неделе.\n'.format(name, tup[0], tup[1], D[str(tup[2][0])])
	return msg

def isEven(today = date.today() + timedelta(days=1), first = config.first_date):
	first = first.split('-')
	first = date(int(first[0]), int(first[1]), int(first[2]))
	cc = today - first
	dd = str(cc).split()[0]
	if round(int(dd)/7) % 2 == 0: return False  # четная
	else: return True  							# нечетная

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

def get_students_array():
	IDs = [val for val in base.col_values(1) if val]
	courses = [val for val in base.col_values(2) if val]
	specs = [val for val in base.col_values(3) if val]
	studs = [Student(IDs[i], courses[i], specs[i]) for i in range(len(IDs))]
	return studs

def get_users_id():
	return [val for val in base.col_values(1)[1:] if val]

def check_updates():
	tables = [gc.open(name) for name in config.tables]
	now = datetime.now()
	count = datetime.combine(date.min, d_time(1, 0)) - datetime.min
	for table in tables:
		upd = table.updated
		upd = datetime.strptime(upd, '%Y-%m-%dT%H:%M:%S.%fZ') + timedelta(hours=3)
		if (now - upd) < count:
			bot.send_message(config.creator_id, 'Changes!')
			# name = table.title.split(' ')
			# course, spec = name[0], name[2]
			# studs = get_students_array()
			# for stud in studs:
			# 	if stud.course == course and stud.spec == spec:
			# 		bot.send_message(stud.id, 'В расписании что-то поменялось.')
	threading.Timer(3600, check_updates).start()

def track(message):
	time = datetime.now().replace(microsecond=0)
	i, row = 1, True
	while row:
		i += 1
		row = [val for val in logs.row_values(i) if val]
	vals = [message.chat.first_name, message.chat.last_name, message.text, time]
	cell_list = logs.range('A{0}:D{0}'.format(i))
	
	for i in range(len(cell_list)): cell_list[i].value = vals[i]
	logs.update_cells(cell_list)

def get_logs():
	msg, i = '', 1
	rows, row = [], True
	while row:
		i += 1
		row = [val for val in logs.row_values(i) if val]		
		rows.append(row)
	for row in rows[:-1]:
		string = '{0} {1}: {2} ({3})\n'.format(row[0], row[1], row[2], row[3])
		msg += string
	return msg

def clean_logs():
	i, row = 1, True
	while row:
		i += 1
		row = [val for val in logs.row_values(i) if val]
	cell_list = logs.range('A2:D{0}'.format(i))
	for cell in cell_list: cell.value = ''
	logs.update_cells(cell_list)

def update_news(msg):
	users = get_users_id()
	for user in users:
		time.sleep(1)
		try: bot.send_message(int(user), msg)
		except: bot.send_message(config.creator_id, user + ' не получил уведомление')

def privileged_announce(course, spec, message):
	students = [st for st in get_students_array() if st.spec == spec and st.course == course]
	for student in students:
		time.sleep(1)
		try:
			bot.send_message(int(student.id), message.text)
		except:
			bot.send_message(message.chat.id, student.id + ' не получил уведомление')
		finally:
			bot.send_message(message.chat.id, 'Уведомления отправлены')

@server.route("/bot", methods=['POST'])
def getMessage():
	bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
	return "!", 200

@server.route("/")
def webhook():
	bot.remove_webhook()
	bot.set_webhook(url="https://mgppu.herokuapp.com/bot")
	return "!", 200		

server.run(host="0.0.0.0", port=os.environ.get('PORT', 5000))
server = Flask(__name__)