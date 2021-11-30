from flask_testing import TestCase


class BaseTestCase(TestCase):
    def create_app(self):
        pass

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass
