# -*- coding: utf-8 -*
"""
    src.api.events
    ~~~~~~~~~~~~~~
    Functions:
        create_event()
        delete_event()
        update_event()
        get_event()
        get_events()
"""
from datetime import datetime
from itertools import chain
from dateutil import parser
from firebase_admin import auth, firestore
from flask import Response, jsonify, request
from uuid import uuid4
from werkzeug.exceptions import BadRequest, NotFound, Unauthorized

from src.api import Blueprint
from src.api import notifications
from src.api.notifications import create_notification
from src.common.database import db
from src.common.decorators import check_token
from src.common.notifications import (
    add_scheduled_notification,
    cancel_scheduled_notification,
)

events: Blueprint = Blueprint("events", __name__)


@events.post("/create_event")
@check_token
def create_event() -> Response:
    """
    Creates an event.
    ---
    tags:
        - event
    summary: Creates event
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: '#/components/schemas/CreateEvent'
        description: Created event object
        required: true
    responses:
        201:
            description: Event created
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
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")

    # add more initial information
    data: dict = request.get_json()

    # get user table
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    # Exceptions
    if "title" not in data or not data.get("title").strip():
        return BadRequest("Missing the title")
    if "starttime" not in data or not data.get("starttime").strip():
        return BadRequest("Missing the starttime")
    if "endtime" not in data or not data.get("endtime").strip():
        return BadRequest("Missing the endtime")
    if "type" not in data or not data.get("type").strip():
        return BadRequest("Missing the type")
    if "period" not in data or not isinstance(data.get("period"), bool):
        return BadRequest("Missing the period")
    if "invitees_dod" not in data or not isinstance(
        data.get("invitees_dod"), list
    ):
        return BadRequest("Missing the invitees_dod")
    if "organizer" not in data or not data.get("organizer").strip():
        return BadRequest("Missing the organizer")

    entry: dict = dict()
    entry["author"] = uid
    entry["event_id"] = str(uuid4())
    entry["timestamp"] = firestore.SERVER_TIMESTAMP
    entry["title"] = data.get("title")
    entry["starttime"] = data.get("starttime")
    entry["endtime"] = data.get("endtime")
    entry["type"] = data.get("type")
    entry["period"] = data.get("period")
    entry["invitees_dod"] = data.get("invitees_dod")
    entry["confirmed_dod"] = []
    entry["organizer"] = data.get("organizer")
    entry["description"] = data.get("description")
    entry["weekly"] = data.get("weekly")
    entry["yearly"] = data.get("yearly")

    # write to Firestore DB
    db.collection("Scheduled-Events").document(entry.get("event_id")).set(entry)

    # notify users
    try:
        fcm_tokens: list = list()
        for dod in data.get("invitees_dod"):
            # get to_user uid.
            receiver_docs = (
                db.collection("User").where("dod", "==", dod).limit(1).stream()
            )

            receiver_list: list = []
            for doc in receiver_docs:
                receiver_list.append(doc.to_dict())

            receiver: dict = receiver_list[0]

            if receiver.get("FCMToken"):
                fcm_tokens.append(receiver.get("FCMToken"))

            create_notification(
                notification_type="invite to an event",
                type=entry.get("type"),
                sender=uid,
                id=entry.get("event_id"),
                receiver_dod=dod,
                sender_name=user.get("name"),
            )

    except:
        return NotFound("The invitee was not found")

    if fcm_tokens:
        timer_id: str = add_scheduled_notification(
            data.get("starttime"),
            fcm_tokens,
            {
                "title": "event invitation",
                "body": (
                    user.get("name") + " invite you to " + entry.get("type")
                ),
            },
        )
        db.collection("Scheduled-Events").document(
            entry.get("event_id")
        ).update({"timer_id": timer_id})

    # return Response 201 for successfully creating a new resource
    return Response(response="Event added", status=201)


@events.delete("/delete_event/<event_id>")
@check_token
def delete_event(event_id: str) -> Response:
    """
    Delete an event from database.
    ---
    tags:
        - event
    summary: Deletes an event
    parameters:
        - in: path
          name: event_id
          schema:
            type: string
          description: The event id
          required: true
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
    responses:
        200:
            description: Event deleted
        400:
            description: Bad request
        401:
            description: Unauthorized - the provided token is not valid
        404:
            description: NotFound
        500:
            description: Internal API Error
    """
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")

    # fetch event data from firestore
    event_ref = db.collection("Scheduled-Events").document(event_id)
    event: dict = event_ref.get().to_dict()

    # get user table
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    # if event does not exists
    if not event_ref.get().exists:
        return NotFound("The event not found")

    # Only the event user could delete the event
    if event.get("author") != uid:
        return Response(
            "The user is not authorized to retrieve this content", 401
        )

    # notify users
    try:
        for dod in event.get("invitees_dod"):
            create_notification(
                notification_type="event canceled",
                type=event.get("type"),
                sender=uid,
                id=event.get("event_id"),
                receiver_dod=dod,
                sender_name=user.get("name"),
            )

        for dod in event.get("confirmed_dod"):
            create_notification(
                notification_type="event canceled",
                type=event.get("type"),
                sender=uid,
                id=event.get("event_id"),
                receiver_dod=dod,
                sender_name=user.get("name"),
            )
    except:
        return NotFound("The invitee was not found")

    if "timer_id" in event:
        cancel_scheduled_notification(event.get("timer_id"))

    # delete the notifications about this event.
    notifications_docs = (
        db.collection("Notification").where("id", "==", event).stream()
    )
    for notification_doc in notifications_docs:
        notification_doc.reference.delete()

    event_ref.delete()
    return Response(response="Event deleted", status=200)


@events.put("/update_event")
@check_token
def update_event() -> Response:
    """
    Updates an event that has already been created.
    ---
    tags:
        - event
    summary: Update event
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: '#/components/schemas/UpdateEvent'
        description: Updated event object
        required: true
    responses:
        200:
            description: Event updated
        400:
            description: Bad request
        401:
            description: Unauthorized - the provided token is not valid
        404:
            description: NotFound
        500:
            description: Internal API Error
    """
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    data: dict = request.get_json()
    event_id: str = data.get("event_id")
    uid: str = decoded_token.get("uid")

    # fetch event data from firestore
    event_ref = db.collection("Scheduled-Events").document(event_id)
    event: dict = event_ref.get().to_dict()

    # get user table
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    # if event does not exists
    if not event_ref.get().exists:
        return NotFound("The event was not found")

    # Only the event organizer and admin could update the event
    if event.get("author") != uid and decoded_token.get("admin") != True:
        return Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    # update event by given parameter
    if "starttime" in data:
        event_ref.update({"starttime": data.get("starttime")})
    if "endtime" in data:
        event_ref.update({"endtime": data.get("endtime")})
    if "period" in data:
        event_ref.update({"period": data.get("period")})
    if "type" in data and data.get("type").strip():
        event_ref.update({"type": data.get("type")})
    if "title" in data and data.get("title").strip():
        event_ref.update({"title": data.get("title")})
    if "description" in data and data.get("description").strip():
        event_ref.update({"description": data.get("description")})
    if "organizer" in data and data.get("organizer").strip():
        event_ref.update({"organizer": data.get("organizer")})

    if "new_invitees" in data and data.get("new_invitees"):
        event_ref.update({"invitees_dod": data.get("new_invitees")})

    # fetch event data from firestore
    event_ref = db.collection("Scheduled-Events").document(event_id)
    event: dict = event_ref.get().to_dict()
    # notify users
    try:
        fcm_tokens: list = list()
        for dod in event.get("invitees_dod"):
            # get to_user uid.
            receiver_docs = (
                db.collection("User").where("dod", "==", dod).limit(1).stream()
            )

            receiver_list: list = []
            for doc in receiver_docs:
                receiver_list.append(doc.to_dict())

            receiver: dict = receiver_list[0]

            if receiver.get("FCMToken"):
                fcm_tokens.append(receiver.get("FCMToken"))
            create_notification(
                notification_type="event updated",
                type=event.get("type"),
                sender=uid,
                id=event.get("event_id"),
                receiver_dod=dod,
                sender_name=user.get("name"),
            )
        for dod in event.get("confirmed_dod"):
            # get to_user uid.
            receiver_docs = (
                db.collection("User").where("dod", "==", dod).limit(1).stream()
            )

            receiver_list: list = []
            for doc in receiver_docs:
                receiver_list.append(doc.to_dict())

            receiver: dict = receiver_list[0]

            if receiver.get("FCMToken"):
                fcm_tokens.append(receiver.get("FCMToken"))
            create_notification(
                notification_type="event updated",
                type=event.get("type"),
                sender=uid,
                id=event.get("event_id"),
                receiver_dod=dod,
                sender_name=user.get("name"),
            )
    except:
        return NotFound("The invitee was not found")

    if "timer_id" in event:
        cancel_scheduled_notification(event.get("timer_id"))
        timer_id: str = add_scheduled_notification(
            event.get("starttime"),
            fcm_tokens,
            {
                "title": "event invitation",
                "body": (
                    user.get("name") + " invite you to " + event.get("type")
                ),
            },
        )
        db.collection("Scheduled-Events").document(
            event.get("event_id")
        ).update({"timer_id": timer_id})

    return Response(response="Event updated", status=200)


@events.get("/get_todays_events")
@check_token
def get_todays_events() -> Response:
    """
    Gets events for the current day.
    ---
    tags:
        - event
    summary: Gets events for the current day
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
    responses:
        200:
            content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: '#/components/schemas/Event'
        400:
            description: Bad request
        401:
            description: Unauthorized - the provided token is not valid
        500:
            description: Internal API Error
    """
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")

    # get user table
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    today = datetime.now().date()

    docs1: list = (
        db.collection("Scheduled-Events")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .where("invitees_dod", "array_contains", user.get("dod"))
        .stream()
    )
    docs2: list = (
        db.collection("Scheduled-Events")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .where("confirmed_dod", "array_contains", user.get("dod"))
        .stream()
    )
    docs3: list = (
        db.collection("Scheduled-Events")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .where("author", "==", uid)
        .stream()
    )
    docs = chain(docs1, docs2, docs3)

    events: list = []
    for doc in docs:
        temp: dict = doc.to_dict()
        starttime_string = temp["starttime"].split("T")
        endtime_string = temp["starttime"].split("T")
        starttime = datetime.strptime(starttime_string[0], "%Y-%m-%d").date()
        endtime = datetime.strptime(endtime_string[0], "%Y-%m-%d").date()

        if (
            starttime <= today
            and endtime >= today
            or starttime == today
            or endtime == today
        ):
            events.append(temp)

    return jsonify(events), 200


@events.get("/get_events")
@check_token
def get_events() -> Response:
    """
    Get recent 10 events from database.
    ---
    tags:
        - event
    summary: Gets recent 10 events
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
        - in: query
          name: type
          schema:
            type: string
          example: mandatory, optional, or personal.
          required: false
        - in: query
          name: page_limit
          schema:
            type: integer
          example: default is 10.
          required: false
        - in: query
          name: target
          schema:
            type: integer
          description: 0 -> unconfirmed event || 1 -> confirmed event || 2 -> both confirmed and unconfirmed || 3 -> created events
          required: fasle
    responses:
        200:
            content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: '#/components/schemas/Event'
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
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")

    # get user table
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    page_limit: int = request.args.get("page_limit", type=int, default=100)
    target: int = request.args.get("target", type=int, default=1)

    if "type" in request.args:
        type: str = request.args.get("type", type=str)
        if target == 0:
            docs: list = (
                db.collection("Scheduled-Events")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("invitees_dod", "array_contains", user.get("dod"))
                .where("type", "==", type)
                .limit(page_limit)
                .stream()
            )
        elif target == 1:
            docs: list = (
                db.collection("Scheduled-Events")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("confirmed_dod", "array_contains", user.get("dod"))
                .where("type", "==", type)
                .limit(page_limit)
                .stream()
            )
        elif target == 2:
            docs1: list = (
                db.collection("Scheduled-Events")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("invitees_dod", "array_contains", user.get("dod"))
                .where("type", "==", type)
                .limit(page_limit)
                .stream()
            )
            docs2: list = (
                db.collection("Scheduled-Events")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("confirmed_dod", "array_contains", user.get("dod"))
                .where("type", "==", type)
                .limit(page_limit)
                .stream()
            )
            docs = chain(docs1, docs2)
        else:
            docs: list = (
                db.collection("Scheduled-Events")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("author", "==", uid)
                .where("type", "==", type)
                .limit(page_limit)
                .stream()
            )
    else:
        if target == 0:
            docs: list = (
                db.collection("Scheduled-Events")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("invitees_dod", "array_contains", user.get("dod"))
                .limit(page_limit)
                .stream()
            )
        elif target == 1:
            docs: list = (
                db.collection("Scheduled-Events")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("confirmed_dod", "array_contains", user.get("dod"))
                .limit(page_limit)
                .stream()
            )
        elif target == 2:
            docs1: list = (
                db.collection("Scheduled-Events")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("invitees_dod", "array_contains", user.get("dod"))
                .limit(page_limit)
                .stream()
            )
            docs2: list = (
                db.collection("Scheduled-Events")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("confirmed_dod", "array_contains", user.get("dod"))
                .limit(page_limit)
                .stream()
            )
            docs = chain(docs1, docs2)
        else:
            docs: list = (
                db.collection("Scheduled-Events")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("author", "==", uid)
                .limit(page_limit)
                .stream()
            )

    events: list = []
    for doc in docs:
        temp: dict = doc.to_dict()
        del temp["confirmed_dod"]
        del temp["invitees_dod"]
        events.append(temp)

    return jsonify(events), 200


@events.get("/get_event/<event_id>")
@check_token
def get_event(event_id: str) -> Response:
    """
    Get the event from database.
    ---
    tags:
        - event
    summary: Gets the event
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
    responses:
        200:
            content:
                application/json:
                    schema:
                        $ref: '#/components/schemas/Event'
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
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")

    # get user table
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    # get the user table
    event_ref = db.collection("Scheduled-Events").document(event_id).get()
    if event_ref.exists == False:
        return NotFound("The event was not found")
    event: dict = event_ref.to_dict()

    # only the author and the invitees can access the event
    if (
        event.get("author") != uid
        and user.get("dod") not in event.get("confirmed_dod")
        and user.get("dod") not in event.get("invitees_dod")
    ):
        return Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    if event.get("author") != uid:
        del event["confirmed_dod"]
        del event["invitees_dod"]

    return jsonify(event), 200


@events.post("/confirm_event/<event_id>")
@check_token
def confirm_event(event_id: str) -> Response:
    """
    Confirm the event invitation.
    ---
    tags:
        - event
    summary: Confirm event
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
    responses:
        201:
            description: Confirmed event
        400:
            description: Bad request
        401:
            description: Unauthorized - the provided token is not valid
        404:
            description: NotFound
        500:
            description: Internal API Error
    """
    # check tokens and get uid from token
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")
    # get user table
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    # fetch event data from firestore
    event_ref = db.collection("Scheduled-Events").document(event_id)
    if not event_ref.get().exists:
        return NotFound("The event was not found")
    event: dict = event_ref.get().to_dict()

    if not user.get("dod") in event.get("invitees_dod"):
        return BadRequest("User are not in the invite list")

    event_ref.update(
        {
            "invitees_dod": firestore.ArrayRemove([user.get("dod")]),
            "confirmed_dod": firestore.ArrayUnion([user.get("dod")]),
        }
    )

    # notify users
    try:
        create_notification(
            notification_type="confirm event",
            type=event.get("type"),
            sender=uid,
            id=event.get("event_id"),
            receiver_uid=event.get("author"),
            sender_name=user.get("name"),
        )
    except:
        return NotFound("The invitee was not found")

    return Response("Confirmed event", 200)
