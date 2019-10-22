#!/usr/bin/env python3

from configparser import ConfigParser
import db
import argparse

parser = argparse.ArgumentParser(description='search the db.')
parser.add_argument('terms', type=str, nargs='+', help="terms to search")
args = parser.parse_args()

config_file_name = 'config.ini'

config = ConfigParser()
config.read(config_file_name)

conn = db.login(config)

for result in db.search_text(conn, ' '.join(args.terms)):
    print(result['title'])
    print(result['url']);
    print(f"{result['rank']:6.3f} | {result['processed_text_rank']:6.3f} | {result['title_rank']:6.3f} | {result['headers_rank']:6.3f}")
    print('-'*72)
