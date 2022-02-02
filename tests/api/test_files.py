# -*- coding: utf-8 -*
"""
    tests.api.test_files
    ~~~~~~~~~~~~~~~~~~~~
"""
from urllib import response

from httplib2 import Response
from tests.base import BaseTestCase
from src.common.decorators import check_token
from src.common.database import db
from firebase_admin import storage, auth, firestore
import requests
from flask import jsonify

token: str = input("Please put your token here:")


class TestFilesBlueprint(BaseTestCase):
    """Tests for files endpoints"""

    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")

    """upload_file"""

    def test_upload_file(self):
        url: str = "https://mercury456.herokuapp.com/files/upload_file"
        data: dict = {
            "filename": "Backend_Uint_Testing.pdf",
            "reviewer": "4F1JpM9bZYOdruyTheiNC1gGRWG2",
            "file": "This is a simple test!",
        }
        body = jsonify(data)
        header: dict = {
            "Content-Type": "application/json",
            "Authorization": token,
        }
        response = requests.put(url, header=header, data=body)

        assert response.status_code == 201

    """get_file"""

    def test_get_file(self):
        pass

    """delete_file"""

    def test_delete_file(self):
        pass
