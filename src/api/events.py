# -*- coding: utf-8 -*
"""
    src.api.events
    ~~~~~~~~~~~~~~
    Functions:
        create_event()
        update_event()
        get_all_events()
        get_event()
        get_recent_events()
        register_event()
        change_status()
"""
from datetime import datetime
from firebase_admin import auth, firestore
from flask import Response, jsonify, request
from uuid import uuid4
from werkzeug.exceptions import BadRequest, NotFound, Unauthorized

from src.api import Blueprint
from src.api.notifications import create_notification
from src.common.database import db
from src.common.decorators import admin_only, check_token

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

    # Exceptions
    if "title" not in data or data.get("title").isspace():
        return BadRequest("Missing the title")
    if "starttime" not in data or data.get("starttime").isspace():
        return BadRequest("Missing the starttime")
    if "endtime" not in data or data.get("endtime").isspace():
        return BadRequest("Missing the endtime")
    if "type" not in data or data.get("type").isspace():
        return BadRequest("Missing the type")
    if "period" not in data or not isinstance(data.get("period"), bool):
        return BadRequest("Missing the period")
    if "invitees_dod" not in data or isinstance(data.get("invitees_dod"), list):
        return BadRequest("Missing the invitees_dod")
    if "organizer" not in data or data.get("organizer").isspace():
        return BadRequest("Missing the organizer")
    if "description" not in data or data.get("description").isspace():
        return BadRequest("Missing the description")

    entry: dict = dict()
    try:
        entry["starttime"] = datetime.fromisoformat(data.get("starttime"))
    except:
        return BadRequest("The starttime formate should be datetime type")
    try:
        entry["endtime"] = datetime.fromisoformat(data.get("endtime"))
    except:
        return BadRequest("The endtime formate should be datetime type")
    entry["author"] = uid
    entry["event_id"] = str(uuid4())
    entry["timestamp"] = firestore.SERVER_TIMESTAMP
    entry["title"] = data.get("title")
    # entry["starttime"] = data.get("starttime")
    # entry["endtime"] = data.get("endtime")
    entry["type"] = data.get("type")
    entry["period"] = data.get("period")
    entry["invitees_dod"] = data.get("invitees_dod")
    entry["confirmed_dod"] = []
    entry["organizer"] = data.get("organizer")
    entry["description"] = data.get("description")

    # write to Firestore DB
    db.collection("Scheduled-Events").document(entry.get("event_id")).set(entry)

    # notify users
    try:
        for dod in data.get("invitees_dod"):
            create_notification("create event", None, uid, dod, None)
    except:
        return NotFound("The invitee was not found")

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

    # if event does not exists
    if not event_ref.get().exists:
        return NotFound("The event not found")

    # Only the event user could delete the event
    if event.get("author") != uid:
        return Response(
            "The user is not authorized to retrieve this content", 401
        )

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

    # if event does not exists
    if not event_ref.get().exists:
        return NotFound("The event was not found")

    # Only the event organizer and admin could update the event
    if event.get("author") != uid and decoded_token.get("admin") != True:
        return Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    # update event by given paramter
    if "starttime" in data:
        try:
            event_ref.update(
                {"starttime": datetime.fromisoformat(data.get("starttime"))}
            )
        except:
            return BadRequest("The starttime formate should be datetime type")

    if "endtime" in data:
        try:
            event_ref.update(
                {"endtime": datetime.fromisoformat(data.get("endtime"))}
            )
        except:
            return BadRequest("The endtime formate should be datetime type")

    if "period" in data and not data.get("period").isspace():
        event_ref.update({"period": data.get("period")})
    if "type" in data and not data.get("type").isspace():
        event_ref.update({"type": data.get("type")})
    if "title" in data and not data.get("title").isspace():
        event_ref.update({"title": data.get("title")})
    if "description" in data and not data.get("description").isspace():
        event_ref.update({"description": data.get("description")})
    if "organizer" in data and not data.get("organizer").isspace():
        event_ref.update({"organizer": data.get("organizer")})

    if "add_invitees" in data and data.get("add_invitees"):
        event_ref.update(
            {"invitees_dod": firestore.ArrayUnion(data.get("add_invitees"))}
        )

    if "remove_invitees" in data and data.get("remove_invitees"):
        event_ref.update(
            {"invitees_dod": firestore.ArrayRemove(data.get("remove_invitees"))}
        )

    return Response(response="Event updated", status=200)


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

    page_limit: int = request.args.get("page_limit", type=int, default=10)

    if "type" in request.args:
        type: str = request.args.get("type", type=str)
        docs: list = (
            db.collection("Scheduled-Events")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .where("confirmed_dod", "array_contains", user.get("dod"))
            .where("type", "==", type)
            .limit(page_limit)
            .stream()
        )
    else:
        docs: list = (
            db.collection("Scheduled-Events")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .where("confirmed_dod", "array_contains", user.get("dod"))
            .limit(page_limit)
            .stream()
        )

    events: list = []
    for doc in docs:
        events.append(doc.to_dict())

    return jsonify(events), 200


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
            "invitees_dod": firestore.ArrayRemove(user.get("dod")),
            "confirmed_dod": firestore.ArrayUnion(user.get("dod")),
        }
    )

    return Response("Confirmed event", 200)
