#!/usr/bin/env python3.8

import requests
import requests.exceptions
from configparser import ConfigParser
import db
import requests_cache
from readability import Document
from bs4 import BeautifulSoup
import psycopg2

requests_cache.install_cache('page_fetcher_cache')


config_file_name = 'config.ini'

config = ConfigParser()
config.read(config_file_name)

conn = db.login(config)

def extract_content_text(soup):
    # The readability module didn't see to work on the python docs, so
    # we'll just do something quick and dirty.
    body = None

    if article := soup.select_one('article'):
        body = article
    elif role_main := soup.select_one('[role=main]'):
        body = role_main
    else:
        body = soup.body

    if body:
        for tag in body.select('iframe, script'):
            tag.extract()

        headers = " ".join(map(lambda t: t.text, body.select("h1,h2,h3,h4,h5,h6")))
        return (body.text, headers)
    return ("", "")

i = 0
ua_header = {
    'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:67.0) Gecko/20100101 Firefox/67.0',
    'Accept': 'text/html',
}
for he in db.get_history_for_text(conn):
    i += 1
    if i % 1 == 0:
        print(f"On record {i} {he['url']}")
    url_text = {
        'history_entry_id': he['history_entry_id'],
        'bookmark_entry_id': he['bookmark_entry_id'],
        'title': he['title'],
        'url': he['url'],
    }
    try:
        response = requests.get(he['url'], headers=ua_header)
    except requests.exceptions.RequestException as e:
        print(f"{he['url']} {e}")
        url_text['http_status'] = -300
        db.insert_url_text(conn, url_text)
        continue

    url_text['http_status'] = response.status_code

    if response.status_code != requests.codes.ok:
        print(f"{he['url']} returned code {response.status_code}")
        db.insert_url_text(conn, url_text)
        continue

    if 'Content-Type' in response.headers and 'text/html' not in response.headers['Content-Type']:
        print(f"{he['url']} is not HTML (is {response.headers['Content-Type']})")
        db.insert_url_text(conn, url_text)
        continue


    soup = BeautifulSoup(response.text, 'html.parser')
    processed_text, headers = extract_content_text(soup)

    title = None
    if soup.title:
       title = soup.title.text
    elif first_h1 := (soup.body and soup.body.select_one('h1')):
       title = first_h1.text

    url_text.update({
        'raw_text': response.text,
        'processed_text': processed_text,
        'title': title, 
        'headers': headers,
    })
    try:
        db.insert_url_text(conn, url_text)
    except psycopg2.OperationalError as e:
        if 'index row requires' in str(e) or 'index row size' in str(e):
            print(f"{he['url']} is too long at {len(processed_text)}")
            url_text['raw_text'] = None
            url_text['processed_text'] = None
            db.insert_url_text(conn, url_text)
        else:
            raise e

