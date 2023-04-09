# -*- coding: utf-8 -*
"""
    src.api.rosters
    ~~~~~~~~~~~~~
    Functions:
    create_roster()
    show_rosters()
    search_roster()
    delete_roster()
    add_to_roster()
    remove_from_roster()
"""
from tabnanny import check
from flask import Response, request
from src.common.decorators import admin_only, check_token
from werkzeug.exceptions import BadRequest, NotFound, UnsupportedMediaType
from firebase_admin import storage, auth, firestore
from uuid import uuid4
from flask import jsonify

from src.common.database import db
from src.api import Blueprint
from src.common.helpers import find_subordinates_by_dod
import base64
from io import BytesIO
import pandas as pd

from src.common.notifications import add_medical_notifications

rosters: Blueprint = Blueprint("rosters", __name__)

@rosters.post("/create_roster")
@check_token
def create_roster() -> Response:
    
    try:
        # check tokens and get uid from token
        roster_data: dict = request.get_json()

        # Extract roster name and users list from the user_data dictionary
        roster_name = roster_data.get("roster_name")
        users_list = roster_data.get("users")

        # check if the user is in the table or not
        roster_ref = db.collection("Roster").document(roster_name)
        if roster_ref.get().exists == True:
            return BadRequest("The roster is already registered")

        # save data to firestore batabase    
        entry: dict = dict()
        entry["roster_name"] = roster_name
        entry["users"] = users_list

        # upload to the user table
        db.collection("Roster").document(roster_name).set(entry)

        return Response("Roster registered", 201)
     
    except Exception as e:
        # Handle any potential exceptions and return error response
        return NotFound("Failed to create roster: {}".format(str(e))), 500

@rosters.get("/show_rosters")
@check_token
def show_rosters() -> Response:
    
    try:
        # Query Firestore for all rosters
        roster_data = db.collection("Roster").get()

        # Extract roster data from Firestore documents
        rosters = []
        for roster in roster_data:
            rosters.append(roster.to_dict())

        # Return roster data as JSON response
        return jsonify(rosters), 200
    
    except Exception as e:
        return NotFound("Failed to retrieve rosters: {}".format(str(e))), 500

@rosters.get("/search_roster")
@check_token
def search_roster() -> Response:
    try:
        # Get search query from request
        search_data = request.get_json()
        search_query = search_data.get("query")

        # Query Firestore for rosters matching search query
        query = db.collection("Roster").where("roster_name", "==", search_query).get()

        # Extract roster data from Firestore documents
        roster_data = []
        for roster in query:
            roster_data.append(roster.to_dict())

        # Return roster data as JSON response
        return jsonify(roster_data), 200

    except Exception as e:
        # Handle any potential exceptions and return error response
        return NotFound("Failed to search rosters: {}".format(str(e))), 500

@rosters.delete("/delete_roster")
@check_token
def delete_roster() -> Response:
    try:
        # Get roster name from request
        roster_data = request.get_json()
        roster_name = roster_data.get("roster_name")

        # Check if roster exists in Firestore
        roster_ref = db.collection("Roster").document(roster_name)

        if not roster_ref.get().exists:
            return NotFound("Roster not found"), 404

        # Delete roster from Firestore
        roster_ref.delete()

        # Return success response
        return jsonify("Roster deleted successfully"), 200
        

    except Exception as e:
        # Handle any potential exceptions and return error response
        return BadRequest("Failed to delete roster: {}".format(str(e))), 500

@rosters.put("/add_to_roster")
@check_token
def add_to_roster() -> Response:
    try:
        # Get request data
        roster_data = request.get_json()
        roster_name = roster_data.get("roster_name")
        user_data = roster_data.get("user_data")

        # Check if roster exists in Firestore
        roster_ref = db.collection("Roster").document(roster_name)
        roster_doc = roster_ref.get()
        if not roster_doc.exists:
            return NotFound("Roster not found"), 404

        # Update roster with new user data
        roster_users = roster_doc.get("users") or []
        roster_users.append(user_data)
        roster_ref.update({"users": roster_users})

        # Return success response
        return jsonify("User added to roster successfully"), 200

    except Exception as e:
        # Handle any potential exceptions and return error response
        return BadRequest("Failed to add user to roster: {}".format(str(e))), 500

@rosters.delete("/remove_from_roster")
@check_token
@admin_only
def remove_from_roster() -> Response:
    try:
        # Get request data
        roster_data = request.get_json()
        roster_name = roster_data.get("roster_name")
        user_data = roster_data.get("user_data")

        # Check if roster exists in Firestore
        roster_ref = db.collection("Roster").document(roster_name)
        roster_doc = roster_ref.get()
        if not roster_doc.exists:
            return NotFound("Roster not found"), 404

        # Remove user data from roster
        roster_users = roster_doc.get("users") or []
        if user_data in roster_users:
            roster_users.remove(user_data)
            roster_ref.update({"users": roster_users})
            return jsonify("User removed from roster successfully"), 200
        else:
            return NotFound("User not found in roster"), 404

    except Exception as e:
        # Handle any potential exceptions and return error response
        return BadRequest("Failed to remove user from roster: {}".format(str(e))), 500
