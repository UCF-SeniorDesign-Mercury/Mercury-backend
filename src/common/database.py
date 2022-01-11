# -*- coding: utf-8 -*
"""
    src.common.database
    ~~~~~~~~~~~~~~~~~~~
"""
from firebase_admin import credentials, firestore, initialize_app, storage
import os
from dotenv import load_dotenv

load_dotenv()

FIREBASE_KEYS = {
    "type": "service_account",
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace("\\n", "\n"),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI"),
    "auth_provider_x509_cert_url": os.getenv(
        "FIREBASE_AUTH_PROVIDER_X509_CERT_URL"
    ),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL"),
}

cred = credentials.Certificate(FIREBASE_KEYS)
firebase_app = initialize_app(
    cred, {"storageBucket": "electric-eagles.appspot.com"}
)
db = firestore.client()
