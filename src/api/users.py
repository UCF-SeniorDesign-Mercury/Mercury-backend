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
from flask import Response, request
from src.common.decorators import admin_only, check_token
from werkzeug.exceptions import BadRequest, NotFound
from firebase_admin import storage, auth
from werkzeug.exceptions import BadRequest, NotFound, Unauthorized
from firebase_admin.auth import UserRecord
from google.cloud import firestore
from uuid import uuid4
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
    entry["email"] = decoded_token.get("email")
    entry["user_status"] = 1

    # if user upload the profile picture
    bucket = storage.bucket()
    profile_picture: str = "profile_picture/" + str(uuid4())
    if "profile_picture" in user_data:
        blob = bucket.blob(profile_picture)
        blob.upload_from_string(
            user_data["profile_picture"], content_type="image"
        )
        entry["profile_picture"] = profile_picture
    else:
        entry[
            "profile_picture"
        ] = "profile_picture/f1f720cb-bf7a-4aa3-a9eb-a447753f229e"

    # if user upload the description
    if "description" in user_data:
        entry["description"] = user_data["description"]
    else:
        entry["description"] = ""

    # upload to the user table
    db.collection("User").document(uid).set(entry)

    return Response("User registered", 201)


@users.put("/update_user")
@check_token
def update_user() -> Response:
    """
    Update user data
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
                    $ref: '#/components/schemas/UserUpdate'
    responses:
        201:
            description: Successfully update user data
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
    data: dict = request.get_json()

    # check if the user is in the table or not
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        raise NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()
    bucket = storage.bucket()

    # update the user table
    if "display_name" in data:
        user_ref.update({"display_name": data.get("display_name")})
    if "phone" in data:
        user_ref.update({"phone": data.get("phone")})
    if "email" in data:
        user_ref.update({"email": data.get("email")})
    if "description" in data:
        user_ref.update({"description": data.get("description")})

    if "profile_picture" in data:
        profile_picture_path: str = ""
        if "profile_picture" in user:
            profile_picture_path = user.get("profile_picture")
        else:
            profile_picture_path = "profile_picture/" + str(uuid4)
            user_ref.update({"profile_picture": profile_picture_path})
        blob = bucket.blob(profile_picture_path)
        blob.upload_from_string(
            data.get("profile_picture"), content_type="image"
        )
    if "signature" in data:
        if "signature" in user:
            signature_path = user.get("signature")
        else:
            signature_path = "signature/" + str(uuid4)
            user_ref.update({"signature": signature_path})
        blob = bucket.blob(signature_path)
        blob.upload_from_string(data.get("signature"), content_type="image")

    return Response("Successfully update user data", 200)


@users.delete("/delete_user/<uid>")
@check_token
@admin_only
def delete_user(uid: str) -> Response:
    """
    Delete the user from Firebase Storage.
    ---
    tags:
        - users
    summary: Deletes a user
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
    responses:
        200:
            description: User deleted
        400:
            description: Bad request
        401:
            description: Unauthorized - the provided token is not valid
        404:
            description: NotFound
        500:
            description: Internal API Error
    """
    # get the user date from the user table
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        raise NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    # delete the signature and profile_picture from firebase storage
    bucket = storage.bucket()
    if "signature" in user:
        blob = bucket.blob(user.get("signature"))
        if not blob.exists():
            return NotFound("The signature not found.")
        blob.delete()

    if "profile_picture" in user:
        blob = bucket.blob(user.get("profile_picture"))
        if not blob.exists():
            return NotFound("The profile_picture not found.")
        blob.delete()

    # delete record from user table
    user_ref.delete()

    return Response("User Deleted", 200)


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

    # check if the user exists
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        raise NotFound("The user was not found")

    user: dict = user_ref.get().to_dict()

    # get the signature and the profile picture
    bucket = storage.bucket()

    if "signature" in user:
        signature_path: str = user.get("signature")
        blob = bucket.blob(signature_path)

        if not blob.exists():
            raise NotFound("The signature not found.")

        # download the signature image
        signature = blob.download_as_bytes()
        user["signature"] = signature.decode("utf-8")

    if "profile_picture" in user:
        profile_picture_path: str = user.get("profile_picture")
        blob = bucket.blob(profile_picture_path)

        if not blob.exists():
            raise NotFound("The profile picture not found.")

        # download the profile_picture image
        profile_picture = blob.download_as_bytes()
        user["profile_picture"] = profile_picture.decode("utf-8")

    return jsonify(user), 200


@users.post("/assign_role")
@check_token
@admin_only
def assign_role() -> Response:
    """
    Assign a role for newly registered user.
    ---
    tags:
        - users
    summary: Upon newly registering a user, they are granted a role.
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
                    $ref: '#/components/schemas/Role'
    responses:
        200:
            description: Successfully assigned role.
        404:
            description: Fail assigned role.
    """
    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)

    # only admin have access to assign role
    if decoded_token.get("admin") != True:
        raise Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    # Get role and accessLevel
    data: dict = request.get_json()
    email: str = data.get("email")
    role: str = data.get("role")
    level: str = data.get("level")
    rank: str = data.get("rank")
    user: UserRecord = auth.get_user_by_email(email)
    current_custom_claims = user.custom_claims

    # Reference to user document
    user_ref = db.collection("User").document(user.uid)
    if user_ref.get().exists == False:
        raise NotFound("The user was not found")

    # User has no previous role in their custom claims
    if current_custom_claims is None:
        auth.set_custom_user_claims(
            user.uid, {role: True, "accessLevel": level}
        )
    # User has a role set previously
    else:
        current_custom_claims["accessLevel"] = level
        current_custom_claims[role] = True

        auth.set_custom_user_claims(user.uid, current_custom_claims)

    user_ref.update({"role": role})

    if "rank" in data:
        user_ref.update({"rank": rank})

    return Response("Successfully assigned role", 200)


@users.delete("/revoke_role/<email>")
@check_token
@admin_only
def revoke_role(email: str) -> Response:
    """
    Remove a role from a specificed user. Level is also updated if it's affected by the removal of role
    ---
    tags:
        - users
    summary: Upon newly registering a user, they are granted a role.
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
    responses:
        200:
            description: Successfully removing role.
        404:
            description: Fail removing role.
    """
    user_record = auth.get_user_by_email(email)

    # Reference to user document
    user_ref = db.collection("User").document(user_record.uid)
    if user_ref.get().exists == False:
        raise NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    # remove the custom user claims
    auth.set_custom_user_claims(
        user_record.uid, {user.get("role"): None, "accessLevel": None}
    )

    # update user table
    user_ref.update({"role": firestore.DELETE_FIELD})

    return Response("Successfully removing role", 200)


@users.get("/get_users")
@check_token
@admin_only
def get_users() -> Response:
    """
    Get a file from Firebase Storage.
    ---
    tags:
        - users
    summary: Gets a file
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
        - in: query
          name: rank
          schema:
            type: string
          required: false
        - in: query
          name: page_limit
          schema:
            type: integer
          required: false
        - in: query
          name: role
          schema:
            type: string
          required: false
        - in: query
          name: email
          schema:
            type: string
          required: false
    responses:
        200:
            content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: '#/components/schemas/User'
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
    # the default page limits is 10
    page_limit: int = 10
    if "page_limit" in request.args:
        page_limit = request.args.get("page_limit", default=10, type=int)

    user_docs: list = []
    rank: str = request.args.get("rank", type=str)
    role: str = request.args.get("role", type=str)
    email: str = request.args.get("email", type=str)

    # email exact search
    if "email" in request.args:
        user_docs = (
            db.collection("User")
            .where("email", "==", email)
            .limit(page_limit)
            .stream()
        )
    # both status and filename fuzzy search
    elif "role" in request.args and "rank" in request.args:
        user_docs = (
            db.collection("User")
            .where("role", "==", role)
            .where("rank", "==", rank)
            .limit(page_limit)
            .stream()
        )
    elif "role" in request.args:
        user_docs = (
            db.collection("User")
            .where("role", "==", role)
            .limit(page_limit)
            .stream()
        )
    elif "rank" in request.args:
        user_docs = (
            db.collection("User")
            .where("rank", "==", rank)
            .limit(page_limit)
            .stream()
        )
    else:
        user_docs = db.collection("User").limit(page_limit).stream()

    users: list = []
    for user in user_docs:
        users.append(user.to_dict())

    return jsonify(users), 200
