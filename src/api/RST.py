# -*- coding: utf-8 -*
"""
    src.api.admin
    ~~~~~~~~~~~~~
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

from src.common.notifications import add_scheduled_notifications

rst: Blueprint = Blueprint("rst", __name__)


@rst.post("/upload_rst_data")
@check_token
def upload_RST_data() -> Response:
    """
    Upload a excel file that has RST Battle Assembly dates
    ---
    tags:
        - RST
    summary: Uploads battle assembly data
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
                    $ref:
    responses:
        201:
            description: RST records uploaded
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
    csv_data["Mandatory"] = csv_data["Mandatory"].astype(str)

    for i in range(len(csv_data)):
        entry: dict = dict()
        entry["author"] = uid
        entry["confirmed_dod"] = []
        entry["description"] = "Training Drills"
        entry["event_id"] = str(uuid4())
        entry["organizer"] = user.get("name")
        entry["period"] = True
        entry["timestamp"] = firestore.SERVER_TIMESTAMP
        entry["title"] = "Battle Assembly"

        if csv_data.iloc[i]["Mandatory"] == "YES":
            entry["type"] = "Mandatory"
        elif csv_data.iloc[i]["Mandatory"] == "NO":
            entry["type"] = "Optional"
        else:
            entry["type"] = "Invalid"

        date_split = csv_data.iloc[i]["Dates"].split()
        dates = date_split[0].split("-")

        datetime_object = datetime.strptime(date_split[1], "%B")
        month_int = datetime_object.month
        month_str = str(month_int)

        entry["starttime"] = (
            date_split[2] + "-" + month_str + "-" + dates[0] + "T00:00:00.000Z"
        )
        entry["endtime"] = (
            date_split[2] + "-" + month_str + "-" + dates[1] + "T00:00:00.000Z"
        )

        db.collection("Scheduled-Events").document(entry.get("event_id")).set(
            entry
        )

        receiver_docs = (
            db.collection("User")
            .where("dod", "==", user.get("dod"))
            .limit(1)
            .stream()
        )
        receiver_list: list = []

        for doc in receiver_docs:
            receiver_list.append(doc.to_dict())

        receiver: dict = receiver_list[0]
        fcm_tokens: list = [receiver.get("FCMToken")]

        # add_scheduled_notifications(
        #     entry.get("starttime"),
        #     fcm_tokens,
        #     {"title": "event alert", "body": "training drills: " + entry.get("type")}
        # )

        return Response("Successfully uploaded RST Training Dates")
