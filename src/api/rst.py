# -*- coding: utf-8 -*
"""
    src.api.admin
    ~~~~~~~~~~~~~
    Functions:
"""

from datetime import datetime, timedelta
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
from pytz import timezone
import pytz


def time_conv(date_split, time_split, time_zone):
    hour = time_split[0:2]
    minute = time_split[2:4]
    time = date_split[0] + "/" + date_split[1] + "/" + date_split[2] + " " + hour + ":" + minute
    format_data = "%d/%b/%y %H:%M"
    tz = ""
    
    if time_zone == "EDT":
        tz = timezone("US/Eastern")
    elif time_zone == "CDT":
        tz = timezone("America/Chicago")
    elif time_zone == "MDT":
        tz = timezone("America/Denver")
    elif time_zone == "PDT":
        tz = timezone("America/Los_Angeles")

    local_time = datetime.strptime(time, format_data)
    local_time = tz.localize(local_time)

    utc_time = local_time.astimezone(pytz.utc) + timedelta(hours=12)
    final_time = utc_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    return final_time


def replace_event(period, start_date_split, previous_date, unit, title):
    date = start_date_split[1] + "/" + start_date_split[2]
    events_ref = db.collection("Scheduled-Events")
    query_for_events = (
        events_ref.where("unit", "==", unit)
        .where("title", "==", title)
        .where("date", "==", date)
        .get()
    )

    if query_for_events == None:
        return

    for doc in query_for_events:
        result_dict = doc.to_dict()

        if period == True or start_date_split == previous_date:
            events_ref.document(result_dict["event_id"]).delete()

        elif period == False and int(start_date_split[0]) - 1 != int(
            previous_date[0]
        ):
            events_ref.document(result_dict["event_id"]).delete()

        else:
            return


rst: Blueprint = Blueprint("rst", __name__)


@rst.post("/upload_rst_data")
@check_token
def upload_rst_data() -> Response:
    """
    Upload a csv file that has RST Battle Assembly dates
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
    time_zone = pd.read_csv(
        BytesIO(csv_file), dtype=str, keep_default_na=False, nrows=1
    )
    time_zone = time_zone.iloc[0, 0]
    
    csv_data = pd.read_csv(
        BytesIO(csv_file), dtype=str, keep_default_na=False, skiprows=3
    )

    for i in range(len(csv_data)):
        entry: dict = dict()
        entry["author"] = uid
        entry["description"] = "Training Drills"
        entry["confirmed_dod"] = []
        entry["event_id"] = str(uuid4())
        entry["organizer"] = user.get("name")
        entry["timestamp"] = firestore.SERVER_TIMESTAMP
        entry["title"] = csv_data.iloc[i]["EVENT"]
        entry["type"] = csv_data.iloc[i]["EVENT TYPE"]
        entry["unit"] = csv_data.iloc[i]["UNIT"]
        entry["location"] = csv_data.iloc[i]["LOCATION"]
        entry["muta"] = csv_data.iloc[i]["MUTA"]
        entry["training_events"] = csv_data.iloc[i]["TRAINING EVENTS"]
        entry["remarks"] = csv_data.iloc[i]["REMARKS"]
        entry["remarks_2"] = csv_data.iloc[i]["REMARKS 2"]

        # adding invitees with same unit name
        unit = entry["unit"]
        invitees_ref = db.collection("User")
        query_for_invitees = invitees_ref.where("unit_name", "==", unit).get()
        invitees_dods = []

        for doc in query_for_invitees:
            result_dict = doc.to_dict()
            if user.get("dod") != result_dict["dod"]:
                invitees_dods.append(result_dict["dod"])

        entry["invitees_dod"] = invitees_dods

        start_date_split = csv_data.iloc[i]["START DATE"].split("-")
        start_time = csv_data.iloc[i]["START TIME"]
        end_date_split = csv_data.iloc[i]["END DATE"].split("-")
        end_time = csv_data.iloc[i]["END TIME"]
        
        if int(start_time) < 1000:
            start_time = "0" + start_time

        if start_time == "TBD":
            start_time = "0000"
            entry["description"] += " (Start time TBD)"

        if end_time == "TBD":
            end_time = "1200"
            entry["description"] += " (End time TBD)"

        entry["date"] = start_date_split[1] + "/" + start_date_split[2]
        entry["starttime"] = time_conv(start_date_split, start_time, time_zone)
        entry["endtime"] = time_conv(end_date_split, end_time, time_zone)

        if start_date_split[0] == end_date_split[0]:
            entry["period"] = False
        else:
            entry["period"] = True

        if i == 0:
            previous_date = start_date_split
        else:
            previous_date = csv_data.iloc[i - 1]["START DATE"].split("-")

        title = entry["title"]
        period = entry["period"]
        replace_event(period, start_date_split, previous_date, unit, title)

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
