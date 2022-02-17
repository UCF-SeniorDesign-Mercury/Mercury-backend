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
        get_next_event_page()
        register_event()
        update_event()
        change_status()
"""
from firebase_admin import auth, firestore
from flask import Response, jsonify, request
from uuid import uuid4
from werkzeug.exceptions import BadRequest, NotFound, Unauthorized

from src.api import Blueprint
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

    entry: dict = dict()

    entry["author"] = uid
    entry["event_id"] = str(uuid4())
    entry["timestamp"] = firestore.SERVER_TIMESTAMP
    entry["title"] = data.get("title")
    entry["starttime"] = data.get("starttime")
    entry["endtime"] = data.get("endtime")
    entry["type"] = data.get("type")
    entry["period"] = data.get("period")
    entry["organizer"] = data.get("organizer")
    entry["description"] = data.get("description")

    # write to Firestore DB
    db.collection("Scheduled-Events").document(data["id"]).set(entry)

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
    if event["author"] != uid:
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
        415:
            description: Unsupported media type.
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

    # Only the user could delete the event
    if event.get("author") != uid:
        return Unauthorized(
            "The user is not authorized to retrieve this content", 401
        )

    # update event by given paramter
    if "starttime" in event:
        event_ref.update({"starttime": data.get("starttime")})
    if "endtime" in event:
        event_ref.update({"endtime": data.get("endtime")})
    if "period" in event:
        event_ref.update({"period": data.get("period")})
    if "type" in event:
        event_ref.update({"type": data.get("type")})
    if "title" in event:
        event_ref.update({"title": data.get("title")})
    if "description" in event:
        event_ref.update({"description": data.get("description")})
    if "organizer" in event:
        event_ref.update({"organizer": data.get("organizer")})

    return Response(response="Event updated", status=200)


@events.get("/get_event/<event_id>")
@check_token
def get_event(event_id: str) -> Response:
    """
    Get an event from database.
    ---
    tags:
        - event
    summary: Gets an event
    parameters:
        - in: path
          name: event_id
          schema:
              type: string
          required: true
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

    # fetch the event data from firestore
    event_ref = db.collection("Scheduled-Events").document(event_id)
    event: dict = event_ref.get().to_dict()

    # Only the user could get the event
    if event.get("author") != uid:
        return Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    # event not found exception
    if not event_ref.get().exists:
        return NotFound("Event no longer exist")

    return jsonify(event), 200


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
          name: status
          schema:
            type: boolean
          example: true for comming events, false for past events.
          required: false
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

    page_limit: str = request.args.get("page_limit", type=int, default=10)

    docs: list = (
        db.collection("Scheduled-Events")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .where("author", "==", uid)
        .limit(page_limit)
        .stream()
    )

    events: list = []
    for doc in docs:
        events.append(doc.to_dict())

    return jsonify(events), 200
