#!/usr/bin/env python3

import requests
from fxa.core import Client
from fxa.plugins.requests import FxABearerTokenAuth, FxABrowserIDAuth
from requests_hawk import HawkAuth
from fxa.crypto import derive_key, calculate_hmac

def login(user):
    """
    Logs a user into their Firefox account and returns tempoary credentials
    for use by AuthRequest.
    """
    # TODO: pull out the urls to be part of the config.
    client = Client("https://api.accounts.firefox.com")
    session = client.login(user['email'], user['password'], keys=True)

    keyA,keyB = session.fetch_keys()

    # Magic strings from the docs
    # https://moz-services-docs.readthedocs.io/en/latest/sync/storageformat5.html
    info = b"identity.mozilla.com/picl/v1/oldsync"
    namespace = b"oldsync"
    keys = derive_key(secret=keyB, namespace=namespace, size=64)
    encryption_key = keys[0:32]
    hmac_key = keys[32:64]

    # TODO: Store this or a derived longer-lived token
    #       Causes a login event which causes an email
    # TODO: Should move to use OAuth which solves the long-term cred storage
    #       issue
    fxab = FxABrowserIDAuth(user['email'], user['password'], with_client_state=True)
    raw_resp = requests.get('https://token.services.mozilla.com/1.0/sync/1.5', auth=fxab)
    raw_resp.raise_for_status()
    hawk_resp = raw_resp.json()

    return {
        "hawk_resp": hawk_resp,
        "hawk_uid": hawk_resp['uid'],
        "hawk_hashalg": hawk_resp['hashalg'],
        "hawk_api_endpoint": hawk_resp['api_endpoint'],
        "hawk_duration": hawk_resp['duration'],
        "hawk_key": hawk_resp['key'],
        "hawk_hashed_fxa_uid": hawk_resp['hashed_fxa_uid'],
        "hawk_id": hawk_resp['id'],

        'encryption_key': encryption_key.hex(),
        'hmac_key': hmac_key.hex(),
    }

class AuthRequest:
    """
    Provides a wrapper for making requests to the endpoint found when
    first authenticating and the tempoary credentials.
    """
    def __init__(self, login_resp):
        self.encryption_key = bytes.fromhex(login_resp['encryption_key'])
        self.hmac_key       = bytes.fromhex(login_resp['hmac_key'])
        self.user_id        = login_resp['hawk_uid']
        self.endpoint       = login_resp['hawk_api_endpoint']
        self.hawk_auth      = HawkAuth(id=login_resp['hawk_id'], key=login_resp['hawk_key'])

    def request(self, path, params=None):
        path = f"{self.endpoint}/{path}"
        raw_resp = requests.get(path, auth=self.hawk_auth, params=params)
        raw_resp.raise_for_status()
        return raw_resp
