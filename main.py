import os
import config
import gspread
import time, threading
from oauth2client.service_account import ServiceAccountCredentials
from student import Student

scope = ['https://spreadsheets.google.com/feeds']
credentials = ServiceAccountCredentials.from_json_keyfile_name(config.json_keyfile, scope)
gc = gspread.authorize(credentials)
base = gc.open("Студенты").sheet1
logs = gc.open("Логи МГППУ").sheet1

def get_logs():
	msg, i = '', 1
	rows, row = [], True
	while row:
		i += 1
		try:
			row = [val.encode('utf-8') for val in logs.row_values(i) if val]
			print(row)
		except: continue
		rows.append(row)
	for row in reversed(rows[-15:-1]):
		string = '\[_{0}_] *{1} {2}*: {3} ({4})\n'.format(*row)
		msg += string
	return msg
print(get_logs())