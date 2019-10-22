#!/usr/bin/env python3

import requests
from configparser import ConfigParser
import db
import requests_cache
from readability import Document
from bs4 import BeautifulSoup
import psycopg2

requests_cache.install_cache('demo_cache')


config_file_name = 'config.ini'

config = ConfigParser()
config.read(config_file_name)

conn = db.login(config)

def extract_content_text(soup):
    # The readability module didn't see to work on the python docs, so
    # we'll just do something quick and dirty.
    body = None

    article = soup.select_one('article')
    role_main = soup.select_one('[role=main]')
    if article:
        body = article
    elif role_main:
        body = role_main
    else:
        body = soup.body

    if body:
        for tag in body.select('iframe, script'):
            tag.extract()

        headers = " ".join(map(lambda t: t.text, body.select("h1,h2,h3,h4,h5,h6")))
        return (body.text, headers)
    return ("", "")

for he in db.get_history_for_text(conn):
    response = requests.get(he['url'])

    if response.status_code != requests.codes.ok:
        continue

    soup = BeautifulSoup(response.text, 'html.parser')
    processed_text, headers = extract_content_text(soup)

    title = None
    first_h1 = soup.body.select_one('h1')
    if soup.title:
       title = soup.title.text
    elif first_h1:
       title = first_h1.text

    url_text = {
        'history_id': he['history_id'],
        'raw_text': response.text,
        'processed_text': processed_text,
        'title': title, 
        'headers': headers,
    }
    try:
        db.insert_url_text(conn, url_text)
    except psycopg2.OperationalError as e:
        if 'index row requires' in str(e):
            print(f"{he['url']} is too long at {len(processed_text)}")
        else:
            raise e

