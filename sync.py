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

config_file_name = 'config.ini'

config = ConfigParser()
config.read(config_file_name)

hawk_resp = None
encryption_key = None
hmac_key = None

if 'hawk' not in config or 'fxa' not in config:
    user = config['user']

    client = Client("https://api.accounts.firefox.com")
    session = client.login(user['email'], user['password'], keys=True)

    keyA,keyB = session.fetch_keys()

    info = b"identity.mozilla.com/picl/v1/oldsync"
    namespace = b"oldsync"
    keys = derive_key(secret=keyB, namespace=namespace, size=64)
    encryption_key = keys[0:32]
    hmac_key = keys[32:64]

    # TODO: Store this or a derived longer-lived token
    #       Causes a login event which causes an email
    fxab = FxABrowserIDAuth(user['email'], user['password'], with_client_state=True)
    raw_resp = requests.get('https://token.services.mozilla.com/1.0/sync/1.5', auth=fxab)
    raw_resp.raise_for_status()

    hawk_resp = raw_resp.json()
    config['hawk'] = hawk_resp
    config['fxa'] = {
        'encryption_key': encryption_key.hex(),
        'hmac_key': hmac_key.hex(),
    }
    with open(config_file_name, 'w') as configfile:
        config.write(configfile)
else:
    hawk_resp = config['hawk']
    encryption_key = bytes.fromhex(config['fxa']['encryption_key'])
    hmac_key = bytes.fromhex(config['fxa']['hmac_key'])

user_id = hawk_resp['uid']
endpoint = hawk_resp['api_endpoint']
hawk_auth = HawkAuth(id=hawk_resp['id'], key=hawk_resp['key'])

class AES_HMAC_KeyPairs:
    def __init__(self, e, h):
        self.account_keypair= (e, h)

        self.collection_keys = {}
        self.collection_keypair = None

    def set_collection_default(self, pair):
        self.collection_keypair = pair

    def get_account_default(self):
        return self.account_keypair

    def get_collection_default(self):
        if self.collection_keypair is not None:
            return self.collection_keypair
        return self.account_keypair

    def __setitem__(self, key, val):
        self.collection_keys[key] = val;

    def __getitem__(self, key):
        if key in self.collection_keys:
            return self.collection_keys[key]
        return self.get_collection_default()

keypairs = AES_HMAC_KeyPairs(encryption_key, hmac_key)

def get_collection(collection):
    raw_resp=requests.get(f"{endpoint}/storage/{collection}", auth=hawk_auth)
    assert raw_resp.status_code == requests.codes.ok, f"{raw_resp.status_code} is not OK for collection {collection}"

    items = raw_resp.json()
    for item in items:
        yield get_item(collection, item)


def get_item(collection, item):
    raw_resp=requests.get(f"{endpoint}/storage/{collection}/{item}", auth=hawk_auth)
    assert raw_resp.status_code == requests.codes.ok, f"{raw_resp.status_code} is not OK for item {collection}/{item}"
    resp  = raw_resp.json()
    record = json.loads(resp['payload'])

    ciphertext_b64  = record['ciphertext'].encode('ascii')
    iv_b64          = record['IV']
    record_hmac     = record['hmac']

    keypair = keypairs[collection]
    encryption_key, hmac_key = keypairs[collection]

    # It appears that the Base-64 encoded ciphertext is what is HMACed.
    # https://moz-services-docs.readthedocs.io/en/latest/sync/storageformat5.html#crypto-keys-record
    hmac_comp = hmac.new(key=hmac_key, msg=ciphertext_b64, digestmod=hashlib.sha256).digest()

    hmac_comp_hex = hmac_comp.hex()
    assert record_hmac == hmac_comp_hex, "Record HMAC is not correct"

    ciphertext = b64decode(ciphertext_b64)
    iv         = b64decode(iv_b64)

    aes = AES.new(encryption_key, AES.MODE_CBC, iv)
    contents = aes.decrypt(ciphertext)
    # removing PKS7 padding
    contents = contents[:-contents[-1]]
    return json.loads(contents)

for keys in get_collection("crypto"):
    keypairs.set_collection_default(list(map(b64decode, keys["default"])))
    for collection, keypair in keys['collections'].items():
        keypairs[collection] = list(map(b64decode, keypair))

print("bookmarks");
for bookmark in get_collection("bookmarks"):
    print(bookmark)
    break
print("history");
for item in get_collection("history"):
    print(item)
    break
