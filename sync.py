#!/usr/bin/env python3

from base64 import b64decode
from configparser import ConfigParser
import requests
from fxa.core import Client
from fxa.plugins.requests import FxABearerTokenAuth, FxABrowserIDAuth
from requests_hawk import HawkAuth
import json
from fxa.crypto import derive_key, calculate_hmac
from Crypto.Cipher import AES

from hkdf import hkdf_extract, hkdf_expand, Hkdf
import hashlib 
import hmac

from utils import Collections
import auth

config_file_name = 'config.ini'

config = ConfigParser()
config.read(config_file_name)

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
for item, bookmark in collections["bookmarks"].items():
    print(item, bookmark)
    break
print("history");
for item, history_entry in collections["history"].items():
    print(item, history_entry)
    break
