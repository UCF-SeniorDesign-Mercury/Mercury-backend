# -*- coding: utf-8 -*
"""
    tests.api.test_events
    ~~~~~~~~~~~~~~~~~~~~~
"""
from tests.base import BaseTestCase
import json
from firebase_admin import auth
import firebase_admin
import pytest
from unittest import mock
from tests.utils import count_docs
from mockfirestore import MockFirestore


class TestEventsBlueprint(BaseTestCase):
    """Tests for events endpoints"""

    """create_event"""

    def test_create_event(self):
        with mock.patch("firebase_admin.auth.verify_id_token") as magic_mock:
            magic_mock.return_value = {
                "uid": "6Fowt6pbYbJAU8IRUudDnntrYvfc",
            }

            res = self.client.post(
                "/events/create_event",
                headers={"Authorization": "token"},
                data=json.dumps(
                    {
                        "title": "Test Event",
                        "description": "Test Description",
                        "starttime": "2020-01-01T00:00:00",
                        "endtime": "2020-01-01T00:00:00",
                        "type": "Test Type",
                        "period": "Test Period",
                        "organizer": "Test Organizer",
                    }
                ),
                content_type="application/json",
            )

            magic_mock.assert_called()

            self.assertEqual(res.data.decode(), "Event added")
            self.assertEqual(res.status_code, 201)
            self.assertEqual(count_docs("Scheduled-Events"), 1)

    """delete_event"""

    def test_delete_event(self):
        pass

    """update_event"""

    def test_update_event(self):
        pass

    """get_event"""

    def test_get_event(self):
        pass

    """get_events"""

    def test_get_events(self):
        pass
