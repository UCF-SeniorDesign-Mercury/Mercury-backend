from flask_testing import TestCase
from src import app
from src.common.database import db


class BaseTestCase(TestCase):
    def create_app(self):
        return app

    @classmethod
    def setUpClass(cls):
        db.reset()

    @classmethod
    def tearDownClass(cls):
        db.reset()

    def tearDown(self):
        db.reset()
