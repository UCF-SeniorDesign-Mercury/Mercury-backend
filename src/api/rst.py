# -*- coding: utf-8 -*
"""
    src.api.admin
    ~~~~~~~~~~~~~
    Functions:
"""

from datetime import datetime
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


def time_conv(date_split, time_split):
    day = int(date_split[0])
    datetime_object = datetime.strptime(date_split[1], "%b")
    month_int = datetime_object.month
    year = "20" + date_split[2]
    time = int(time_split[0])

    if time < 10:
        time = "0" + str(time)

    else:
        time = str(time)

    if day < 10:
        day = "0" + str(day)

    else:
        day = str(day)

    if month_int < 10:
        month = "0" + str(month_int)

    else:
        month = str(month_int)

    if time_split[1] == "AM" and time[:2] == "12":
        return year + "-" + month + "-" + day + "T00:" + time[:-2] + ":00.000Z"

    elif time_split[1] == "AM":
        return year + "-" + month + "-" + day + "T" + time + ":00.000Z"

    elif time_split[1] == "PM" and time[:2] == "12":
        return year + "-" + month + "-" + day + "T" + time + ":00.000Z"

    else:
        return (
            year
            + "-"
            + month
            + "-"
            + day
            + "T"
            + str(int(time[:2]) + 12)
            + ":"
            + time[:-2]
            + ":00.000Z"
        )


rst: Blueprint = Blueprint("rst", __name__)


@rst.post("/upload_rst_data")
@check_token
def upload_rst_data() -> Response:
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

    # check if the user exists
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    csv_file: str = base64.b64decode(data.get("csv_file"))
    csv_data = pd.read_csv(BytesIO(csv_file))

    for i in range(len(csv_data)):
        entry: dict = dict()
        entry["author"] = uid
        entry["confirmed_dod"] = []
        entry["description"] = "Training Drills"
        entry["event_id"] = str(uuid4())
        entry["invitees_dod"] = []
        entry["organizer"] = user.get("name")
        entry["period"] = True
        entry["timestamp"] = firestore.SERVER_TIMESTAMP
        entry["title"] = "Battle Assembly"
        entry["type"] = csv_data.iloc[i]["EVENT TYPE"]
        entry["Unit"] = csv_data.iloc[i]["UNIT"]
        entry["Location"] = csv_data.iloc[i]["LOCATION"]
        entry["MUTA"] = csv_data.iloc[i]["MUTA"]
        entry["Training Events"] = csv_data.iloc[i]["TRAINING EVENTS"]
        entry["Remarks"] = csv_data.iloc[i]["REMARKS"]

        start_date_split = csv_data.iloc[i]["START DATE"].split("-")
        start_time_split = csv_data.iloc[i]["START TIME"].split(":")
        end_date_split = csv_data.iloc[i]["END DATE"].split("-")
        end_time_split = csv_data.iloc[i]["END TIME"].split(":")

        firebase_starttime = time_conv(start_date_split, start_time_split)
        firebase_endtime = time_conv(end_date_split, end_time_split)

        entry["starttime"] = firebase_starttime
        entry["endtime"] = firebase_endtime

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

    return Response("Successfully uploaded Battle Assembly dates")
