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
"""
from firebase_admin import auth, firestore
from flask import Response, jsonify, request
from uuid import uuid4
from werkzeug.exceptions import Unauthorized, BadRequest
import ast

from src.api import Blueprint
from src.common.database import db
from src.common.decorators import check_token

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

    data: dict = request.get_json()
    data["author"] = uid
    data["id"] = f"{uuid4()}"
    data["timestamp"] = firestore.SERVER_TIMESTAMP

    # Write to Firestore DB
    db.collection("Scheduled-Events").add(data)

    # Return Response 201 for successfully creating a new resource
    return Response(response="Event added", status=201)


@events.delete("/delete_event/<event_id>")
def delete_event(event_id: str) -> Response:
    """
    Delete an event from Firebase.
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
            description: File deleted
        404:
            description: Delete failed
    """
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)

    uid: str = decoded_token["uid"]

    try:
        docs = (
            db.collection("Scheduled-Events")
            .where("id", "==", event_id)
            .where("author", "==", uid)
            .stream()
        )

        # Delete document
        for doc in docs:
            # Store document id and use it to locate the specific document to delete
            doc_id = doc.id
            db.collection("Scheduled-Events").document(doc_id).delete()

        return Response(response="Event deleted", status=200)
    except:
        return Response(response="Delete failed", status=400)


@events.post("/update_event")
@check_token
def update_event() -> Response:
    """
    Updates an event that has already been created.
    ---
    tags:
        - event
    summary: Updates event
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
        description: Updated event object
        required: true
    responses:
        201:
            description: OK
        400:
            description: Bad request.
    """
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)

    try:
        data: dict = request.get_json()
        event_data: dict = data["data"]
        event_id: str = event_data["id"]
        uid: str = decoded_token["uid"]

        docs: list = (
            db.collection("Scheduled-Events")
            .where("id", "==", event_id)
            .where("author", "==", uid)
            .stream()
        )

        # Try to get reference to event document from Firestore
        for doc in docs:
            doc_id = doc.id

            # Update document
            db.collection("Scheduled-Events").document(doc_id).update(
                {
                    "data.eventDate": event_data["eventDate"],
                    "data.eventDescription": event_data["eventDescription"],
                    "data.eventOrganizer": event_data["eventOrganizer"],
                    "data.eventTitle": event_data["eventTitle"],
                }
            )

        return Response(response="Event edited", status=200)
    except:
        return Response(response="Edit failed", status=400)


@events.get("/get_event/<event_id>")
@check_token
def get_event() -> Response:
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
          description: The event id
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
    event_id = request.args.get("event")

    try:
        doc = db.collection("Scheduled-Events").document(event_id).get()
        if doc.exists:
            return jsonify(doc.to_dict()), 200

        return Response(response="Event no longer exist", status=400)
    except:
        return Response(response="Failed to retrieve", status=400)


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
                        type: object
        404:
            description: The file with the given filename was not found
        500:
            description: Internal API Error
    """

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
                        type: object
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
