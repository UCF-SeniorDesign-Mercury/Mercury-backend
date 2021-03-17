from firebase_admin import credentials, auth, firestore, initialize_app
from flask import Flask, Response, request, jsonify
from functools import wraps
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

    # Check if form data sent from client exists

    # If exists, extract data from request

    # Try to write to Firestore DB

    # Return Response 200
    return Response(response="Event added", status=200)


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
        return jsonify({"Message": "It works!!!"})
    except:
        return jsonify({"Message": "Not assigned a role"})


# 
if __name__ == '__main__':
    app.run(host='192.168.1.13', debug=True)