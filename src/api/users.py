# -*- coding: utf-8 -*
"""
    src.api.users
    ~~~~~~~~~~~~~
    Functions:
        register_user()
        update_user()
        delete_user()
        get_user()
"""
from asyncore import read
from tabnanny import check
import uuid
from flask import Response, request
from src.common.decorators import check_token
from werkzeug.exceptions import (
    InternalServerError,
    BadRequest,
    NotFound,
    Unauthorized,
)
from firebase_admin import storage, auth, firestore
from uuid import uuid4
from os.path import splitext
from flask import jsonify

from src.common.database import db
from src.api import Blueprint

users: Blueprint = Blueprint("users", __name__)


@users.post("/register_user")
@check_token
def register_user() -> Response:
    """
    register a new user
    ---
    tags:
        - users
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
                    $ref: '#/components/schemas/UserRegister'
    responses:
        201:
            description: User registered
        400:
            description: Bad request
        401:
            description: Unauthorized - the provided token is not valid
        404:
            description: NotFound
        415:
            description: Unsupported media type.
        500:
            description: Internal API Error
    """
    # check tokens and get uid from token
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")
    user_data: dict = request.get_json()

    # check if the user is in the table or not
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == True:
        raise BadRequest("The user already registered")

    # save data to firestore batabase
    entry: dict = dict()
    entry["display_name"] = user_data.get("display_name")
    entry["phone"] = user_data.get("phone")
    entry["email"] = user_data.get("email")
    entry["status"] = 1

    # if user upload the profile picture
    bucket = storage.bucket()
    profile_picture: str = "/profile_picture/" + str(uuid4())
    if "profile_picture" in user_data:
        blob = bucket.blob(profile_picture)
        blob.upload_from_string(
            user_data["profile_picture"], content_type="image"
        )
        entry["profile_picture"] = profile_picture
    else:
        entry["profile_picture"] = "/profile_picture/ArmyReserve.png"

    # if user upload the description
    if "description" in user_data:
        entry["description"] = user_data["description"]
    else:
        entry["description"] = ""

    # upload to the user table
    db.collection("User").document(uid).set(entry)

    return Response("User registered", 201)


# @users.put("/update_user")
# @check_token


# @users.delete("/delete_user")
# @check_token


@users.get("/get_user")
@check_token
def get_user() -> Response:
    """
    Get a user info from Firebase Storage.
    ---
    tags:
        - users
    summary: Gets a user
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
                        '#/components/schemas/User'
        400:
            description: Bad request
        401:
            description: Unauthorized - the provided token is not valid
        404:
            description: NotFound
        415:
            description: Unsupported media type.
        500:
            description: Internal API Error
    """
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")

    # check if the user exsist
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        raise NotFound("The user not found")

    user: dict = user_ref.get().to_dict()

    # get the signature and the profile picture
    bucket = storage.bucket()

    if "signature" in user:
        blob = bucket.blob(user.get("signature"))

        if not blob.exists():
            raise NotFound("The signature not found.")

        # download the signature image
        signature = blob.download_as_bytes()
        user["signature"] = signature.decode("utf-8")

    if "profile_picture" in user:
        blob = bucket.blob(user.get("profile_picture"))

        if not blob.exists():
            raise NotFound("The profile picture not found.")

        # download the signature image
        profile_picture = blob.download_as_bytes()
        user["profile_picture"] = profile_picture.decode("utf-8")

    return jsonify(user), 200
