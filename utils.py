#!/usr/bin/env python3

from base64 import b64decode
import json
from Crypto.Cipher import AES
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
        resp = self.auth_request.request(f"info/collections")
        collections = resp.json()
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

        self.cache  = {}
        self.next_offset = None

    def path(self, item=None):
        p = f"storage/{self.collection}"
        if item:
            p += f"/{item}"
        return p

    def keys(self):
        # https://mozilla-services.readthedocs.io/en/latest/storage/apis-1.5.html
        # 
        # This request has additional optional query parameters:
        #
        #     ids: a comma-separated list of ids. Only objects whose id is in this list will be returned. A maximum of 100 ids may be provided.
        #     newer: a timestamp. Only objects whose last-modified time is strictly greater than this value will be returned.
        #     older: a timestamp. Only objects whose last-modified time is strictly smaller than this value will be returned.
        #     full: any value. If provided then the response will be a list of full BSO objects rather than a list of ids.
        #
        # We should make use of these to batch calls and only find newer
        params = {
            'sort': 'oldest',
        }
        resp = self.auth_request.request(self.path(), params)
        items = resp.json()

        return items

    def items(self, newer=None):
        params = {
            'sort': 'oldest',
            'limit': 1000,
            'full': True,
        }
        first = True
        while first or self.next_offset:
            first = False
            if self.next_offset:
                params['offset'] = self.next_offset
            if newer:
                params['newer'] = newer
            resp = self.auth_request.request(self.path(), params)
            items = resp.json()

            if 'X-Weave-Next-Offset' in resp.headers:
                self.next_offset = resp.headers['X-Weave-Next-Offset']
            else:
                self.next_offset = None

            if type(items) is list:
                if len(items) > 0:
                    test = items[0]
                    if type(test) is dict:
                        self.cache = {v['id']: v for v in items}
            for item in self.cache.keys():
                yield (item, self[item])

    def __getitem__(self, item):
        bso = None

        if item in self.cache:
            bso = self.cache[item]
        else:
            resp = self.auth_request.request(self.path(item))
            bso = resp.json()

        payload = json.loads(bso['payload'])

        ciphertext_b64  = payload['ciphertext'].encode('ascii')
        iv_b64          = payload['IV']
        payload_hmac    = payload['hmac']

        encryption_key, hmac_key = self.keypairs[self.collection]

        # It appears that the Base-64 encoded ciphertext is what is HMACed.
        # https://moz-services-docs.readthedocs.io/en/latest/sync/storageformat5.html#crypto-keys-payload
        hmac_comp = hmac.new(key=hmac_key, msg=ciphertext_b64, digestmod=hashlib.sha256).digest()

        hmac_comp_hex = hmac_comp.hex()
        #TODO: Convert to an exception
        assert payload_hmac == hmac_comp_hex, "Record HMAC is not correct"

        ciphertext = b64decode(ciphertext_b64)
        iv         = b64decode(iv_b64)

        aes = AES.new(encryption_key, AES.MODE_CBC, iv)
        contents = aes.decrypt(ciphertext)
        # removing PKS7 padding
        contents = contents[:-contents[-1]]
        contents = json.loads(contents)
        contents['modified'] = bso['modified']

        return contents
