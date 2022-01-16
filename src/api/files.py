# -*- coding: utf-8 -*
"""
    src.api.files
    ~~~~~~~~~~~~~
    Functions:
        add_file()
        delete_file()
        get_file()
"""
from xmlrpc.client import boolean
from flask import Response, request, send_file
from src.common.decorators import check_token
from werkzeug.exceptions import (
    BadRequest,
    NotFound,
    Unauthorized,
    UnsupportedMediaType,
)
from firebase_admin import storage, auth, firestore
from io import BytesIO, UnsupportedOperation
from uuid import uuid4
from enum import Enum
from base64 import b64encode, b64decode
from os.path import splitext
from flask import jsonify

from src.common.database import db
from src.api import Blueprint

files: Blueprint = Blueprint("files", __name__)


@files.post("/upload_file")
@check_token
def upload_file() -> Response:
    """
    Upload a PDF file to Firebase Storage.
    ---
    tags:
        - files
    summary: Uploads a file
    requestBody:
        content:
            application/json:
                schema:
                    $ref: '#/components/schemas/File'
    responses:
        201:
            description: File uploaded
        400:
            description: Bad request
        401:
            description: Unauthorized - the provided token is not valid
        415:
            description: Unsupported media type. Provide a valid PDF
        500:
            description: Internal API Error
    """
    # check tokens and get uid from token
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token["uid"]
    # uid: str = str(uuid4())
    id = str(uuid4())
    data: dict = request.get_json()

    # Expcetions
    if "file" in data:
        file = data["file"]
    else:
        raise BadRequest("There was no file provided")

    if data.get("filename") and splitext(data.get("filename"))[1] != ".pdf":
        raise UnsupportedMediaType(
            "Unsupported media type. The endpoint only accepts PDFs"
        )

    if data.get("status") and data.get("status") < 1 or data.get("status") > 5:
        raise BadRequest("The file status is not supported")

    if "reviewer" not in data:
        raise BadRequest("Missing one reviewer")

    # save data to firestore batabase
    entry: dict = dict()
    entry["id"] = id
    entry["author"] = uid
    entry["timestamp"] = firestore.SERVER_TIMESTAMP
    entry["filename"] = data.get("filename")
    entry["status"] = data.get("status")
    entry["reviewer"] = data["reviewer"]
    entry["comment"] = ""
    db.collection(u"Files").document(id).set(entry)

    # save pdf to firestore storage
    bucket = storage.bucket()
    blob = bucket.blob(id)
    blob.upload_from_string(file, content_type="application/pdf")

    # update user table
    user_ref = db.collection(u"User").document(uid)
    user_ref.update({u"files": firestore.ArrayUnion([id])})

    return Response(response="File added", status=201)


@files.get("/get_file/<file_id>/")
@check_token
def get_file(file_id: str) -> Response:
    """
    Get a file from Firebase Storage.
    ---
    tags:
        - files
    summary: Gets a file
    parameters:
        - name: file_id
          in: path
          schema:
              type: string
          description: The ID of the file
          required: true
    responses:
        200:
            content:
                application/json:
                    schema:
                        '#/components/schemas/File'
        404:
            description: The file with the given filename was not found
        500:
            description: Internal API Error
    """
    # check tokens and get uid from token
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token["uid"]

    # get pdf from the firebase storage
    bucket = storage.bucket()
    blob = bucket.blob(file_id)

    if not blob.exists():
        return NotFound("The file with the given filename was not found.")

    # download the pdf file and add it to the file data
    file = blob.download_as_bytes()
    docs = db.collection(u"Files").where("id", "==", file_id).limit(1).stream()
    for doc in docs:
        res = doc.to_dict()
    res["file"] = file.decode("utf-8")

    # Only the author, reviewer, and admin have access to the data
    if (
        uid != res.get("reviewer")
        and uid != res.get("author")
        and decoded_token.get("admin") != True
    ):
        raise Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    return jsonify(res), 200


@files.delete("/delete_file/<file_id>/")
@check_token
def delete_file(file_id: str) -> Response:
    """
    Delete a file from Firebase Storage.
    ---
    tags:
        - files
    summary: Deletes a file
    parameters:
        - name: file_id
          in: path
          schema:
              type: string
          description: The ID of the file
          required: true
    responses:
        200:
            description: File deleted
        404:
            description: The file with the given filename was not found
        500:
            description: Internal API Error
    """
    # check tokens and get uid from token
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token["uid"]

    # get file data from firestore
    data = db.collection(u"Files").document(file_id)

    # Only the author, reviewer, and admin have access to the data
    if (
        uid != data.get("reviewer")
        or uid != data.get("author")
        or decoded_token.get("admin") != True
    ):
        raise Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    # delete the pdf from firebase storage
    bucket = storage.bucket()
    blob = bucket.blob(file_id)
    if not blob.exists():
        return NotFound("The file with the given filename was not found.")
    blob.delete()

    # delete the data from firesotre
    data.delete()

    # update the user table
    user_ref = db.collection(u"User").document(uid)
    user_ref.update({u"files": firestore.ArrayRemove([id])})

    return Response(response="File deleted", status=200)


@files.put("/change_status/")
@check_token
def change_status():
    """
    Change the status of a file case from Firebase Storage.
    ---
    tags:
        - files
    summary: Change the status
    requestBody:
        content:
            application/json:
                schema:
                    $ref: '#/components/schemas/Status'
    responses:
        200:
            description: Status changed
        404:
            description: The file with the given filename was not found
        500:
            description: Internal API Error
    """
    # check tokens and get uid from token
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token["reviwer"]
    # uid = "test00"
    data: dict = request.get_json()

    # exceptions
    if data["decision"] < 3 or data["decision"] > 5:
        raise BadRequest("Unsupported decision type.")

    # fetch the file data from firestore
    file = db.collection(u"Files").document(data["file_id"])

    # Only the reviewer, and admin have access to change the status of the file
    if uid != file.get("reviewer") or decoded_token.get("admin") != True:
        raise Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    if "comment" in data:
        file.update({u"comment": data["comment"]})

    file.update({u"status": data["decision"]})

    return Response("Status changed", 200)
