# -*- coding: utf-8 -*
"""
    src.common.database
    ~~~~~~~~~~~~~~~~~~~
"""
from firebase_admin import credentials, firestore, initialize_app, storage

cred = credentials.Certificate('key.json')
firebase_app = initialize_app(
    cred, {'storageBucket': 'electric-eagles.appspot.com'})
db = firestore.client()
