from firebase_admin import auth, firestore
from flask import Blueprint, Response, jsonify, request
from uuid import uuid4
import ast

from common.database import db
from common.decorators import check_token

events: Blueprint = Blueprint('events', __name__)


@events.route('/addEvent', methods=['POST'])
@check_token
def addEvent() -> Response:
    """
    Firestore DB 'write' for creating new event in the Schedule module

    Returns:
        Response of 201 for successfully adding event to DB
    """
    # Check user access levels
    # Decode token to obtain user's firebase id
    token: str = request.headers['Authorization']
    decoded_token: dict = auth.verify_id_token(token)

    uid: str = decoded_token['uid']

    # If exists, extract data from request
    try:
        data: dict = request.get_json()
        data['author'] = uid
        data['id'] = f'{uuid4()}'
        data['timestamp'] = firestore.SERVER_TIMESTAMP

        # Write to Firestore DB
        db.collection(u'Scheduled-Events').add(data)

        # Return Response 201 for successfully creating a new resource
        return Response(response="Event added", status=201)

    except:
        return Response(response="Failed to add event", status=400)


@events.route('/deleteEvent', methods=['DELETE'])
def deleteEvent() -> Response:
    """
    Firestore DB 'delete' for removing an event in the Schedule module

    Returns:
        Response of 200 for successfully removing specified event to delete in DB
    """

    try:
        data: bytes = request.get_data()
        decode_data: str = data.decode("UTF-8")

        # Convert bytes type to dictionary
        new_data = ast.literal_eval(decode_data)

        # Try to get reference event document from Firestore
        event_id: str = new_data["id"]
        docs = db.collection(
            u'Scheduled-Events').where(u'id', u'==', event_id).stream()

        # Delete document
        for doc in docs:
            # Store document id and use it to locate the specific document to delete
            doc_id = doc.id
            db.collection(u'Scheduled-Events').document(doc_id).delete()

        return Response(response="Event deleted", status=200)
    except:
        return Response(response="Delete failed", status=400)


@events.route('/editEvent', methods=['POST'])
@check_token
def editEvent() -> Response:
    """
    Firestore DB 'write' for updating a current event in the Schedule module

    Returns:
        Response of 200 for successfully editing the specified event 
    """
    try:
        data: dict = request.get_json()
        event_data: dict = data["data"]
        event_id: str = event_data["id"]

        docs: list = db.collection(
            u'Scheduled-Events').where(u'id', u'==', event_id).stream()

        # Try to get reference to event document from Firestore
        for doc in docs:
            doc_id = doc.id

            # Update document
            db.collection(u'Scheduled-Events').document(doc_id).update({
                u'data.eventDate': event_data["eventDate"],
                u'data.eventDescription': event_data["eventDescription"],
                u'data.eventOrganizer': event_data["eventOrganizer"],
                u'data.eventTitle': event_data["eventTitle"]
            })

        return Response(response="Event edited", status=200)
    except:
        return Response(response="Edit failed", status=400)


@events.route('/getEvent', methods=['GET'])
@check_token
def getEvent() -> Response:
    """
    Firestore DB 'read' for specified event in the Schedule module

    Returns:
        An event of the specified event id passed from client side
    """
    event_id = request.args.get('event')
    event: list = []

    try:
        doc = db.collection(u'Scheduled-Events').document(event_id).get()
        if doc.exists:
            return jsonify(doc.to_dict()), 200

        return Response(response="Event no longer exist", status=400)
    except:
        return Response(response="Failed to retrieve", status=400)


@events.route('/getRecentEvents', methods=['GET'])
@check_token
def getRecentEvents() -> Response:
    """
    Retrieve the latest initial upcoming and recent events

    Returns:
        Jsonified list of the latest 10 events from Firestore DB
    """

    try:
        docs: list = db.collection(u'Scheduled-Events').order_by(u'timestamp',
                                                                 direction=firestore.Query.DESCENDING).limit(10).stream()

        events: list = []
        for doc in docs:
            events.append(doc.to_dict())

        return jsonify(events), 200

    except:
        return Response(response="Failed event retrieved", status=400)


@events.route('/getNextEventPage', methods=['GET'])
@check_token
def getNextEventPage() -> Response:
    """
    Retrieves the next page of latest events for pagination. Picks off where /getRecentEvents ended

    Returns;
        Jsonified list of the next latest 10 events from Firestore DB
    """
    try:
        document: list = []
        events: list = []

        # Get ID of last event from client-side
        event_id: str = request.headers['ID']

        # Get reference to document with that ID
        last_ref = db.collection(
            u'Scheduled-Events').where(u'id', u'==', event_id).stream()
        for doc in last_ref:
            document.append(doc.to_dict())

        # Get the next batch of documents that come after the last document we received a reference to before
        docs = db.collection(u'Scheduled-Events').order_by(u'timestamp',
                                                           direction=firestore.Query.DESCENDING).start_after(document[0]).limit(10).stream()
        for doc in docs:
            events.append(doc.to_dict())

        return jsonify(events), 200

    except:
        return Response(response="Failed event retrieved", status=400)
