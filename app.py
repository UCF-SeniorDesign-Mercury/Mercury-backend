from firebase_admin import credentials, auth, firestore, initialize_app
from flask import Flask, Response, request, jsonify
from functools import wraps
from uuid import uuid4
import ast

from decorators import check_token, admin_only
from helpers import send_invite_email

app = Flask(__name__)
cred = credentials.Certificate('key.json')
firebase_app = initialize_app(cred)
db = firestore.client()


@app.errorhandler(404)
def page_not_found(e):
    return jsonify({'Message': "Endpoint doesn't exist"})


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
    event_id = request.args.get('event')
    event = []

    try:
        doc = db.collection(u'Scheduled-Events').document(event_id).get()
        if doc.exists:
            return jsonify(doc.to_dict()), 200

        return Response(response="Event no longer exist", status=400)
    except:
        return Response(response="Failed to retrieve", status=400)


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

        # Get ID of last event from client-side
        event_id = request.headers['ID']
        
        # Get reference to document with that ID
        last_ref = db.collection(u'Scheduled-Events').where(u'id', u'==', event_id).stream()      
        for doc in last_ref:
            document.append(doc.to_dict())
        
        # Get the next batch of documents that come after the last document we received a reference to before
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
    role_to_assign = roles[email]

    try:
        auth.set_custom_user_claims(uid, {role_to_assign: True})

        # Map this new entry to roles_to_user
        doc_allRoles = db.collection(u'Roles').document(u'allRoles')
        doc_allRoles.set({
            u'roles_to_user': {
                role_to_assign: firestore.ArrayUnion([email])
            }
        }, merge=True)

        return Response(response="Successfully added role", status=200)
    except:
        return jsonify({"Message": "Not assigned a role"})




@app.route('/createRole', methods=['POST'])
@check_token
@admin_only
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
@admin_only
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
            return jsonify({"Error": "Email doesn't exist"}), 400



@app.route('/inviteRole', methods=['POST'])
@check_token
def inviteRole():
    data = request.get_json()['data']
    role = data['role']
    event_id = data['event_id']
    
    # Retrieve map of roles to user from DB
    role_docs = db.collection(u'Roles').document(u'allRoles').get()
    roles_to_user = role_docs.to_dict()['roles_to_user']

    # Retrieve list of emails that have a specific from the map
    emails = roles_to_user[role]

    event_docs = db.collection(u'Scheduled-Events').where(u'id', u'==', event_id).stream()
    for doc in event_docs:
        doc_id = doc.id
        send_invite_email(emails, doc_id)


    return jsonify({"Message": "Complete"}), 200




@app.route('/revokeRole', methods=['POST'])
@check_token
@admin_only
def revokeRole():
    """
    Remove a role from a specificed user. Level is also updated if it's affected by the removal of role
    """
    data = request.get_json()['data']
    email = data['email']
    role_to_remove = data['role']
    new_level = 0

    user = auth.get_user_by_email(email)
    current_custom_claims = user.custom_claims
    try:        
        if current_custom_claims[role_to_remove] is True:
            del current_custom_claims[role_to_remove]
            all_keys = list(current_custom_claims.keys())
            
            # Get map of roles to level from DB
            doc = db.collection(u'Roles').document(u'allRoles').get()
            roles_map = doc.to_dict()['roles']
        
            for key in all_keys:
                if key != "accessLevel":
                    role_level = roles_map[key]

                    # if current level status is equal to one of user's existing roles' level
                    if role_level == current_custom_claims['accessLevel']:
                        auth.set_custom_user_claims(user.uid, current_custom_claims)
                        return jsonify({"Message": "Complete"})
                    
                    if role_level > new_level:
                        new_level = role_level

            current_custom_claims['accessLevel'] = new_level
            auth.set_custom_user_claims(user.uid, current_custom_claims)

        return jsonify({"Message": "Complete"}), 200
    except ValueError:
        return jsonify({'Error': 'Specified user ID or the custom claims are invalid'})
    except:
        return jsonify({'Error': 'User has no role to remove'})
    

if __name__ == '__main__':
    app.run(host='192.168.1.12', debug=True)