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
                    $ref: '#/components/schemas/RegisterUser'
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
        return BadRequest("The user already registered")

    # save data to firestore batabase
    entry: dict = dict()
    entry["uid"] = uid
    entry["name"] = user_data.get("name")
    entry["email"] = decoded_token.get("email")
    entry["address"] = decoded_token.get("address")
    entry["unit"] = decoded_token.get("unit")
    entry["user_status"] = 1
    entry["dod"] = user_data.get("dod")
    entry["grade"] = user_data.get("grade")
    entry["rank"] = user_data.get("rank")
    entry["branch"] = user_data.get("branch")
    entry["superior"] = user_data.get("superior")
    entry["level"] = user_data.get("level")
    entry["FCMToken"] = user_data.get("FCMToken")
    # if user upload the profile picture
    if "profile_picture" in user_data:
        bucket = storage.bucket()
        profile_picture: str = "profile_picture/" + str(uuid4())
        blob = bucket.blob(profile_picture)
        blob.upload_from_string(
            user_data["profile_picture"], content_type="image"
        )
        entry["profile_picture"] = profile_picture

    if "description" in user_data:
        entry["description"] = user_data["description"]
        if "Commander" in entry["description"]:
            entry["commander"] = True
        else:
            entry["commander"] = False

    if "phone" in user_data:
        entry["phone"] = user_data.get("phone")

    if user_data.get("grade") and (
        user_data.get("grade")[0:1] == "O" or user_data.get("grade")[0:1] == "W"
    ):
        entry["officer"] = True
    else:
        entry["officer"] = False

    # upload to the user table
    db.collection("User").document(uid).set(entry)

    return Response("User registered", 201)


@users.put("/upload_csv_users")
@check_token
def upload_csv_users() -> Response:
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")
    data: dict = request.get_json()

    # exceptions
    if "csv_file" in data and data.get("csv_file") == "":
        return BadRequest("Missing the csv_file")

    # check if the user exists
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    csv_file: str = base64.b64decode(data.get("csv_file"))
    csv_data = pd.read_csv(BytesIO(csv_file), dtype=str, keep_default_na=False)

    csv_data["DENT_DATE"] = pd.to_datetime(
        csv_data["DENT_DATE"], format="%Y%m%d"
    )
    csv_data["PHA_DATE"] = pd.to_datetime(csv_data["PHA_DATE"], format="%Y%m%d")

    user_entry: dict = dict()
    user_entry["timestamp"] = firestore.SERVER_TIMESTAMP

    medical_entry: dict = dict()
    medical_entry["creator_name"] = user.get("name")
    medical_entry["creator_dod"] = user.get("dod")
    medical_entry["timestamp"] = firestore.SERVER_TIMESTAMP

    for i in range(len(csv_data)):
        user_entry["name"] = csv_data.iloc[i]["NAME"]
        user_entry["email"] = csv_data.iloc[i]["EMAIL"]
        user_entry["password"] = csv_data.iloc[i]["PASSWORD"]
        user_entry["grade"] = csv_data.iloc[i]["GRADE"]
        user_entry["rank"] = str(csv_data.iloc[i]["RANK"])
        user_entry["role"] = str(csv_data.iloc[i]["ROLE"]).lower()
        user_entry["dod"] = str(csv_data.iloc[i]["DOD"])
        user_entry["branch"] = csv_data.iloc[i]["BRANCH"]
        user_entry["address"] = csv_data.iloc[i]["ADDRESS"]
        user_entry["superior"] = bool(csv_data.iloc[i]["SUPERIOR (DOD)"])
        user_entry["unit_name"] = csv_data.iloc[i]["UN"]

        if str(csv_data.iloc[i]["PHONE (optional)"]):
            user_entry["phone"] = str(
                csv_data.iloc[i]["PHONE (optional)"]
            ).replace("-", "")

        medical_entry["upc"] = csv_data.iloc[i]["UPC"]
        medical_entry["rcc"] = csv_data.iloc[i]["RCC"]
        medical_entry["mpc"] = csv_data.iloc[i]["MPC"]
        medical_entry["pdlc"] = csv_data.iloc[i]["PDLC"]
        medical_entry["mrc"] = int(csv_data.iloc[i]["MRC"])
        medical_entry["drc"] = int(csv_data.iloc[i]["DRC"])
        medical_entry["dent_date"] = csv_data.iloc[i]["DENT_DATE"]
        medical_entry["pha_date"] = csv_data.iloc[i]["PHA_DATE"]
        medical_entry["flight_status"] = bool(csv_data.iloc[i]["FLIGHT_STATUS"])
        medical_entry["mos"] = csv_data.iloc[i]["MOS"]
        medical_entry["unit_name"] = user_entry["unit_name"]
        medical_entry["dod"] = user_entry["dod"]

        # create dental event
        dental_event = (
            db.collection("Scheduled-Events")
            .where("confirmed_dod", "array_contains", user_entry["dod"])
            .where("description", "==", "Dental Readiness Examination Due")
            .get()
        )

        if len(dental_event) > 0:
            dental_id = dental_event[0].get("event_id")
        else:
            dental_id = str(uuid4())

        medical_event: dict = dict()
        medical_event["author"] = uid
        medical_event["confirmed_dod"] = [medical_entry.get("dod")]
        medical_event["invitees_dod"] = []
        medical_event["description"] = "Dental Readiness Examination Due"
        medical_event["event_id"] = dental_id
        medical_event["organizer"] = user.get("name")
        medical_event["period"] = False
        medical_event["timestamp"] = medical_entry.get("timestamp")
        medical_event["title"] = "Dental Exam Due"
        medical_event["type"] = "Mandatory"
        medical_event["starttime"] = medical_entry.get("dent_date").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        medical_event["endtime"] = medical_entry.get("dent_date").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        try:
            user_entry["uid"] = auth.get_user(user_entry["dod"]).uid
            auth.update_user(
                user_entry["uid"],
                email=user_entry["email"],
                password=user_entry["password"],
            )
        except auth.UserNotFoundError:
            user_entry["uid"] = auth.create_user(
                uid=user_entry["dod"],
                email=user_entry["email"],
                password=user_entry["password"],
            ).uid

        db.collection("User").document(user_entry["uid"]).set(
            user_entry, merge=True
        )
        db.collection("Medical").document(medical_entry["dod"]).set(
            medical_entry, merge=True
        )
        db.collection("Scheduled-Events").document(
            medical_event.get("event_id")
        ).set(medical_event, merge=True)

        # create pha event
        pa_event = (
            db.collection("Scheduled-Events")
            .where("confirmed_dod", "array_contains", user_entry["dod"])
            .where(
                "description",
                "==",
                "Physical Readiness Examination Due",
            )
            .get()
        )

        if len(pa_event) > 0:
            pa_id = pa_event[0].get("event_id")
        else:
            pa_id = str(uuid4())

        medical_event["title"] = "Physical Exam Due"
        medical_event["description"] = "Physical Readiness Examination Due"
        medical_event["event_id"] = pa_id
        medical_event["starttime"] = medical_entry.get("pha_date").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        medical_event["endtime"] = medical_entry.get("pha_date").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        db.collection("Scheduled-Events").document(
            medical_event.get("event_id")
        ).set(medical_event, merge=True)

        # get to_user uid.
        receiver_docs = (
            db.collection("User")
            .where("dod", "==", medical_entry.get("dod"))
            .limit(1)
            .stream()
        )

        receiver_list: list = []
        for doc in receiver_docs:
            receiver_list.append(doc.to_dict())

        receiver: dict = receiver_list[0]

        fcm_tokens: list = [receiver.get("FCMToken")]

        add_medical_notifications(
            medical_entry.get("dent_date"),
            fcm_tokens,
            {"title": "dent alert", "body": "dental appointment alert"},
        )

        add_medical_notifications(
            medical_entry.get("pha_date"),
            fcm_tokens,
            {"title": "pha alert", "body": "pha appointment alert"},
        )

    return Response("Success upload new user")


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
                    $ref: '#/components/schemas/UpdateUser'
    responses:
        201:
            description: Successfully update user data
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
    data: dict = request.get_json()

    # check if the user is in the table or not
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()
    bucket = storage.bucket()

    # update the user table
    if "grade" in data:
        user_ref.update({"grade": data.get("grade")})
        if data.get("grade")[0:1] == "O" or data.get("grade")[0:1] == "W":
            user_ref.update({"officer": True})
        else:
            user_ref.update({"officer": False})

    if "rank" in data:
        user_ref.update({"rank": data.get("rank")})

    if "branch" in data:
        user_ref.update({"branch": data.get("branch")})

    if "address" in data:
        user_ref.update({"address": data.get("address")})

    if "unit" in data:
        user_ref.update({"unit": data.get("unit")})

    if "superior" in data:
        user_ref.update({"superior": data.get("superior")})

    if "phone" in data:
        user_ref.update({"phone": data.get("phone")})

    if "level" in data:
        user_ref.update({"level": data.get("level")})

    if "description" in data:
        user_ref.update({"description": data.get("description")})

    if "profile_picture" in data:
        profile_picture_path: str = ""
        if "profile_picture" in user:
            profile_picture_path = user.get("profile_picture")
        else:
            profile_picture_path = "profile_picture/" + str(uuid4())
            user_ref.update({"profile_picture": profile_picture_path})
        blob = bucket.blob(profile_picture_path)
        blob.upload_from_string(
            data.get("profile_picture"), content_type="image"
        )

    if "signature" in data:
        signature_path: str = ""
        if "signature" in user:
            signature_path = user.get("signature")
        else:
            signature_path = "signature/" + str(uuid4())
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
        return NotFound("The user was not found")
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
        500:
            description: Internal API Error
    """
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")

    # check if the user exists
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")

    user: dict = user_ref.get().to_dict()

    # get the signature and the profile picture
    bucket = storage.bucket()

    if "signature" in user:
        signature_path: str = user.get("signature")
        blob = bucket.blob(signature_path)

        if not blob.exists():
            return NotFound("The signature not found.")

        # download the signature image
        signature = blob.download_as_bytes()
        user["signature"] = signature.decode("utf-8")

    if "profile_picture" in user:
        profile_picture_path: str = user.get("profile_picture")
        blob = bucket.blob(profile_picture_path)

        if not blob.exists():
            return NotFound("The profile picture not found.")

        # download the profile_picture image
        profile_picture = blob.download_as_bytes()
        user["profile_picture"] = profile_picture.decode("utf-8")

    return jsonify(user), 200


@users.get("/get_users")
@check_token
def get_users() -> Response:
    """
    Get users from Firebase.
    ---
    tags:
        - users
    summary: Get users
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
        - in: query
          name: target
          schema:
            type: string
          required: false
        - in: query
          name: page_limit
          schema:
            type: integer
          required: false
        - in: query
          name: dod
          schema:
            type: string
          required: false
        - in: query
          name: uid
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
        500:
            description: Internal API Error
    """
    # the default page limits is 10
    page_limit: int = 10
    if "page_limit" in request.args:
        page_limit = request.args.get("page_limit", default=10, type=int)

    user_docs: list = []
    target: str = request.args.get("target", type=str)
    dod: str = request.args.get("dod", type=str)

    # exact search
    if "uid" in request.args:
        uid: str = request.args.get("uid", type=str)
        user_docs = (
            db.collection("User").where("uid", "==", uid).limit(1).stream()
        )
    elif "dod" in request.args:
        user_docs = (
            db.collection("User").where("dod", "==", dod).limit(1).stream()
        )
    elif "target" in request.args:
        if target == "officer":
            user_docs = (
                db.collection("User")
                .where("officer", "==", True)
                .limit(page_limit)
                .stream()
            )
        elif target == "commander":
            user_docs = (
                db.collection("User")
                .where("commander", "==", True)
                .limit(page_limit)
                .stream()
            )
        elif target == "level":
            token: str = request.headers["Authorization"]
            decoded_token: dict = auth.verify_id_token(token)
            uid: str = decoded_token.get("uid")
            # check if the user exists
            user_ref = db.collection("User").document(uid)
            if user_ref.get().exists == False:
                return NotFound("The user was not found")
            level: str = user_ref.get().to_dict().get("level")
            user_docs = (
                db.collection("User")
                .where("level", ">", level)
                .limit(page_limit)
                .stream()
            )
    else:
        user_docs = db.collection("User").limit(page_limit).stream()

    users: list = []
    for user in user_docs:
        users.append(user.to_dict())

    return jsonify(users), 200


@users.get("get_subordinates")
@check_token
def get_subordinate() -> Response:
    """
    Get all subordinates for this user.
    ---
    tags:
        - users
    summary: Gets all subordinates
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
        - in: query
          name: dod
          schema:
            type: string
          required: false
    responses:
        200:
            content:
                application/json:
                    schema:
                        type: object
        400:
            description: Bad request
        401:
            description: Unauthorized - the provided token is not valid
        500:
            description: Internal API Error
    """
    dod: str = request.args.get("dod", type=str)

    if "dod" in request.args:
        try:
            subordinates: list = find_subordinates_by_dod(dod=dod)
        except:
            return NotFound("The org chart file not found")
    else:
        return BadRequest("Missing dod id")

    return jsonify(subordinates), 200
