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

@bot.message_handler(commands=['announce'])
def announce(message):
	ad = 'Привет. Теперь я знаю расписание для всех групп. Расскажи друзьям!:)'
	if message.chat.id == config.creator_id:
		try: update_news(ad)
		except: bot.send_message(config.creator_id, 'Что-то пошло не так')
		finally: bot.send_message(config.creator_id, 'Оповещения отправлены')
	else:
		track(message)
		bot.send_message(message.chat.id, 'Эта функция только для разработчика.')

@bot.message_handler(commands=['iseven'])
def even_or_odd(message):
	if message.chat.id != config.creator_id: track(message)
	if isEven(): bot.send_message(message.chat.id, 'Сегодня *четная* неделя', parse_mode = "Markdown")
	else: bot.send_message(message.chat.id, 'Сегодня *нечетная* неделя', parse_mode = "Markdown")

@bot.message_handler(commands=['cleanlogs'])
def cleanlogs(message):
	if message.chat.id == config.creator_id:
		clean_logs()
		bot.send_message(message.chat.id, 'Логи очищены')
	else:
		track(message) 
		bot.send_message(message.chat.id, 'Эта функция только для разработчика.')

@bot.message_handler(commands=['showlogs'])
def showlogs(message):
	if message.chat.id == config.creator_id:
		log = get_logs()
		if log: bot.send_message(message.chat.id, log, parse_mode = "Markdown")
		else: bot.send_message(message.chat.id, 'Логи пусты')
	else:
		track(message)
		bot.send_message(message.chat.id, 'Эта функция только для разработчика.')

@bot.message_handler(commands=['getid'])
def get_id(message):
	if message.chat.id != config.creator_id: track(message)
	bot.send_message(message.chat.id, str(message.chat.id))

@bot.message_handler(commands=['help'])
def help(message):
	if message.chat.id != config.creator_id: track(message)
	bot.send_message(message.chat.id, 'Помощи нет.')

@bot.message_handler(commands=['start'])
def start(message):
	set_id(message)
	markup = types.ReplyKeyboardMarkup()
	if message.chat.id not in config.privileged_id:
		for course in config.courses:
			markup.add(course)
		markup.add('Магистратура')
		msg = bot.send_message(message.chat.id, "Привет. Выбери свой курс", reply_markup = markup)
		bot.register_next_step_handler(msg, process_course_pick)
	else:
		markup.add('Сделать рассылку...')
		bot.send_message(message.chat.id, 'Здравствуйте!', reply_markup = markup)
	if message.chat.id != config.creator_id: track(message)

def process_course_pick(message):
	markup = types.ReplyKeyboardMarkup()
	if message.text == 'Магистратура':
		markup.add('1 курс')
		markup.add('2 курс')
		set_stud_spec(message)
		msg = bot.send_message(message.chat.id, 'Выбери курс', reply_markup = markup)
	else:
		set_stud_course(message)
		course_num, specialization = get_stud_info(message)
		for spec in config.specializations: markup.add(spec)
		msg = bot.send_message(message.chat.id, 'Выбери направление', reply_markup = markup)		
	bot.register_next_step_handler(msg, process_spec_pick)

def process_spec_pick(message):
	markup = types.ReplyKeyboardMarkup(resize_keyboard = True)
	markup.row(config.main_queries[0], config.main_queries[1])
	if message.text == '1 курс' or message.text == '2 курс':
		set_stud_course(message)
		markup.row('Неделя')
	else:
		set_stud_spec(message) 
		markup.row(config.main_queries[2], config.main_queries[3])
	markup.row(config.main_queries[4])
	markup.row(config.main_queries[5])
	markup.row(config.main_queries[6])
	markup.row('Назад')

	course_num, specialization = get_stud_info(message)
	bot.send_message(message.chat.id, 'Что хочешь знать?', reply_markup = markup)


@bot.message_handler(func=lambda message: message.chat.id in config.privileged_id and message.text == 'Сделать рассылку...', content_types=['text'])
def do_spam(message):
	markup = types.ReplyKeyboardMarkup()
	for table in config.tables:
		markup.add(table)
	markup.add('Назад')
	msg = bot.send_message(message.chat.id, 'Выберите группу', reply_markup = markup)
	if message.chat.id != config.creator_id: track(message)
	bot.register_next_step_handler(msg, privileged_announce)

def privileged_announce(message):
	splitted_mes = message.text.split()
	course, spec = int(splitted_mes[0]), splitted_mes[2]
	msg = bot.send_message(message.chat.id, "Введите сообщение, которое нужно разослать")

	if   course == 4 and spec == 'математики':  bot.register_next_step_handler(msg, announce_4_mat)
	elif course == 4 and spec == 'информатики': bot.register_next_step_handler(msg, announce_4_inf)
	elif course == 4 and spec == 'режиссеры':   bot.register_next_step_handler(msg, announce_4_prod)
	elif course == 3 and spec == 'математики':  bot.register_next_step_handler(msg, announce_3_mat)
	elif course == 3 and spec == 'информатики': bot.register_next_step_handler(msg, announce_3_inf)
	elif course == 3 and spec == 'режиссеры':   bot.register_next_step_handler(msg, announce_3_prod)
	elif course == 2 and spec == 'математики':  bot.register_next_step_handler(msg, announce_2_mat)
	elif course == 2 and spec == 'информатики': bot.register_next_step_handler(msg, announce_2_inf)
	elif course == 2 and spec == 'режиссеры':   bot.register_next_step_handler(msg, announce_2_prod)
	elif course == 1 and spec == 'математики':  bot.register_next_step_handler(msg, announce_1_mat)
	elif course == 1 and spec == 'информатики': bot.register_next_step_handler(msg, announce_1_inf)
	elif course == 1 and spec == 'режиссеры':   bot.register_next_step_handler(msg, announce_1_prod)

	announce_1_inf  = lambda message: sample_announce(message, 1, 'информатики')
	announce_2_inf  = lambda message: sample_announce(message, 2, 'информатики')
	announce_3_inf  = lambda message: sample_announce(message, 3, 'информатики')
	announce_4_inf  = lambda message: sample_announce(message, 4, 'информатики')
	announce_1_mat  = lambda message: sample_announce(message, 1, 'математики')
	announce_2_mat  = lambda message: sample_announce(message, 2, 'математики')
	announce_3_mat  = lambda message: sample_announce(message, 3, 'математики')
	announce_4_mat  = lambda message: sample_announce(message, 4, 'математики')
	announce_1_prod = lambda message: sample_announce(message, 1, 'режиссеры')
	announce_2_prod = lambda message: sample_announce(message, 2, 'режиссеры')
	announce_3_prod = lambda message: sample_announce(message, 3, 'режиссеры')
	announce_4_prod = lambda message: sample_announce(message, 4, 'режиссеры')

def sample_announce(message, course, spec):
	bot.send_message(message.chat.id, 'Начинаю рассылку...')
	students = [st for st in get_students_array() if st.course == str(course) and st.spec == spec]
	msg = '*Внимание, сообщение от деканата:*\n\n' + message.text
	for student in students:
		time.sleep(1)
		try: bot.send_message(int(student.id), msg, parse_mode = "Markdown")
		except: bot.send_message(message.chat.id, '{0} не получил уведомление'.format(student.id))
	bot.send_message(message.chat.id, 'Уведомления отправлены')

def get_students_array():
	IDs = [val for val in base.col_values(1) if val]
	courses = [val for val in base.col_values(2)]
	specs = [val for val in base.col_values(3)]
	studs = [Student(IDs[i], courses[i], specs[i]) for i in range(len(IDs))]
	return studs

@bot.message_handler(func=lambda message: message.text == 'Расписание на завтра', content_types=['text'])
def schedule_tomorrow(message):
	course_num, specialization = get_stud_info(message)
	table_name = course_num + ' курс ' + specialization
	bot.send_message(message.chat.id, 'Подожди, смотрю...')
	try:
		answer = parse_tomorrow(gc.open(table_name))
		bot.send_message(message.chat.id, answer, parse_mode = "Markdown")
	except:
		bot.send_message(message.chat.id, 'Упс... Что-то пошло не так:(')
	if message.chat.id != config.creator_id: track(message)

def parse_tomorrow(table):
	try:
		if isEven(): table = table.worksheet('Четная')
		else: table = table.worksheet('Нечетная')
	except: table = table.sheet1
	tomorrow = str((datetime.now() + timedelta(days=1)).isoweekday())  	# ЗАВТРА
	da_tomorrow = None    							 				# ПОСЛЕЗАВТРА
	stud_days = [val for val in table.col_values(1) if val]
	if tomorrow not in stud_days: return 'Завтра выходной'
	else: da_tomorrow = table.find(stud_days[stud_days.index(str(tomorrow)) + 1])
	cell_num = table.find(tomorrow)
	msg = 'Итак, завтра у тебя:\n'
	return msg + parse(table, cell_num, da_tomorrow)

@bot.message_handler(func=lambda message: message.text == 'Расписание на сегодня', content_types=['text'])
def schedule_today(message):
	course_num, specialization = get_stud_info(message)
	table_name = course_num + ' курс ' + specialization
	bot.send_message(message.chat.id, 'Подожди, смотрю...')
	try:
		answer = parse_today(gc.open(table_name))
		bot.send_message(message.chat.id, answer, parse_mode = "Markdown")
	except:
		bot.send_message(message.chat.id, 'Упс... Что-то пошло не так:(')
	if message.chat.id != config.creator_id: track(message)

def parse_today(table):
	try:
		if isEven(): table = table.worksheet('Четная')
		else: table = table.worksheet('Нечетная')
	except: table = table.sheet1
	today = str(datetime.now().isoweekday()) # Сегодня
	tomorrow = None
	stud_days = [val for val in table.col_values(1) if val]
	if today not in stud_days: return 'Сегодня выходной!'
	else: tomorrow = table.find(stud_days[stud_days.index(today) + 1])
	cell_num = table.find(today)
	msg = 'Итак, сегодня у тебя:\n'
	return msg + parse(table, cell_num, tomorrow)

@bot.message_handler(func=lambda message: message.text=='Назад', content_types=['text'])
def back(message):
	start(message)

@bot.message_handler(func=lambda message: message.text=='Четная неделя', content_types=['text'])
def even_week(message):
	markup = types.ReplyKeyboardMarkup(resize_keyboard = True)
	for day in config.days_even:
		markup.row(day)
	markup.row('В меню')
	msg = bot.send_message(message.chat.id, 'Выбери день', reply_markup = markup)
	if message.chat.id != config.creator_id: track(message)
	bot.register_next_step_handler(msg, parse_even_or_odd_day)

@bot.message_handler(func=lambda message: message.text=='Нечетная неделя', content_types=['text'])
def odd_week(message):
	markup = types.ReplyKeyboardMarkup(resize_keyboard = True)
	for day in config.days_odd:
		markup.row(day)
	markup.row('В меню')
	msg = bot.send_message(message.chat.id, 'Выбери день', reply_markup = markup)
	if message.chat.id != config.creator_id: track(message)


@bot.message_handler(func=lambda message: message.text == 'Неделя', content_types=['text'])
def any_day(message):
	markup = types.ReplyKeyboardMarkup(resize_keyboard = True)
	for day in config.days:
		markup.row(day)
	markup.row('В меню')
	msg = bot.send_message(message.chat.id, 'Выбери день', reply_markup = markup)
	if message.chat.id != config.creator_id: track(message)


@bot.message_handler(func=lambda message: message.text in config.days, content_types=['text'])
def days(message):
	bot.send_message(message.chat.id, 'Подожди, смотрю...')
	msg = ''
	course_num, specialization = get_stud_info(message)
	table_name = course_num + ' курс ' + specialization
	day_name = message.text.split(' ')[0]
	parsing_result = parse_any_day(gc.open(table_name).sheet1, day_name)
	if parsing_result != 'Это выходной':
		msg = 'Расписание на {0}:\n'.format(day_name.lower())
	msg += parsing_result
	bot.send_message(message.chat.id, msg, parse_mode = "Markdown")
	if message.chat.id != config.creator_id: track(message)

@bot.message_handler(func=lambda message: message.text in config.days_odd, content_types=['text'])
def odd_days(message):
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
	if message.chat.id != config.creator_id: track(message)

@bot.message_handler(func=lambda message: message.text in config.days_even, content_types=['text'])
def even_days(message):
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
	if message.chat.id != config.creator_id: track(message)

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

def parse(table, start, end):
	hasNumbers = lambda inputString: any(char.isdigit() for char in inputString)
	values_list = []
	msg = ''
	for i in range(int(start.row), int(end.row)):
		t = table.range('B'+str(i)+':F'+str(i))
		values_list.append([elem.value for elem in t])
	indiv_days = []
	for i, vals in enumerate(values_list):
		f = False
		if hasNumbers(vals[0]):
			f = True
			indiv_days, name = get_individual_days(vals[0])
			vals[0] = name
			mess = 'только '
			for v in indiv_days:
				for j in v[0]:
					mess += str(j) + ', '
				mess = (mess[:-2] + ' ' + config.months[str(v[1])] + ', ')
			values_list[i].append(mess[:-2]+'.')
		if ',' in vals[1]:
			vals[1] = vals[1].split(',')
			vals[1][0] = decline_name(vals[1][0])
			vals[1][1] = decline_name(vals[1][1])
			vals[1] = vals[1][0] + '/' + vals[1][1][1:]
		else: vals[1] = decline_name(vals[1])
		if (f):
			string = '{0})_{1}_ у {2} в аудитории *{3}* в *{5}* ({4}) (*{6}*)\n'.format(i+1, *vals)
		else: string = '{0})_{1}_ у {2} в аудитории *{3}* в *{5}* ({4})\n'.format(i+1, *vals)
		msg += string
	return msg

def get_individual_days(string):
	splitted = string.split(' ')
	name = ' '.join(splitted[1:])
	months, days = [], []
	for part in splitted[0].split(';'):
		dash_index = part.find('-')
		months.append(part[dash_index + 1:])
		days.append(part[:dash_index].split(','))
	zipped = list(zip(days, months))
	return zipped, name

def decline_name(name):
	if name[-1] == 'а': name = name[:-1] + 'ой'
	elif name[-1] == 'й': name = name[:-2] + 'ого'
	elif name[-1] == 'ь': name = name[:-1] + 'я'
	elif name[-1] == 'о': name = name
	else: name += 'а'
	return name

@bot.message_handler(func=lambda message: message.text == 'Найти преподавателя', content_types=['text'])
def find_lecturer(message):
	msg = bot.send_message(message.chat.id, 'Введи его фамилию с большой буквы')
	if message.chat.id != config.creator_id: track(message)
	bot.register_next_step_handler(msg, search_lecturer)

def search_lecturer(message):
	bot.send_message(message.chat.id, 'Подожди, ищу...')
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
				cells = sheet.findall(message.text)
				for i, cell in enumerate(cells):
					days.append(find_day(sheet, cell))
					times.append(find_time(sheet, cell))
					places.append(find_place(sheet, cell))
			except: continue
	if days == [] or times == []:
		return 'Что-то я не могу найти этого преподавателя :('

	T = set(zip(places, times, days))
	T = sorted(T, key = lambda x: x[2])
	msg = ''
	for tup in T:
		if 'even' in tup[2]:
			msg += '{0} бывает в аудитории *{1}* в *{2}* в {3} на четной неделе.\n'.format(message.text, tup[0], tup[1], D[str(tup[2][0])])
		elif 'odd' in tup[2]:
			msg += '{0} бывает в аудитории *{1}* в *{2}* в {3} на нечетной неделе.\n'.format(message.text, tup[0], tup[1], D[str(tup[2][0])])
	bot.send_message(message.chat.id, msg, parse_mode = "Markdown")

@bot.message_handler(func=lambda message: message.text == 'В меню', content_types=['text'])
def to_menu(message):
	course_num, specialization = get_stud_info(message)
	table_name = course_num + ' курс ' + specialization
	markup = types.ReplyKeyboardMarkup(resize_keyboard = True)
	markup.row(config.main_queries[0], config.main_queries[1])
	if specialization != 'магистратура':
		markup.row(config.main_queries[2], config.main_queries[3])
	else: markup.row('Неделя')
	markup.row(config.main_queries[4])
	markup.row(config.main_queries[5])
	markup.row(config.main_queries[6])
	markup.row('Назад')
	bot.send_message(message.chat.id, 'Что хочешь знать?', reply_markup = markup)
	if message.chat.id != config.creator_id: track(message)

@bot.message_handler(func=lambda message: message.text == 'Сессия', content_types=['text'])
def session(message):
	markup = types.ReplyKeyboardMarkup(resize_keyboard = True)
	for query in config.ses_queries:
		markup.add(query)
	markup.add('В меню')
	bot.send_message(message.chat.id, 'Что хочешь знать?', reply_markup = markup)
	if message.chat.id != config.creator_id: track(message)

@bot.message_handler(func=lambda message: message.text in config.ses_queries, content_types=['text'])
def session_query(message):
	if message.chat.id != config.creator_id: track(message)
	bot.send_message(message.chat.id, 'Расписания сессии пока нет')
	# bot.send_message(message.chat.id, 'Подожди, смотрю...')
	# course_num, specialization = get_stud_info(message)
	# table_name = 'Сессия {0} {1}'.format(course_num, specialization)
	# try:
	# 	answer = parse_session(gc.open(table_name), message.text)
	# 	bot.send_message(message.chat.id, answer)
	# except:
		# bot.send_message(message.chat.id, 'Упс... Что-то пошло не так:(')

@bot.message_handler(func=lambda message: message.text == 'Какая сегодня неделя?', content_types=['text'])
def whats_week(message):
	even_or_odd(message)

@bot.message_handler(func=lambda message: True, content_types = ['text'])
def default(message):
	# bot.send_message(message.chat.id, 'Используй кнопки')  # TODO: всегда срабатывает
	if message.chat.id != config.creator_id: track(message)

def parse_session(table, query):
	msg, values = '', []
	i, row_vals = 2, True
	if query == 'Зачеты':
		while row_vals:
			values.append([val for val in table.worksheet('Зачеты').row_values(i) if va])
			i += 1
		values.pop()
		for i, val in enumerate(values):
			msg += '{0}){1} {2} в {3} в аудитории {4}\n'.format(i+1, *val)
	elif query == 'Экзамены':
		while row_vals:
			values.append([val for val in table.worksheet('Экзамены').row_values(i) if val])
			i += 1
		values.pop()
		for i, val in enumerate(values):
			msg += '{0}){1} {2} в {3} в аудитории {4}\n'.format(i+1, *val)		
	elif query == 'Консультации':
		while row_vals:
			values.append([val for val in table.worksheet('Экзамены').row_values(i) if val])
			i += 1
		values.pop()
		for i, val in enumerate(values):
			msg += '{0}){1} {2} в {3} в аудитории {4}\n'.format(i+1, *val)
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
		base.update_acell('D'+str(ind), message.chat.first_name +' '.join(message.chat.last_name))

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
	threading.Timer(3600, check_updates).start()

def track(message):
	time = datetime.now().replace(microsecond=0)
	i, row = 1, True
	while row:
		i += 1
		row = [val for val in logs.row_values(i) if val]
	vals = [message.chat.id, message.chat.first_name, message.chat.last_name, message.text, time]
	cell_list = logs.range('A{0}:E{0}'.format(i))
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
		string = '\[_{0}_] *{1} {2}*: {3} ({4})\n'.format(*row)
		msg += string
	return msg

def clean_logs():
	i, row = 1, True
	while row:
		i += 1
		row = [val for val in logs.row_values(i) if val]
	cell_list = logs.range('A2:F{0}'.format(i))
	for cell in cell_list: cell.value = ''
	logs.update_cells(cell_list)

def update_news(msg):
	users = get_users_id()
	for user in users:
		time.sleep(1)
		try: bot.send_message(int(user), msg)
		except: bot.send_message(config.creator_id, user + ' не получил уведомление')

@server.route("/bot", methods=['POST'])
def getMessage():
	bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
	return "!", 200

@server.route("/")
def webhook():
	bot.remove_webhook()
	bot.set_webhook(url="https://mgppu.herokuapp.com/bot")
	return "!", 200

if __name__ == '__main__':
	server.run(host="0.0.0.0", port=os.environ.get('PORT', 5000))
	server = Flask(__name__)