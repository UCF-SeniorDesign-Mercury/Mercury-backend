# -*- coding: utf-8 -*
"""
    src.common.database
    ~~~~~~~~~~~~~~~~~~~
"""
from firebase_admin import credentials, firestore, initialize_app, storage
from os import environ

FIREBASE_KEYS = {
    "type": "service_account",
    "project_id": environ["FIREBASE_PROJECT_ID"],
    "private_key_id": environ["FIREBASE_PRIVATE_KEY_ID"],
    "private_key": environ["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n"),
    "client_email": environ["FIREBASE_CLIENT_EMAIL"],
    "client_id": environ["FIREBASE_CLIENT_ID"],
    "auth_uri": environ["FIREBASE_AUTH_URI"],
    "token_uri": environ["FIREBASE_TOKEN_URI"],
    "auth_provider_x509_cert_url": environ["FIREBASE_AUTH_PROVIDER_X509_CERT_URL"],
    "client_x509_cert_url": environ["FIREBASE_CLIENT_X509_CERT_URL"],
}

cred = credentials.Certificate(FIREBASE_KEYS)
firebase_app = initialize_app(
    cred, {'storageBucket': 'electric-eagles.appspot.com'})
db = firestore.client()
