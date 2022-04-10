# -*- coding: utf-8 -*
"""
    src.api.admin
    ~~~~~~~~~~~~~
    upload_medical_data()
    Functions:
"""
from uuid import uuid4
from flask import Response, request, jsonify
from src.api import Blueprint
from src.common.decorators import check_token
from src.common.database import db
from firebase_admin import auth, firestore
from werkzeug.exceptions import (
    NotFound,
    BadRequest,
    UnsupportedMediaType,
    Unauthorized,
)
from io import BytesIO
import pandas as pd
import base64

from src.common.notifications import add_medical_notifications


medical: Blueprint = Blueprint("medical", __name__)


@medical.post("/upload_medical_data")
@check_token
def upload_medical_data() -> Response:
    """
    Upload a excel file to notify users' medical appointment
    ---
    tags:
        - medical
    summary: Uploads medical data
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
                    $ref: '#/components/schemas/UploadMedical'
    responses:
        201:
            description: Medical records uploaded
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
    data: dict = request.get_json()

    # exceptions
    if "filename" in data and data.get("filename") == "":
        return BadRequest("Missing the filename")
    if data["filename"][-4:] != ".csv":
        return UnsupportedMediaType("The endpoint only accept .csv file")
    if "csv_file" in data and data.get("csv_file") == "":
        return BadRequest("Missing the csv_file")

    # check if the user exists
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    csv_file: str = base64.b64decode(data.get("csv_file"))
    csv_data = pd.read_csv(BytesIO(csv_file))
    csv_data["dent_date"] = pd.to_datetime(
        csv_data["dent_date"], format="%Y%m%d"
    )
    csv_data["pha_date"] = pd.to_datetime(csv_data["pha_date"], format="%Y%m%d")
    csv_data["dod"] = csv_data["dod"].astype(str)

    entry: dict = dict()
    entry["creator_name"] = user.get("name")
    entry["creator_uid"] = uid
    entry["creator_dod"] = user.get("dod")
    entry["timestamp"] = firestore.SERVER_TIMESTAMP

    for i in range(len(csv_data)):
        entry["upc"] = csv_data.iloc[i]["upc"]
        entry["unit_name"] = csv_data.iloc[i]["un"]
        entry["rcc"] = csv_data.iloc[i]["rcc"]
        entry["dod"] = str(csv_data.iloc[i]["dod"])
        entry["name"] = csv_data.iloc[i]["name"]
        entry["mpc"] = csv_data.iloc[i]["mpc"]
        entry["pdlc"] = csv_data.iloc[i]["pdlc"]
        entry["mrc"] = int(csv_data.iloc[i]["mrc"])
        entry["drc"] = int(csv_data.iloc[i]["drc"])
        entry["dent_date"] = csv_data.iloc[i]["dent_date"]
        entry["pha_date"] = csv_data.iloc[i]["pha_date"]
        db.collection("Medical").document(entry["dod"]).set(entry)

        # create dental event
        medical_event: dict = dict()
        medical_event["author"] = uid
        medical_event["confirmed_dod"] = []
        medical_event["invitees_dod"] = [entry.get("dod")]
        medical_event["description"] = "medical"
        medical_event["event_id"] = str(uuid4())
        medical_event["organizer"] = user.get("name")
        medical_event["period"] = False
        medical_event["timestamp"] = entry.get("timestamp")
        medical_event["title"] = "medical"
        medical_event["type"] = "Mandatory"
        medical_event["starttime"] = entry.get("dent_date").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        medical_event["endtime"] = entry.get("dent_date").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        db.collection("Scheduled-Event").document(
            medical_event.get("event_id")
        ).set(medical_event)

        # create pha event
        medical_event["event_id"] = str(uuid4())
        medical_event["starttime"] = entry.get("pha_date").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        medical_event["endtime"] = entry.get("pha_date").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        db.collection("Scheduled-Event").document(
            medical_event.get("event_id")
        ).set(medical_event)

        # get to_user uid.
        receiver_docs = (
            db.collection("User")
            .where("dod", "==", entry.get("dod"))
            .limit(1)
            .stream()
        )

        receiver_list: list = []
        for doc in receiver_docs:
            receiver_list.append(doc.to_dict())

        receiver: dict = receiver_list[0]

        fcm_tokens: list = [receiver.get("FCMToken")]

        add_medical_notifications(
            entry.get("dent_date"),
            fcm_tokens,
            {"title": "dent alert", "body": "dental appointment alert"},
        )

        add_medical_notifications(
            entry.get("pha_date"),
            fcm_tokens,
            {"title": "pha alert", "body": "pha appointment alert"},
        )

    return Response("Success upload medical data")


@medical.get("/get_medical_data")
@check_token
def get_medical_data() -> Response:
    """
    Get a medical record from Firebase Storage.
    ---
    tags:
        - medical
    summary: Gets a medical data
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
                        $ref: '#/components/schemas/Medical'
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

    # get the user table
    user_ref = db.collection("User").document(uid).get()
    if not user_ref.exists:
        return NotFound("The user was not found")
    user: dict = user_ref.to_dict()

    docs = (
        db.collection("Medical")
        .where("dod", "==", user.get("dod"))
        .limit(1)
        .stream()
    )
    res: dict = dict()
    for doc in docs:
        res = doc.to_dict()

    return jsonify(res), 200


@medical.delete("/delete_medical_records")
@check_token
def delete_medical_records() -> Response:
    """
    Delete medical records from Firebase Storage.
    ---
    tags:
        - medical
    summary: Deletes medical records
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
                    $ref: '#/components/schemas/DeleteMedical'
    responses:
        200:
            description: Medical records deleted
        400:
            description: Bad request
        401:
            description: Unauthorized - the provided token is not valid
        404:
            content:
                application/json:
                    schema:
                        type: array
                        items:
                            type: string
        415:
            description: Unsupported media type.
        500:
            description: Internal API Error
    """
    # check tokens and get uid from token
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")
    data: list = request.get_json()
    fail_list: list = list()

    if "dods" not in data:
        return BadRequest("Missing medical record dods")

    for dod in data.get("dods"):
        medical_ref = db.collection("Medical").document(dod)
        if not medical_ref.get().exists:
            fail_list.append(dod)
            continue
        medical: dict = medical_ref.get().to_dict()
        # Only the author, and admin have access to the data
        if (
            uid != medical.get("creator_uid")
            and decoded_token.get("admin") != True
        ):
            return Unauthorized(
                "The user is not authorized to retrieve this content"
            )
        medical_ref.delete()

    if len(fail_list) > 0:
        return jsonify(fail_list), 404

    return Response(response="File deleted", status=200)


@medical.get("/get_medical_records")
@check_token
def get_medical_records() -> Response:
    """
    Get medical records from Firebase Storage.
    ---
    tags:
        - medical
    summary: Gets medical datas
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
                        type: array
                        items:
                            $ref: '#/components/schemas/Medical'
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

    docs = db.collection("Medical").where("creator_uid", "==", uid).stream()
    res: list = list()
    for doc in docs:
        res.append(doc.to_dict())

    return jsonify(res), 200
