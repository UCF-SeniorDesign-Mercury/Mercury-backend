from firebase_admin import auth, firestore
from flask import Response, jsonify, request
from src.api import Blueprint
from src.common.database import db
from src.common.decorators import admin_only, check_token
from src.api.notifications import create_notification
import pandas as pd
"""
firebase_admin : General firebase admin functions
    auth - For user authorization
    firestore - for access to the db

flask : API framework
    request: Recieves request
    Response: Outputs
    jsonify: Easily turn hashmaps to JSON

src.api: Init python file that contains the blueprints aka '/' directory
    Blueprints: GUide

pandas: For CSV processing
"""

adminConsole: Blueprint = Blueprint("adminConsole", __name__)

# Basic CRUD (Create - Read - Update - Delete)

# CREATE FUNCTIONS

# FUNCTIONAL
@adminConsole.post('/register_user')
def register_user ():

    try:

        content = request.json

        userRecord = auth.create_user(
            email = content['email'],
            password = content['password']
        
        )
        entry = {
                    "name": content["name"],
                    "address": content["address"],
                    "email": content["email"],
                    "password": content["password"],
                    "phone": content["phone"],
                    "grade": content["grade"],
                    "branch": content["branch"],
                    "role": content["role"],
                    "rank": content["rank"],
                    "superior": content["superior"],
                    "unit_name": content["unit_name"],
                    "uid": content['uid'],
                    "dod": content['dod']
                }
        
        db.collection('User').document(userRecord.uid).set(entry)

        response = jsonify({"message" : "User successfully registed"})
        response.status_code = 200

        return response
    
    except Exception as e:
        return jsonify({"message" : "User couldn't be registered", "error": str(e)})
            
    

# One is already made
@adminConsole.post('/upload_user_from_csv')
def upload_user_from_csv():
    pass

# READ FUNCTIONS 
# FUNCTIONAL
@adminConsole.get('/get_all_users')
def get_all_users():

    try:
        user_docs = db.collection("User").stream()
        users = [doc.to_dict() for doc in user_docs]

        response = jsonify(users)
        response.status_code = 200

        return response
    except Exception as e:
        return jsonify({"message" : "COuld not retriew users", "error": e})



# In the works
@adminConsole.post('/search_user')
def search_user():
    try:
        content = request.json
        query = content['query']

        searchByName_docs = db.collection("User").where('name', '>=', query).where('name', '<=', query + u'\uf8ff')
        searchByEmail_docs = db.collection("User").where('email', '>=', query).where('email', '<=', query + u'\uf8ff')
        SearchByPhone_docs = db.collection("User").where('phone', '>=', query).where('phone', '<=', query + u'\uf8ff')
        searchByDOD_docs = db.collection("User").where('dod', '>=', query).where('dod', '<=', query + u'\uf8ff')

        Users = dict()


        for user in searchByName_docs.stream():
            Users[user.id] = user.to_dict()
        
        for user in searchByEmail_docs.stream():
            Users[user.id] = user.to_dict()

        for user in SearchByPhone_docs.stream():
            Users[user.id] = user.to_dict()

        for user in searchByDOD_docs.stream():
            Users[user.id] = user.to_dict()

        response = jsonify(list(Users.values()))
        response.status_code = 200

        return response
    except Exception as e:
        return jsonify({"message" : "error looking for user", "error" : str(e)})


# UPDATE FUNCTIONS

# FUNCTIONAL
@adminConsole.put('/update_user')
def update_user():
    try:

        content = request.json
        user_doc = db.collection("User").document(content['uid'])

        if user_doc.get().exists:
            user_doc.update(content)
            response = jsonify({"message": "User successfully updated"})
            response.status_code = 200
        else:
            response = jsonify({"message": "User does not exist"})
            response.status_code = 404

        return response

    except Exception as e:
        return jsonify({"message": "User couldn't be updated", "error": str(e)})



# DELETE FUNCTIONS

#FUNCTIONAL
@adminConsole.delete('/del_user')
def del_user():

    try:
        content = request.json
        user_doc = db.collection("User").document(content['uid'])

        if user_doc.get().exists:
            user_doc.delete()
            auth.delete_user(content['uid'])
            response = jsonify({"message": "User successfully deleted"})
            response.status_code = 200
        else:
            response = jsonify({"message": "User does not exist"})
            response.status_code = 404

        return response

    except Exception as e:
        return jsonify({"message": "User couldn't be deleted", "error": str(e)})


