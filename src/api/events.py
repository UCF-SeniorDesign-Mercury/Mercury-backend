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

from src.api import Blueprint
from src.common.database import db
from src.common.decorators import admin_only, check_token

events: Blueprint = Blueprint("events", __name__)


@events.post("/create_event")
@check_token
@admin_only
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
                    $ref: '#/components/schemas/EventData'
        description: Created event object
        required: true
    responses:
        201:
            description: Event created
        400:
            description: Failed to add an event
        401:
            description: Unauthorized - the provided token is not valid
    """
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token["uid"]

    # check user permission

    # add more initial information
    data: dict = request.get_json()
    data["author"] = uid
    data["id"] = str(uuid4())
    data["timestamp"] = firestore.SERVER_TIMESTAMP
    data["participators"] = []
    data["status"] = 1

    # write to Firestore DB
    db.collection("Scheduled-Events").document(data["id"]).set(data)

    # return Response 201 for successfully creating a new resource
    return Response(response="Event added", status=201)


@events.delete("/delete_event/<event_id>")
@check_token
# @admin_only
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
        401:
            description: The user is not authorized to retrieve this content
        404:
            description: The event not found
    """
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token["uid"]

    # fetch event data from firestore
    event_ref = db.collection("Scheduled-Events").document(event_id)
    event = event_ref.get().to_dict()

    # if enevt does not exists
    if not event_ref.get().exists:
        return Response("The event not found", 404)

    # # Future function: Only the event organisor or the admin could delete the event
    # if event["author"] != uid and decoded_token.get("admin") != True:
    #     return Response(
    #         "The user is not authorized to retrieve this content", 401
    #     )

    event_ref.delete()

    return Response(response="Event deleted", status=200)


@events.put("/update_event")
@check_token
@admin_only
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
        401:
            description: The user is not authorized to retrieve this content
        404:
            description: The event not found
    """
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    data: dict = request.get_json()
    event_id: str = data["id"]
    uid: str = decoded_token["uid"]

    # fetch event data from firestore
    event_ref = db.collection("Scheduled-Events").document(event_id)
    event = event_ref.get().to_dict()

    # if enevt does not exists
    if not event_ref.get().exists:
        return Response("The event not found", 404)

    # # Future FUnction: Only the event organisor or the admin could delete the event
    # if event["author"] != uid and decoded_token.get("admin") != True:
    #     return Response(
    #         "The user is not authorized to retrieve this content", 401
    #     )

    # update event by given paramter
    if "date" in event:
        event_ref.update({"date": data["date"]})
    if "title" in event:
        event_ref.update({"title": data["title"]})
    if "description" in event:
        event_ref.update({"description": data["description"]})
    if "organizer" in event:
        event_ref.update({"organizer": data["organizer"]})

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
        404:
            description: The file with the given filename was not found
        500:
            description: Internal API Error
    """
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)

    # fetch the event data from firestore
    doc = db.collection("Scheduled-Events").document(event_id).get()

    # event not found exception
    if not doc.exists:
        return Response(response="Event no longer exist", status=404)

    return jsonify(doc.to_dict()), 200


@events.get("/get_recent_events")
@check_token
def get_recent_events() -> Response:
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
    responses:
        200:
            content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: '#/components/schemas/Event'
        404:
            description: The file with the given filename was not found
        500:
            description: Internal API Error
    """
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)

    try:
        docs: list = (
            db.collection("Scheduled-Events")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(10)
            .stream()
        )

        events: list = []
        for doc in docs:
            events.append(doc.to_dict())

        return jsonify(events), 200

    except:
        return Response(response="Failed event retrieved", status=400)


@events.get("/get_next_event_page")
@check_token
def get_next_event_page() -> Response:
    """
    Get next 10 events from Firebase.
    ---
    tags:
        - event
    summary: Gets next 10 events by pass the last event id.
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
        - in: header
          name: ID
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
        404:
            description: Failed event retrieved
    """
    try:
        document: list = []
        events: list = []

        # Get ID of last event from client-side
        event_id: str = request.headers["ID"]

        # Get reference to document with that ID
        last_ref = (
            db.collection("Scheduled-Events")
            .where("id", "==", event_id)
            .stream()
        )
        for doc in last_ref:
            document.append(doc.to_dict())

        # Get the next batch of documents that come after the last document we received a reference to before
        docs = (
            db.collection("Scheduled-Events")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .start_after(document[0])
            .limit(10)
            .stream()
        )
        for doc in docs:
            events.append(doc.to_dict())

        return jsonify(events), 200

    except:
        return Response(response="Failed event retrieved", status=400)


@events.put("/register_event/<event_id>")
@check_token
def register_event(event_id: str) -> Response:
    """
    User register an exists event
    ---
    tags:
        - event
    summary: Register event
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
        - in: path
          name: event_id
          schema:
            type: string
          required: true
    responses:
        200:
            description: Registered for the event
        404:
            description: The event no longer exists
        403:
            description: The event close for register
    """
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token["uid"]

    # fetch event data from firestore
    event_ref = db.collection("Scheduled-Events").document(event_id)
    event = event_ref.get().to_dict()

    # if enevt does not exists
    if not event_ref.get().exists:
        return Response("The event no longer exists", 404)
    # Only the event organisor or the admin could delete the event
    if event["status"] > 1:
        return Response("The event close for register", 403)

    # Future function: candidates_filter nice to have

    # add the user uid to the participators array
    event_ref.update({"participators": firestore.ArrayUnion([uid])})

    # update the user table
    user_ref = db.collection(u"User").document(uid)
    user_ref.update({u"registeredEvents": firestore.ArrayUnion([event_id])})

    return Response(response="Registered the event", status=200)


@events.put("/cancel_register/<event_id>")
@check_token
def cancel_register(event_id: str) -> Response:
    """
    User register an exists event
    ---
    tags:
        - event
    summary: Cancel registered event
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
        - in: path
          name: event_id
          schema:
            type: string
          required: true
    responses:
        200:
            description: Cancel register for the event
        404:
            description: The event no longer exists
    """
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token["uid"]

    # fetch event data from firestore
    event_ref = db.collection("Scheduled-Events").document(event_id)
    event = event_ref.get().to_dict()

    # if enevt does not exists
    if not event_ref.get().exists:
        return Response("The event no longer exists", 404)

    # add the user uid to the participators array
    event_ref.update({"participators": firestore.ArrayRemove([uid])})

    # update the user table
    user_ref = db.collection(u"User").document(uid)
    user_ref.update({u"registeredEvents": firestore.ArrayRemove([event_id])})

    return Response(response="Canceled the reservation", status=200)


@events.put("/change_status")
@check_token
@admin_only
def change_status():
    """
    Change the status of an event from Firebase Storage.
    ---
    tags:
        - event
    summary: Change the status
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
                    $ref: '#/components/schemas/EventStatus'
    responses:
        200:
            description: Status changed
        400:
            description: Unsupported decision type
        401:
            description: The user is not authorized to retrieve this content
        404:
            description: The file with the given filename was not found
        500:
            description: Internal API Error
    """
    # check tokens and get uid from token
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    reviewer: str = decoded_token["uid"]
    data: dict = request.get_json()

    # exceptions
    if data["decision"] < 1 or data["decision"] > 6:
        return Response("Unsupported decision type", 400)

    # fetch the file data from firestore
    event_ref = db.collection(u"Scheduled-Events").document(data["event_id"])
    event = event_ref.get().to_dict()

    # # Future function: Only the reviewer, and admin have access to change the status of the file
    # if reviewer != event["author"] and decoded_token.get("admin") != True:
    #     raise Response(
    #         "The user is not authorized to retrieve this content", 401
    #     )

    event_ref.update({u"status": data["decision"]})

    return Response("Status changed", 200)
