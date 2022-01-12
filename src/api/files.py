# -*- coding: utf-8 -*
"""
    src.api.files
    ~~~~~~~~~~~~~
    Functions:
        add_file()
        delete_file()
        get_file()
"""
from flask import Response, request, send_file
from src.common.decorators import check_token
from werkzeug.exceptions import (
    BadRequest,
    NotFound,
    Unauthorized,
    UnsupportedMediaType,
)
from firebase_admin import storage, auth, firestore
from io import BytesIO
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
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)

    uid: str = decoded_token["uid"]
    data: dict = request.get_json()

    # if "file" in data:
    #     file = b64decode(data["file"])
    # else:
    #     raise BadRequest("There was no file provided")

    if data.get("filename") and splitext(data.get("filename"))[1] != ".pdf":
        raise UnsupportedMediaType(
            "Unsupported media type. The endpoint only accepts PDFs"
        )
    id = str(uuid4())

    entry: dict = dict()
    entry["id"] = id
    entry["author"] = uid
    entry["timestamp"] = firestore.SERVER_TIMESTAMP
    entry["filename"] = data.get("filename")

    if "file" in data:
        entry["file"] = data["file"]
    else:
        raise BadRequest("There was no file provided")
    if data.get("status") and data.get("status") > 0 and data.get("status") < 6:
        entry["status"] = data.get("status")
    else:
        raise BadRequest("The file status is not supported")

    if data.get("reviewer"):
        entry["reviewer"] = data["reviewer"]

    db.collection(u"Files").add(entry)
    # bucket = storage.bucket()
    # blob = bucket.blob(id)
    # blob.upload_from_string(file, content_type="application/pdf")

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
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)

    uid: str = decoded_token["uid"]

    # bucket = storage.bucket()
    # blob = bucket.blob(file_id)
    # if not blob.exists():
    #     return NotFound("The file with the given filename was not found.")

    # file = blob.download_as_bytes()
    docs = db.collection(u"Files").where("id", "==", file_id).limit(1).stream()
    for doc in docs:
        res = doc.to_dict()
    # res["file"] = file

    if (
        uid != res.get("reviewer")
        or uid != res.get("author")
        or decoded_token.get("admin") != True
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
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)

    uid: str = decoded_token["uid"]

    docs = db.collection(u"Files").where("id", "==", file_id).limit(1).stream()
    for doc in docs:
        doc_id = doc.id
        res = db.collection("Files").document(doc_id).get()

    if (
        uid != res.get("reviewer")
        or uid != res.get("author")
        or decoded_token.get("admin") != True
    ):
        raise Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    # bucket = storage.bucket()
    # blob = bucket.blob(id)
    # if not blob.exists():
    #     return NotFound("The file with the given filename was not found.")
    # blob.delete()
    db.collection(u"Files").document(res.id).delete()

    return Response(response="File deleted", status=200)


@files.put("/change_status/<file_id>/")
@check_token
def change_status(file_id: str):
    pass
