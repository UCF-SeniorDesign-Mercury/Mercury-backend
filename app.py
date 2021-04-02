from firebase_admin import credentials, auth, firestore, initialize_app
from flask import Flask, Response, request, jsonify
from functools import wraps
from uuid import uuid4
from decorators import check_token
import ast

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
def deleteEvent():
 
    try:
        data = request.get_data()
        decode_data = data.decode("UTF-8")

        # Convert bytes type to dictionary
        new_data = ast.literal_eval(decode_data)

        # Try to get reference event document from Firestore
        event_id = new_data["id"]
        docs = db.collection(u'Scheduled-Events').where(u'id', u'==', event_id).stream()

        # Delete document
        for doc in docs:
            # Store document id and use it to locate the specific document to delete
            doc_id = doc.id
            db.collection(u'Scheduled-Events').document(doc_id).delete()


        return Response(response="Event deleted", status=200)
    except:
        return Response(response="Delete failed", status=400)


@app.route('/editEvent', methods=['POST'])
@check_token
def editEvent():
    
    try:
        data = request.get_json()
        event_data = data["data"]
        event_id = event_data["id"]

        docs = db.collection(u'Scheduled-Events').where(u'id', u'==', event_id).stream()

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


@app.route('/getEvent', methods=['GET'])
@check_token
def getEvent():
    """
    Only retrieve events created by this user
    """
    return Response(response="Event retrieved", status=200)


@app.route('/getRecentEvents', methods=['GET'])
@check_token
def getRecentEvents():
    """
    Retrieve all upcoming and recent events
    """

    try:
        docs = db.collection(u'Scheduled-Events').order_by(u'timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
        

        events = []
        for doc in docs:
            events.append(doc.to_dict())
        
        return jsonify(events), 200

    except:
        return Response(response="Failed event retrieved", status=400)



@app.route('/getNextEventPage', methods=['GET'])
@check_token
def getNextEventPage():
    """
    Retrieve more events for pagination. Picks off where /getRecentEvents ended
    """
    try:
        document = []
        events = []

        event_id = request.headers['ID']
        
        last_ref = db.collection(u'Scheduled-Events').where(u'id', u'==', event_id).stream()      
        for doc in last_ref:
            document.append(doc.to_dict())
        
        docs = db.collection(u'Scheduled-Events').order_by(u'timestamp', direction=firestore.Query.DESCENDING).start_after(document[0]).limit(10).stream()     
        for doc in docs:
            events.append(doc.to_dict())

        return jsonify(events), 200

    except:
        return Response(response="Failed event retrieved", status=400)


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
    doc = db.collection(u'Roles').document(u'roleList').get()
    
    # Get role map of predefined users to roles
    roles = doc.to_dict()['role']

    try:
        auth.set_custom_user_claims(uid, {roles[email]: True})
        return Response(response="Successfully added role", status=200)
    except:
        return jsonify({"Message": "Not assigned a role"})




@app.route('/createRole', methods=['POST'])
@check_token
def createRole():
    """
    Creating a new custom role globally for the client side application
    """
    token = request.headers['Authorization']
    decoded_token = auth.verify_id_token(token)

    if decoded_token['admin'] is True:

        data = request.get_json()["data"]
        role = data['roleName']
        level = data['level']

        doc_ref = db.collection(u'Roles').document(u'allRoles')
        doc_ref.set({
            u'roles': {
                role:level
            }
        }, merge=True)

        doc_ref.update({u'roleArray': firestore.ArrayUnion([role])})
        

        return jsonify({"Message": "Complete"}), 200
    else:
        return jsonify({"Message": "Unauthorized"}), 401


@app.route('/getAllRoles', methods=['GET'])
@check_token
def getAllRoles():
    """
    Retrieve all custom roles created by admins to the app
    """
    try:
        doc = db.collection(u'Roles').document(u'allRoles').get()
        data = doc.to_dict()['roleArray']
        return jsonify(data)
    except:
        return jsonify({"Message": "Unauthorized"}), 401


@app.route('/assignRole', methods=['POST'])
@check_token
def assignRole():
    """
    Assign a custom role to a user
    """
    token = request.headers['Authorization']
    decoded_token = auth.verify_id_token(token)

    if decoded_token['admin'] is True:

        doc = db.collection(u'Roles').document(u'allRoles').get()
        roles_dict = doc.to_dict()['roles']

        data = request.get_json()['data']
        email = data['email']
        role = data['role']
        level = roles_dict[role]

        try:
            user = auth.get_user_by_email(email)
            current_custom_claims = user.custom_claims

            # User has no previous role in their custom claims
            if current_custom_claims is None:
                auth.set_custom_user_claims(user.uid, {
                    role: True,
                    "accessLevel": level
                })

            # User has a role set previously
            else:              
                if current_custom_claims["accessLevel"] >= level:
                    current_custom_claims[role] = True
                else:
                    current_custom_claims["accessLevel"] = level
                    current_custom_claims[role] = True
                
                auth.set_custom_user_claims(user.uid, current_custom_claims) 

            return jsonify({"Message": "Complete"}), 200
        except:
            return jsonify({"Message": "Email doesn't exist"}), 400



if __name__ == '__main__':
    app.run(host='192.168.1.13', debug=True)