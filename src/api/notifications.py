# -*- coding: utf-8 -*
"""
    src.api.events
    ~~~~~~~~~~~~~~
    Functions:
        create_notification()
        get_notifications()
        read_notifications()
        delete_notifications()
"""
import email
from firebase_admin import auth, firestore
from firebase_admin.auth import UserRecord
from flask import Response, jsonify, request
from uuid import uuid4
from werkzeug.exceptions import BadRequest, NotFound, Unauthorized

from src.api import Blueprint
from src.common.database import db
from src.common.decorators import admin_only, check_token

notifications: Blueprint = Blueprint("notifications", __name__)


def create_notification(
    notification_type: str,
    file_type: str,
    sender: str,
    receiver_name: str,
    receiver_uid: str,
):

    entry: dict = dict()
    entry["notification_type"] = notification_type
    entry["sender"] = sender
    entry["read"] = False
    entry["file_type"] = file_type
    entry["notification_id"] = str(uuid4())
    entry["timestamp"] = firestore.SERVER_TIMESTAMP

    if receiver_uid != None:
        entry["receiver"] = receiver_uid
    else:
        # get to_user uid.
        receiver_docs = (
            db.collection("User")
            .where("name", "==", receiver_name)
            .limit(1)
            .stream()
        )

        if receiver_docs == None:
            raise NotFound("The receiver was not found")
        receiver: dict = dict
        for doc in receiver_docs:
            receiver = doc.to_dict()
        email: str = receiver.get("email")
        user: UserRecord = auth.get_user_by_email(email)
        entry["receiver"] = user.uid

    db.collection("Notification").document().set(entry)


@notifications.get("/get_notifications")
def get_notifications():
    """
    Get 10 unread notifications.
    ---
    tags:
        - notifications
    summary: Get 10 unread notifications.
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
        - in: query
          name: page_limit
          schema:
            type: integer
          required: false
        - in: query
          name: read
          schema:
            type: boolean
          required: false
        - in: query
          name: file_type
          schema:
            type: string
          required: false
    responses:
        200:
            content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: '#/components/schemas/Notification'
        400:
            description: Bad request
        401:
            description: Unauthorized - the provided token is not valid
        404:
            description: NotFound
        415:
            description: Unsupported media type.
        500:
            description: Internal API Error
    """
    # check tokens and get uid from token
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")
    # Get the page limits, notification_type, read from the front-end if exists
    page_limit: int = request.args.get("page_limit", default=10, type=int)
    file_type: str = request.args.get("file_type", type=str)
    read: int = request.args.get("read", type=bool)

    # Get the next batch of review docs
    if "file_type" in request.args and "read" in request.args:
        notification_docs = (
            db.collection("Notification")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .where("reviewer", "==", uid)
            .where("read", "==", read)
            .where("file_type", "==", file_type)
            .limit(page_limit)
            .stream()
        )
    elif "notification_type" in request.args:
        notification_docs = (
            db.collection("Notification")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .where("receiver", "==", uid)
            .where("file_type", "==", file_type)
            .limit(page_limit)
            .stream()
        )
    elif "read" in request.args:
        notification_docs = (
            db.collection("Notification")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .where("receiver", "==", uid)
            .where("read", "==", read)
            .limit(page_limit)
            .stream()
        )
    else:
        notification_docs = (
            db.collection("Notification")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .where("receiver", "==", uid)
            .limit(page_limit)
            .stream()
        )

    notifications: list = list()
    for doc in notification_docs:
        notifications.append(doc.to_dict())

    return jsonify(notifications), 200


def read_notification():
    pass


def delete_notification():
    pass
