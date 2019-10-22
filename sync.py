#!/usr/bin/env python3

from configparser import ConfigParser
from utils import Collections
import auth
import db

import requests_cache
requests_cache.install_cache('demo_cache')


config_file_name = 'config.ini'

config = ConfigParser()
config.read(config_file_name)

conn = db.login(config)

login_resp = None
if 'login_resp' not in config:
    login_resp = auth.login(config['user'])

    config['login_resp'] = login_resp
    with open(config_file_name, 'w') as configfile:
        config.write(configfile)
else:
    login_resp = config['login_resp']

auth_request = auth.AuthRequest(login_resp)

collections = Collections(auth_request)

print("bookmarks");
i = 0
n = len(collections['bookmarks'].keys())
with db.BookmarkInserter(conn) as bi:
    for item, bookmark in collections["bookmarks"].items():
        bi.insert(bookmark)
        i+=1
        if i % 100 == 0:
            p = (100.0 * i) / n
            print(f"{i} of {n} ({p}%)")

print("history");
i = 0
n = len(collections["history"].keys())
print(db.last_history_time(conn))
with db.HistoryInserter(conn) as hi:
    for item, history_entry in collections["history"].items():
        hi.insert(history_entry)
        i+=1
        if i % 100 == 0:
            p = (100.0 * i) / n
            print(f"{i} of {n} ({p}%)")
