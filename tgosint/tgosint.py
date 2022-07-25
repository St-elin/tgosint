import configparser
import json
import pandas as pd
import os
import csv
import sys
import requests
import shutil
from git import Repo
import git
import apprise
from apprise import NotifyFormat
from apprise import NotifyType
import asyncio
import re
import glob


maxInt = sys.maxsize

while True:
	try:
		csv.field_size_limit(maxInt)
		break
	except OverflowError:
		maxInt = int(maxInt/2)

from telethon.sync import TelegramClient
from telethon import connection
from datetime import date, datetime
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch
from telethon.tl.functions.messages import GetHistoryRequest

sep = os.sep
config = configparser.ConfigParser()
config.read("config.ini")

api_id = config['Telegram']['api_id']
api_hash = config['Telegram']['api_hash']
username = config['Telegram']['username']
tg_bot_token = config['Telegram']['bot_token']
tg_chat_id = config['Telegram']['chat_id']
rocket_token = config['Rocket']['token']
rocket_host = config['Rocket']['host']
DATA_PATH = config['Locations']['data_path']
if not os.path.exists(DATA_PATH):
	os.makedirs(DATA_PATH, exist_ok=True)
CACHE_PATH = config['Locations']['cache_path']
TIMEOUT = config['Telegram']['timeout']
if not os.path.exists(CACHE_PATH):
	os.makedirs(CACHE_PATH, exist_ok=True)
client = TelegramClient(username, api_id, api_hash)
client.start()


def history_search(date_from: str, date_to: str, data_path) -> list:
	messages = []
	if not date_from:
		date_from = '01.01.1970'
	for file in glob.glob(f'{data_path}{sep}**{sep}*.json'):
		filename = file.split(sep)[-1]
		date_string = filename.split('_')[-1].split('.')[0].split('T')[0]
		with open(file, 'r', encoding='utf-8') as f:
			data = json.load(f)
		if data:
			df = pd.json_normalize(data)
			mask = df[['date']].apply(lambda x: x.str.contains(date_from, regex=True, na=False)).any(axis=1)


def find_urls_in_df(df: pd.DataFrame) -> list:
	urls = []
	for index, row in df.iterrows():
		if 'entities' in row.keys():
			for entity in row['entities']:
				if 'url' in entity.keys():
					urls.append(entity['url'])
	urls = sorted(set(urls))
	return urls


def ask_exit() -> None:                          
	for task in asyncio.Task.all_tasks():
		task.cancel()                    
	asyncio.ensure_future(exit())   


def rocket_send_notification(title: str, body: str, format: str = NotifyFormat.TEXT) -> None:
	url = f'rocket://{rocket_token}@{rocket_host}/'
	apobj = apprise.Apprise()
	apobj.add(url)
	apobj.notify(body=body, title=title, notify_type=NotifyType.WARNING)


def telegram_send_notification(title: str, body: str, format: str = NotifyFormat.TEXT) -> None:
	url = f'tgram://{tg_bot_token}/{tg_chat_id}?overflow=split'
	apobj = apprise.Apprise()
	apobj.add(url)
	apobj.notify(body=body, title=title)


def github_targets_parser(repos: list, patterns: list):
	for r in repos:
		repo = Repo(r)
		repo.git().pull()
		headcommit = repo.commit('HEAD').hexsha
		url = repo.remote().url
		filename = '_'.join(url.split('/')[3:])[:-4]
		with open(f'..{sep}commits{sep}{filename}', 'rt') as fp:
			history_commit = fp.read()
		if headcommit == history_commit:
			continue
		else:
			i = 1
			while True:
				c = repo.commit(f'HEAD~{str(i)}').hexsha
				if c == history_commit:
					break
				else:
					i += 1
			new_urls = []
			for item in repo.git.diff(f'HEAD~{str(i)}').split('\n'):
				res = re.search(r'^\+{1}.*',item)
				if res:
					new_urls.append(res.group(0))
			targets = []
			for u in new_urls:
				for pattern in patterns:
					p, d = pattern.split([sep for sep in seps if sep in pattern][0])[0], pattern.split([sep for sep in seps if sep in pattern][0])[1]
					p1=r'.*'+p+r'.*'
					findings = re.search(p1,u)
					if findings:
						targets.append(('finding - ' + u, 'pattern - ' + p, 'descr - ' + d))
			if targets:
				# rocket_send_notification(f'{url}. {str(targets)}.', f'{url[:-4]}/commit/{headcommit}')
				telegram_send_notification(f'{url}. {str(targets)}.', f'{url[:-4]}/commit/{headcommit}')
			with open(f'..{sep}commits{sep}{filename}', 'w') as fp:
				fp.write(headcommit)



def search_for_pattern(pattern_to_search:str, report: str) -> tuple:
	with open(report, 'r', encoding='utf-8') as f:
		data = json.load(f)
	if data:
		df = pd.json_normalize(data)
		mask = df[['message']].apply(lambda x: x.str.contains(pattern_to_search, regex=True, na=False)).any(axis=1)
		pattern_df = df[mask]
		if not pattern_df.empty:
			return True, pattern_df
		else: 
			return False, None
	else:
			return False, None



async def dump_all_messages(channel, short_url_, datetime_) -> None:
	prefix_data = f"{DATA_PATH}{sep}{short_url_}{sep}"
	prefix_cache = f"{CACHE_PATH}{sep}{short_url_}{sep}"
	if os.path.exists(f"{prefix_cache}"):
		if os.path.exists(f"{prefix_cache}message_offset"):
			with open(f"{prefix_cache}message_offset", 'r') as f:
				min_id = int(f.read())
		else:
			min_id = 0
	else:
		os.makedirs(f"{prefix_cache}", exist_ok=True)
		min_id = 0
	
	if os.path.exists(f"{prefix_data}"):
		pass
	else:
		os.makedirs(f"{prefix_data}", exist_ok=True)
	offset_msg = 0
	limit_msg = 10 
	all_messages = [] 
	total_messages = 0
	total_count_limit = 0
	
	class DateTimeEncoder(json.JSONEncoder):
		def default(self, o):
			if isinstance(o, datetime):
				return o.isoformat()
			if isinstance(o, bytes):
				return list(o)
			return json.JSONEncoder.default(self, o)

	while True:
		history = await client(GetHistoryRequest(
			peer=channel,
			offset_id=offset_msg,
			offset_date=None, add_offset=0,
			limit=limit_msg, max_id=0, min_id=min_id,
			hash=0))
		if not history.messages:
			break
		messages = history.messages
		for message in messages:
			all_messages.append(message.to_dict())
		offset_msg = messages[len(messages) - 1].id
		total_messages = len(all_messages)
		if total_count_limit != 0 and total_messages >= total_count_limit:
			break
	with open(f"{prefix_cache}message_offset", 'w') as f:
		f.write(str(total_messages+min_id))
	if all_messages:
		with open(f'{prefix_cache}{short_url_}_messages_{datetime_}.json', 'w', encoding='utf8') as outfile:
			json.dump(all_messages, outfile, ensure_ascii=False, cls=DateTimeEncoder)
		json_file = pd.read_json(f'{prefix_cache}{short_url_}_messages_{datetime_string}.json')
		json_file.to_csv(f'{prefix_cache}{short_url_}_messages_{datetime_string}.csv', index = None, encoding = 'utf8')

async def main():
	channel = await client.get_entity(url)
	await dump_all_messages(channel, channel_string, datetime_string)
		

with open('tg_links.txt', 'r') as f:
	urls = [x.strip() for x in f.readlines()]

with open('patterns', 'r', encoding='utf-8') as f:
	patterns = [x.strip() for x in f.readlines()]

with open('git_repos', 'r', encoding='utf-8') as f:
	repos = [x.strip() for x in f.readlines()]

seps = [',', ':', ';', '\t']

mode = 'silent'
github_targets_parser(repos, patterns)
for url in urls:
	channel_string = url.split('/')[-1]
	datetime_string = str(datetime.now()).replace("-", "").replace(" ", "T").replace(":", "").split(".")[0]
	with client:
		client.loop.run_until_complete(main())
for root, dirs, files in os.walk(f'{CACHE_PATH}'):
	for file in files:
		name = file.split('_messages')[0]
		if file.endswith('.json'):
			for pattern in patterns:
				p, d = pattern.split([sep for sep in seps if sep in pattern][0])[0], pattern.split([sep for sep in seps if sep in pattern][0])[1]
				link = [channel for channel in urls if name in channel][0]
				search_result = search_for_pattern(p, os.path.join(root, file))
				if search_result[0]:
					df = search_result[1]
					s = df[['date', 'message']].to_string().replace(r'\n', '\n')
					additional_urls = find_urls_in_df(df)
					s = re.sub(' +', ' ', s)
					p=r'.*'+p+r'.*'
					findings = re.search(p,s)
					if findings:
						findings = findings.group(0)
					if mode == 'silent':
						indexies = df['id'].values
						if len(indexies) > 0:
							for index in indexies:
								i = str(index)
								# rocket_send_notification(f'pattern {p} ({d}) in channel {link}. Finding - {findings}. msg link', f'{link}/{i}')
								# rocket_send_notification('This links were find in message and can be useful', '\n'.join(additional_urls))
								telegram_send_notification(f'pattern {p} ({d}) in channel {link}. Finding - {findings}. msg link', f'{link}/{i}')
								telegram_send_notification('This links were find in message and can be useful', '\n'.join(additional_urls))
					else:
						# rocket_send_notification(f'pattern {p} ({d}) in channel {link}', s)
						# rocket_send_notification('This links were find in message and can be useful', '\n'.join(additional_urls))
						telegram_send_notification(f'pattern {p} ({d}) in channel {link}', s)
				else:
						pass
						# print(f'No pattern {pattern} in {link}')
		if not 'message_offset' in file:
			shutil.copy(os.path.join(root, file), f'{DATA_PATH}{sep}{name}{sep}{file}')
			os.remove(os.path.join(root, file))



# ask_exit()

