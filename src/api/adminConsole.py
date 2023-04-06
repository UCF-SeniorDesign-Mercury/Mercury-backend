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
                    "uid": userRecord.uid,
                    "dod": userRecord.uid
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
        query_str = content['query'].lower()

        user_docs = db.collection("User").where('dod', '>=', query_str).where('dod', '<=', query_str + u'\uf8ff').stream()
        user_docs += db.collection("User").where('name', '>=', query_str).where('name', '<=', query_str + u'\uf8ff').stream()
        user_docs += db.collection("User").where('email', '>=', query_str).where('email', '<=', query_str + u'\uf8ff').stream()
        user_docs += db.collection("User").where('phone', '>=', query_str).where('phone', '<=', query_str + u'\uf8ff').stream()

        Users = [doc.to_dict() for doc in user_docs]

        response = jsonify(Users)
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


