# -*- coding: utf-8 -*
"""
    src.api.admin
    ~~~~~~~~~~~~~
    upload_medical_data()
    Functions:
"""
from flask import Response, request, jsonify
from src.api import Blueprint
from src.common.decorators import check_token
from src.common.database import db
from firebase_admin import auth, firestore

# from src.common.helpers import find_subordinates_by_dod
from werkzeug.exceptions import NotFound, BadRequest, UnsupportedMediaType
from io import BytesIO
import pandas as pd
import base64


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
            description: File uploaded
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

    # subordinates: list = find_subordinates_by_dod(dod=user.get("dod"))

    csv_file: str = base64.b64decode(data.get("csv_file"))
    csv_data = pd.read_csv(BytesIO(csv_file))
    csv_data["dent_date"] = pd.to_datetime(
        csv_data["dent_date"], format="%Y%m%d"
    )
    csv_data["pha_date"] = pd.to_datetime(csv_data["pha_date"], format="%Y%m%d")

    entry: list = list()
    entry["creator_name"] = user.get("name")
    entry["creator_uid"] = uid
    entry["creator_dod"] = user.get("dod")
    entry["timestamp"] = firestore.SERVER_TIMESTAMP

    for i in range(len(csv_data)):
        entry["upc"] = csv_data.loc[i, "upc"]
        entry["unit_name"] = csv_data.loc[i, "upc"]
        entry["upc"] = csv_data.loc[i, "upc"]
        entry["upc"] = csv_data.loc[i, "upc"]
        entry["upc"] = csv_data.loc[i, "upc"]
        entry["upc"] = csv_data.loc[i, "upc"]
        entry["upc"] = csv_data.loc[i, "upc"]
        entry["upc"] = csv_data.loc[i, "upc"]
        entry["upc"] = csv_data.loc[i, "upc"]

    return Response("Success upload medical data")


def create_medical_events(root: list, data):
    pass
