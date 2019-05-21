#!/usr/bin/env python3

from configparser import ConfigParser
import requests
from fxa.core import Client
from fxa.plugins.requests import FxABearerTokenAuth, FxABrowserIDAuth
from requests_hawk import HawkAuth
import json
from fxa.crypto import derive_key, calculate_hmac

from hkdf import hkdf_extract, hkdf_expand, Hkdf
import hashlib 
import hmac

config = ConfigParser()
config.read('config.ini')
user = config['user']


client = Client("https://api.accounts.firefox.com")
session = client.login(user['email'], user['password'], keys=True)

#TODO: Store keys because logining causes an email to be sent out
keyA,keyB = session.fetch_keys()

print("Key A: " + keyA.hex())
print("Key B: " + keyB.hex())

info = b"identity.mozilla.com/picl/v1/oldsync"
namespace = b"oldsync"
keys = derive_key(secret=keyB, namespace=namespace, size=64)
encryption_key = keys[0:32]
hmac_key = keys[32:]

# Verify that derive key does what I'm expecting
prk = hkdf_extract(salt=bytes([0]), input_key_material=keyB, hash=hashlib.sha256)
key_bundle = hkdf_expand(pseudo_random_key=prk, info=info, length=64, hash=hashlib.sha256)
assert(key_bundle == keys)

assert(len(encryption_key) == 32)
assert(len(hmac_key) == 32)

# TODO: Store this or a derived longer-lived token
#       Causes a login event which causes an email
fxab = FxABrowserIDAuth(user['email'], user['password'], with_client_state=True)
raw_resp = requests.get('https://token.services.mozilla.com/1.0/sync/1.5', auth=fxab)
raw_resp.raise_for_status()

resp = raw_resp.json()
user_id = resp['uid']
endpoint = resp['api_endpoint']
hawk_auth = HawkAuth(id=resp['id'], key=resp['key'])

#TODO: Include newest item's time
raw_resp=requests.get(f"{endpoint}/info/collections", auth=hawk_auth)
collections = raw_resp.json()

print("Looking for items to sync")
for collection, last_mod_time in collections.items():
    print(f"{collection}(last modified time={last_mod_time})")
    raw_resp=requests.get(f"{endpoint}/storage/{collection}", auth=hawk_auth)
    items = raw_resp.json()
    for item in items:
        print(f"  {item}")
        raw_resp=requests.get(f"{endpoint}/storage/{collection}/{item}", auth=hawk_auth)
        resp  = raw_resp.json()
        record = json.loads(resp['payload'])

        ciphertext_b64  = record['ciphertext'].encode('ascii')
        iv              = record['IV']
        record_hmac     = record['hmac']


        hmac_comp = calculate_hmac(key=hmac_key, data=ciphertext_b64)

        # Verify that calculate_hmac does what I expect.
        manual_hmac_comp = hmac.new(key=hmac_key, msg=ciphertext_b64, digestmod=hashlib.sha256).digest()
        assert(manual_hmac_comp == hmac_comp)

        hmac_comp_hex = hmac_comp.hex()
        print(f"    HMAC")
        print(f"      Expected: {record_hmac}")
        print(f"      Computed: {hmac_comp_hex}")
        assert(record_hmac == hmac_comp_hex)

# Output
# ======
# Key A: 8af1d34887ac4cf9bad29638d1c37f1cdedeefe6153cebbb63c8b9139fe48b95
# Key B: c096a55f369ea47c3bc4520b1cb01cdf6c228c4e31bca3a9fdbbea3ac3839db4
# Looking for items to sync
# tabs(last modified time=1558452052.49)
#   ErUks95k6Qqf
#     HMAC
#       Expected: 332bb635a36b09ef27a2164d4ae418f07b6c2ab65c5bc92c426852f935f082fb
#       Computed: ef786422c2837cbd34d6982eeb6121049a6da27606708d3e270c778f987a98bd
# Traceback (most recent call last):
#   File "./sync.py", line 87, in <module>
#     assert(record_hmac == hmac_comp_hex)
# AssertionError
