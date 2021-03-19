from firebase_admin import credentials, auth, firestore, initialize_app
from flask import Flask, Response, request, jsonify
from functools import wraps
from uuid import uuid4
from decorators import check_token

app = Flask(__name__)
cred = credentials.Certificate('key.json')
firebase_app = initialize_app(cred)
db = firestore.client()


@app.route('/addEvent', methods=['POST'])
@check_token
def addEvent():
    """
    Firestore DB 'write' for creating new event in the Schedule module
    """
    # Check user access levels
    
    # Decode token to obtain user's firebase id
    token = request.headers['Authorization']
    decoded_token = auth.verify_id_token(token)
    
    uid = decoded_token['uid']

    # If exists, extract data from request
    try:
        data = request.get_json()
        data['author'] = uid
        data['id'] = f'{uuid4()}'
        data['timestamp'] = firestore.SERVER_TIMESTAMP

        # Write to Firestore DB
        db.collection(u'Scheduled-Events').add(data)

        # Return Response 201 for successfully creating a new resource
        return Response(response="Event added", status=201)

    except:
        return Response(response="Failed to add event", status=400)


@app.route('/deleteEvent', methods=['DELETE'])
@check_token
def deleteEvent():

    # Check user access levels

    # Try to get reference event document from Firestore

    # Delete document

    return Response(response="Event deleted", status=200)


@app.route('/editEvent', methods=['POST'])
@check_token
def editEvent():

    # Check user access levels

    # Try to get reference to event document from Firestore

    # Update document

    return Response(response="Event edited", status=200)


@app.route('/getEvent', methods=['GET'])
@check_token
def getEvent():
    """
    Only retrieve events created by this user
    """
    return Response(response="Event retrieved", status=200)


@app.route('/getAllEvents', methods=['GET'])
#@check_token
def getAllEvents():
    """
    Retrieve all upcoming and recent events
    """

    try:
        docs = db.collection(u'Scheduled-Events').order_by(u'timestamp', direction=firestore.Query.DESCENDING).limit(20).stream()
        

        events = []
        for doc in docs:
            events.append(doc.to_dict())
        
        return jsonify(events), 200

    except:
        return Response(response="Failed event retrieved", status=200)


@app.route('/grantRole')
@check_token
def grantRole():
    """
    Upon newly registering a user, they are granted a role if their email used is matched to one in the database. 
    """

    # Decode token to obtain user's firebase id
    token = request.headers['Authorization']
    decoded_token = auth.verify_id_token(token)
    
    email = decoded_token['email']
    uid = decoded_token['uid']

    # Reference to roles document
    doc_ref = db.collection(u'Roles').document(u'roleList')
    doc = doc_ref.get()

    roles = {}
    if doc.exists:
        roles = doc.to_dict()['role']

    try:
        auth.set_custom_user_claims(uid, {roles[email]: True})
        return Response(response="Successfully added role", status=200)
    except:
        return jsonify({"Message": "Not assigned a role"})


# 
if __name__ == '__main__':
    app.run(host='192.168.1.13', debug=True)