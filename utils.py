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

class Collections:
    def __init__(self, auth_request):
        self.keypairs     = AES_HMAC_KeyPairs(auth_request.encryption_key, auth_request.hmac_key)
        self.auth_request = auth_request
        self.load_keypairs()

    def load_keypairs(self):
        def process_keypair(keypair):
            return list(map(b64decode, keypair))

        for item, keys in self["crypto"].items():
            self.keypairs.set_collection_default(process_keypair(keys["default"]))
            for collection, keypair in keys['collections'].items():
                self.keypairs[collection] = process_keypair(keypair)

    def keys(self):
        #TODO: Include newest item's time
        collections = self.auth_request.request(f"info/{path}")
        return collections

    def items(self):
        for collection in self.keys():
            yield (collection, self[collection])

    def __getitem__(self, collection):
        return Collection(self.keypairs, collection, self.auth_request)

class Collection:
    def __init__(self, keypairs, collection, auth_request):
        self.keypairs     = keypairs
        self.collection   = collection
        self.auth_request = auth_request

    def path(self, item=None):
        p = f"storage/{self.collection}"
        if item:
            p += f"/{item}"
        return p

    def keys(self):
        #TODO: Include newest item's time
        items = self.auth_request.request(self.path())
        return items

    def items(self):
        for item in self.keys():
            yield (item, self[item])

    def __getitem__(self, item):
        payload = self.auth_request.request(self.path(item))
        record = json.loads(payload['payload'])

        ciphertext_b64  = record['ciphertext'].encode('ascii')
        iv_b64          = record['IV']
        record_hmac     = record['hmac']

        encryption_key, hmac_key = self.keypairs[self.collection]

        # It appears that the Base-64 encoded ciphertext is what is HMACed.
        # https://moz-services-docs.readthedocs.io/en/latest/sync/storageformat5.html#crypto-keys-record
        hmac_comp = hmac.new(key=hmac_key, msg=ciphertext_b64, digestmod=hashlib.sha256).digest()

        hmac_comp_hex = hmac_comp.hex()
        #TODO: Convert to an exception
        assert record_hmac == hmac_comp_hex, "Record HMAC is not correct"

        ciphertext = b64decode(ciphertext_b64)
        iv         = b64decode(iv_b64)

        aes = AES.new(encryption_key, AES.MODE_CBC, iv)
        contents = aes.decrypt(ciphertext)
        # removing PKS7 padding
        contents = contents[:-contents[-1]]
        return json.loads(contents)
