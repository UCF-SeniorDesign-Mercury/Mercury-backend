# -*- coding: utf-8 -*
"""
    src.api.files
    ~~~~~~~~~~~~~
    Functions:
        change_status()
        delete_file()
        get_file()
        update_file()
        upload_file()
        get_user_files()
        get_next_user_files_page()
"""
from flask import Response, request
from src.common.decorators import check_token
from werkzeug.exceptions import (
    InternalServerError,
    BadRequest,
    NotFound,
    Unauthorized,
    UnsupportedMediaType,
)
from firebase_admin import storage, auth, firestore
from uuid import uuid4
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
                    $ref: '#/components/schemas/File'
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
    # check tokens and get uid from token
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")
    file_id: str = str(uuid4())
    signature_id: str = str(uuid4())
    data: dict = request.get_json()

    # get user table
    user_ref = db.collection(u"User").document(uid)
    if user_ref.get().exists == False:
        raise NotFound("The user not found")
    user: dict = user_ref.get().to_dict()

    # Exceptions
    if "file" in data:
        file = data["file"]
    else:
        raise BadRequest("There was no file provided")

    if data.get("filename") and splitext(data.get("filename"))[1] != ".pdf":
        raise UnsupportedMediaType(
            "Unsupported media type. The endpoint only accepts PDFs"
        )

    if user.get("signature") == None and data.get("signature") == None:
        raise BadRequest("Missing the signature")

    if "reviewer" not in data:
        raise BadRequest("Missing the reviewer")

    # save data to firestore batabase
    entry: dict = dict()
    entry["id"] = file_id
    entry["author"] = uid
    entry["timestamp"] = firestore.SERVER_TIMESTAMP
    entry["filename"] = data.get("filename")
    entry["status"] = 1
    entry["reviewer"] = data["reviewer"]
    entry["comment"] = ""
    db.collection(u"Files").document(file_id).set(entry)

    try:
        # save pdf to firestore storage
        bucket = storage.bucket()
        blob = bucket.blob(file_id)
        blob.upload_from_string(file, content_type="application/pdf")
    except:
        raise InternalServerError("Could not save pdf")

    # update signature
    if data.get("signature") != None:
        try:
            # save signature image to firebase storage
            blob = bucket.blob(signature_id)
            blob.upload_from_string(data.get("signature"), content_type="image")
        except:
            raise InternalServerError("Could not save signature")
        user_ref.update({u"signature": signature_id})

    return Response(response="File added", status=201)


@files.get("/get_file/<file_id>")
@check_token
def get_file(file_id: str) -> Response:
    """
    Get a file from Firebase Storage.
    ---
    tags:
        - files
    summary: Gets a file
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
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

    # get the user table
    user_ref = db.collection(u"User").document(uid).get()
    if user_ref.exists == False:
        raise NotFound("The user not found")
    user: dict = user_ref.to_dict()

    # Only the author, reviewer, and admin have access to the data
    if (
        uid != res.get("reviewer")
        and uid != res.get("author")
        and user.get("role") != "admin"
    ):
        raise Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    # download the pdf file and add it to the file data
    blob = bucket.blob(user.get("signature"))

    if not blob.exists():
        return NotFound("The user's signature was not found.")
    signature = blob.download_as_bytes()
    res["signature"] = signature.decode("utf-8")

    return jsonify(res), 200


@files.delete("/delete_file/<file_id>")
@check_token
def delete_file(file_id: str) -> Response:
    """
    Delete a file from Firebase Storage.
    ---
    tags:
        - files
    summary: Deletes a file
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
        - name: file_id
          in: path
          schema:
              type: string
          description: The ID of the file
          required: true
    responses:
        200:
            description: File deleted
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

    # get file data from firestore
    data_ref = db.collection(u"Files").document(file_id)

    if not data_ref.get().exists:
        return NotFound("The file not found")

    data: dict = data_ref.get().to_dict()

    # get the user date from the user table
    user_ref = db.collection(u"User").document(uid)
    if user_ref.get().exists == False:
        raise NotFound("The user not found")
    user: dict = user_ref.get().to_dict()

    # Only the author, reviewer, and admin have access to the data
    if (
        uid != data.get("reviewer")
        and uid != data.get("author")
        and user.get("role") != "admin"
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
    data_ref.delete()

    return Response(response="File deleted", status=200)


@files.put("/update_file")
@check_token
def update_file():
    """
    The users update their own file from Firebase Storage.
    ---
    tags:
        - files
    summary: update file
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
                    $ref: '#/components/schemas/UpdateFile'
    responses:
        200:
            description: File Updated
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
    author_uid: str = decoded_token.get("uid")
    data: dict = request.get_json()

    # fetch the file data from firestore
    file_ref = db.collection(u"Files").document(data["file_id"])
    if file_ref.get().exists == False:
        raise NotFound("The file not found")
    file = file_ref.get().to_dict()

    # get the user table
    user_ref = db.collection(u"User").document(author_uid).get()
    if user_ref.exists == False:
        raise NotFound("The user not found")
    user: dict = user_ref.to_dict()

    # exceptions
    if not file_ref.get().exists:
        return NotFound("The file with the given filename was not found")

    if file["status"] < 0 or file["status"] > 3:
        raise BadRequest("Files is not allow to change after decision made")

    # Only the author have access to update the file
    if author_uid != file["author"]:
        raise Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    # if filename in the request update it
    if "filename" in data:
        if data.get("filename") and splitext(data.get("filename"))[1] != ".pdf":
            raise UnsupportedMediaType(
                "Unsupported media type. The endpoint only accepts PDFs"
            )
        file_ref.update({u"filename": data.get("filename")})

    # save pdf to firestore storage
    bucket = storage.bucket()
    if "file" in data:
        try:
            blob = bucket.blob(data.get("file_id"))
            blob.upload_from_string(
                data.get("file"), content_type="application/pdf"
            )
        except:
            raise InternalServerError("cannot update pdf to storage")

    # save pdf to firestore storage
    if "signature" in data:
        try:
            blob = bucket.blob(user.get("signature"))
            blob.upload_from_string(data.get("signature"), content_type="image")
        except:
            raise InternalServerError("cannot update signature to storage")

    return Response("File Updated", 200)


@files.put("/change_status")
@check_token
def change_status():
    """
    Change the status of a file case from Firebase Storage.
    ---
    tags:
        - files
    summary: Change the status
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
                    $ref: '#/components/schemas/FileStatus'
    responses:
        200:
            description: Status changed
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
    reviewer: str = decoded_token.get("uid")
    data: dict = request.get_json()

    # exceptions
    if data.get("decision") < 3 or data.get("decision") > 5:
        raise BadRequest("Unsupported decision type.")

    # fetch the file data from firestore
    file_ref = db.collection("Files").document(data.get("file_id"))
    if file_ref.get().exists == False:
        raise NotFound("The file not found")
    file: dict = file_ref.get().to_dict()

    user_ref = db.collection("User").document(reviewer).get()
    if user_ref.exists == False:
        raise NotFound("The user not found")
    user: dict = user_ref.to_dict()

    # Only the reviewer, and admin have access to change the status of the file
    if reviewer != file.get("reviewer") and user.get("role") != "admin":
        raise Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    if "comment" in data:
        file_ref.update({u"comment": data.get("comment")})

    file_ref.update({u"status": data.get("decision")})

    return Response("Status changed", 200)


@files.get("/get_user_files")
@check_token
def get_user_files() -> Response:
    """
    Get a file from Firebase Storage.
    ---
    tags:
        - files
    summary: Gets a file
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
                            $ref: '#/components/schemas/RecentFile'
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

    file_docs: list = (
        db.collection("Files")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .where("author", "==", uid)
        .limit(10)
        .stream()
    )

    files: list = []
    for file in file_docs:
        files.append(file.to_dict())

    return jsonify(files), 200


@files.get("/get_next_user_files_page")
@check_token
def get_next_event_page() -> Response:
    """
    Get next 10 user files from Firebase.
    ---
    tags:
        - files
    summary: Get next 10 user files from Firebase by passing file id.
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
        - in: header
          name: ID
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
                            $ref: '#/components/schemas/RecentFile'
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

    try:
        document: list = []
        files: list = []

        # Get ID of last event from client-side
        file_id: str = request.headers["ID"]

        # Get reference to document with that ID
        last_ref = db.collection("Files").where("id", "==", file_id).stream()
        for doc in last_ref:
            document.append(doc.to_dict())

        # Get the next batch of documents that come after the last document we received a reference to before
        docs = (
            db.collection("Files")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .where("author", "==", uid)
            .start_after(document[0])
            .limit(10)
            .stream()
        )
        for doc in docs:
            files.append(doc.to_dict())

        return jsonify(files), 200

    except:
        return InternalServerError("Failed event retrieved")
