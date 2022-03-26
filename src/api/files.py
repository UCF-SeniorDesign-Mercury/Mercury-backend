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
        review_user_files()
        get_recommend_files()
        give_recommendation()
"""
from src.common.decorators import check_token
from src.common.database import db
from src.api import Blueprint
from firebase_admin import storage, auth, firestore
from flask import Response, request, jsonify
from uuid import uuid4
from src.api.notifications import create_notification
from werkzeug.exceptions import (
    InternalServerError,
    BadRequest,
    NotFound,
    Unauthorized,
    UnsupportedMediaType,
)

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
                    $ref: '#/components/schemas/UploadFile'
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
    file_path: str = "file/" + file_id
    signature_path: str = "signature/" + signature_id
    data: dict = request.get_json()

    # get user table
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    # Exceptions
    if "file" not in data or not data.get("file").strip():
        return BadRequest("There was no file provided")
    else:
        file = data.get("file")

    if (
        data.get("filetype") != "rst_request"
        and data.get("filetype") != "1380_form"
    ):
        return UnsupportedMediaType(
            "Unsupported file. The endpoint only accepts rst_request and 1380_form"
        )

    if user.get("signature") == None and data.get("signature") == None:
        return BadRequest("Missing the signature")

    if "reviewer" not in data or not data.get("reviewer").strip():
        return BadRequest("Missing the reviewer")

    if "filename" not in data or not data.get("filename").strip():
        return BadRequest("Missing the filename")

    # save data to firestore batabase
    entry: dict = dict()
    entry["id"] = file_id
    entry["author"] = uid
    entry["timestamp"] = firestore.SERVER_TIMESTAMP
    entry["filetype"] = data.get("filetype")
    entry["filename"] = data.get("filename")
    entry["status"] = 1
    entry["reviewer"] = data.get("reviewer")
    entry["comment"] = ""
    entry["reviewer_visible"] = True
    if "recommender" in data and data.get("filetype") == "rst_request":
        if not data.get("recommender").strip():
            return BadRequest("Missing the recommender")
        entry["recommender"] = data.get("recommender")
        entry["reviewer_visible"] = False
        # notification send to recommender
        try:
            create_notification(
                notification_type="recommend file",
                type=data.get("filetype"),
                id=file_id,
                sender=uid,
                receiver_dod=data.get("recommender"),
                receiver_uid=None,
            )
        except:
            return NotFound("The recommender was not found")
    else:
        # notification send to reviewer
        try:
            create_notification(
                notification_type="review file",
                type=data.get("filetype"),
                sender=uid,
                id=file_id,
                receiver_dod=data.get("reviewer"),
                receiver_uid=None,
            )
        except:
            return NotFound("The reviewer was not found")

    db.collection("Files").document(file_id).set(entry)

    try:
        # save pdf to firestore storage
        bucket = storage.bucket()
        blob = bucket.blob(file_path)
        blob.upload_from_string(file, content_type="application/pdf")
    except:
        return InternalServerError("Could not save pdf")

    # update signature
    if "signature" in data:
        if "signature" in user:
            signature_path = user.get("signature")
        try:
            # save signature image to firebase storage
            blob = bucket.blob(signature_path)
            blob.upload_from_string(data.get("signature"), content_type="image")
        except:
            return InternalServerError("Could not save signature")
        user_ref.update({"signature": signature_path})

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
                        $ref: '#/components/schemas/File'
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
    file_path: str = "file/" + file_id
    # get pdf from the firebase storage
    bucket = storage.bucket()
    blob = bucket.blob(file_path)

    if not blob.exists():
        return NotFound("The file with the given filename was not found.")

    # download the pdf file and add it to the file data
    file = blob.download_as_bytes()
    docs = db.collection("Files").where("id", "==", file_id).limit(1).stream()
    res: dict = dict()
    for doc in docs:
        res = doc.to_dict()
    res["file"] = file.decode("utf-8")

    # get the user table
    user_ref = db.collection("User").document(uid).get()
    if user_ref.exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.to_dict()

    # Only the author, reviewer, and admin have access to the data
    if (
        user.get("dod") != res.get("reviewer")
        and uid != res.get("author")
        and user.get("dod") != res.get("recommender")
        and decoded_token.get("admin") != True
    ):
        return Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    # download the pdf file and add it to the file data
    if "signature" not in user:
        return BadRequest("User need upload a signature")
    signature_path: str = user.get("signature")
    blob = bucket.blob(signature_path)
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
    file_path: str = "file/" + file_id

    # get file data from firestore
    file_ref = db.collection("Files").document(file_id)
    if not file_ref.get().exists:
        return NotFound("The file was not found")
    data: dict = file_ref.get().to_dict()

    # Only the author, reviewer, and admin have access to the data
    if (
        uid != data.get("reviewer")
        and uid != data.get("author")
        and decoded_token.get("admin") != True
    ):
        return Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    # delete the pdf from firebase storage
    bucket = storage.bucket()
    blob = bucket.blob(file_path)
    if not blob.exists():
        return NotFound("The file with the given filename was not found.")
    blob.delete()

    # delete the data from firesotre
    file_ref.delete()

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
    uid: str = decoded_token.get("uid")
    data: dict = request.get_json()

    # fetch the file data from firestore
    file_ref = db.collection("Files").document(data.get("file_id"))
    if file_ref.get().exists == False:
        return NotFound("The file not found")
    file: dict = file_ref.get().to_dict()

    # exceptions
    if not file_ref.get().exists:
        return NotFound("The file with the given filename was not found")

    if file.get("status") < 0 or file.get("status") > 3:
        return BadRequest("Files is not allow to change after decision made")

    # Only the author have access to update the file
    if uid != file.get("author"):
        return Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    # Only rst_request could have recommender
    if "recommender" in data and files.get("filetype") != "rst_request":
        return BadRequest("Only rst_request files could have recommender")

    if "recommender" in data:
        file_ref.update({"recommender": data.get("recommender")})
        try:
            # notification send to recommender
            create_notification(
                notification_type="recommend " + " file",
                type=data.get("filetype"),
                sender=uid,
                id=file.get("id"),
                receiver_uid=None,
                receiver_dod=data.get("recommender"),
            )
        except:
            return NotFound("The recommender was not found")

    if "filename" in data:
        file_ref.update({"filename": data.get("filename")})

    # save pdf to firestore storage
    bucket = storage.bucket()
    file_path: str = "file/" + data.get("file_id")
    if "file" in data:
        blob = bucket.blob(file_path)
        blob.upload_from_string(
            data.get("file"), content_type="application/pdf"
        )

    # save pdf to firestore storage
    if "signature" in data:
        # get the user table
        user_ref = db.collection("User").document(uid).get()
        if user_ref.exists == False:
            return NotFound("The user was not found")
        user: dict = user_ref.to_dict()
        signature_path: str = "signature/" + user.get("signature")
        try:
            blob = bucket.blob(signature_path)
            blob.upload_from_string(data.get("signature"), content_type="image")
        except:
            return InternalServerError("cannot update signature to storage")

    file_ref.update({"timestamp": firestore.SERVER_TIMESTAMP})

    return Response("File Updated", 200)


@files.put("/review_file")
@check_token
def review_file():
    """
    Review the file from Firebase Storage.
    ---
    tags:
        - files
    summary: Review the file
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
                    $ref: '#/components/schemas/ReviewFile'
    responses:
        200:
            description: Status changed
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
    reviewer_uid: str = decoded_token.get("uid")
    data: dict = request.get_json()

    # exceptions
    if (
        "decision" not in data
        or data.get("decision") < 3
        or data.get("decision") > 5
    ):
        return BadRequest("Unsupported decision type")

    if "file_id" not in data or not data.get("file_id").strip():
        return BadRequest("Missing the file id")

    if "file" not in data or not data.get("file").strip():
        return BadRequest("Missing the file")

    # get the user table
    reviewer_ref = db.collection("User").document(reviewer_uid).get()
    if reviewer_ref.exists == False:
        return NotFound("The user was not found")
    reviewer: dict = reviewer_ref.to_dict()

    # fetch the file data from firestore
    file_ref = db.collection("Files").document(data.get("file_id"))
    if file_ref.get().exists == False:
        return NotFound("The file not found")
    file: dict = file_ref.get().to_dict()

    # Only the reviewer, and admin have access to change the status of the file
    if (
        reviewer.get("dod") != file.get("reviewer")
        and decoded_token.get("admin") != True
    ):
        return Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    if "comment" in data:
        file_ref.update({"comment": data.get("comment")})

    file_ref.update(
        {
            "status": data.get("decision"),
            "timestamp": firestore.SERVER_TIMESTAMP,
        }
    )

    # update the file in the storage
    bucket = storage.bucket()
    file_path: str = "file/" + data.get("file_id")
    blob = bucket.blob(file_path)
    blob.upload_from_string(data.get("file"), content_type="application/pdf")

    # notified user the decision
    try:
        if data.get("decision") == 3:
            create_notification(
                notification_type="resubmit file",
                type=file.get("filetype"),
                sender=reviewer_uid,
                id=data.get("file_id"),
                receiver_uid=file.get("author"),
                receiver_dod=None,
            )
        elif data.get("decision") == 4:
            create_notification(
                notification_type="file approved",
                type=file.get("filetype"),
                sender=reviewer_uid,
                id=data.get("file_id"),
                receiver_uid=file.get("author"),
                receiver_dod=None,
            )
        elif data.get("decision") == 5:
            create_notification(
                notification_type="file rejected",
                type=file.get("filetype"),
                sender=reviewer_uid,
                id=data.get("file_id"),
                receiver_uid=file.get("author"),
                receiver_dod=None,
            )
    except:
        return NotFound("The author was not found")

    return Response("Status changed", 200)


@files.get("/get_user_files")
@check_token
def get_user_files() -> Response:
    """
    Get the user  files from Firebase Storage.
    ---
    tags:
        - files
    summary: Gets user files
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
        - in: query
          name: status
          schema:
            type: integer
          required: false
        - in: query
          name: page_limit
          schema:
            type: integer
          required: false
        - in: query
          name: filetype
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
                            $ref: '#/components/schemas/UserFiles'
        400:
            description: Bad request
        401:
            description: Unauthorized - the provided token is not valid
        500:
            description: Internal API Error
    """
    # check tokens and get uid from token
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")
    # the default page limits is 10
    page_limit: int = 10

    if "page_limit" in request.args:
        page_limit = request.args.get("page_limit", default=10, type=int)

    file_docs: list = []
    filetype: str = request.args.get("filetype", type=str)
    status: int = request.args.get("status", type=int)
    # both status and filetype search
    if "status" in request.args and "filetype" in request.args:
        file_docs = (
            db.collection("Files")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .where("author", "==", uid)
            .where("status", "==", status)
            .where("filetype", "==", filetype)
            .limit(page_limit)
            .stream()
        )
    elif "status" in request.args:
        file_docs = (
            db.collection("Files")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .where("author", "==", uid)
            .where("status", "==", status)
            .limit(page_limit)
            .stream()
        )
    elif "filetype" in request.args:
        file_docs = (
            db.collection("Files")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .where("author", "==", uid)
            .where("filetype", "==", filetype)
            .limit(page_limit)
            .stream()
        )
    else:
        file_docs = (
            db.collection("Files")
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .where("author", "==", uid)
            .limit(page_limit)
            .stream()
        )

    files: list = []
    for file in file_docs:
        files.append(file.to_dict())

    return jsonify(files), 200


@files.get("/get_review_files")
@check_token
def get_review_files() -> Response:
    """
    Get 10 unreviewed user files from Firebase.
    ---
    tags:
        - files
    summary: Get 10 unreviewed user files from Firebase.
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
        - in: query
          name: page_limit
          schema:
            type: integer
          required: false
        - in: query
          name: status
          schema:
            type: integer
          required: false
        - in: query
          name: filetype
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
                            $ref: '#/components/schemas/UserFiles'
        400:
            description: Bad request
        401:
            description: Unauthorized - the provided token is not valid
        500:
            description: Internal API Error
    """
    # check tokens and get uid from token
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")
    # get the user table
    user_ref = db.collection("User").document(uid).get()
    if user_ref.exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.to_dict()
    files: list = []

    # Get the page limits, filetype, status from the front-end if exists
    page_limit: int = request.args.get("page_limit", default=10, type=int)
    filetype: str = request.args.get("filetype", type=str)
    status: int = request.args.get("status", type=int)

    # Admins could review all files
    if decoded_token.get("admin") == True:
        # Get the next batch of documents that come after the last document we received a reference to before
        if "status" in request.args and "filetype" in request.args:
            file_docs = (
                db.collection("Files")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("status", "==", status)
                .where("filetype", "==", filetype)
                .limit(page_limit)
                .stream()
            )
        elif "status" in request.args:
            file_docs = (
                db.collection("Files")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("status", "==", status)
                .limit(page_limit)
                .stream()
            )
        elif "filetype" in request.args:
            file_docs = (
                db.collection("Files")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("filetype", "==", filetype)
                .limit(page_limit)
                .stream()
            )
        else:
            file_docs = (
                db.collection("Files")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(page_limit)
                .stream()
            )
    # Reviewers could only review the files assigned to them
    else:
        # Get the next batch of documents that come after the last document we received a reference to before
        if "status" in request.args and "filetype" in request.args:
            file_docs = (
                db.collection("Files")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("reviewer", "==", user.get("dod"))
                .where("status", "==", status)
                .where("filetype", "==", filetype)
                .where("reviewer_visible", "==", True)
                .limit(page_limit)
                .stream()
            )
        elif "status" in request.args:
            file_docs = (
                db.collection("Files")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("reviewer", "==", user.get("dod"))
                .where("status", "==", status)
                .where("reviewer_visible", "==", True)
                .limit(page_limit)
                .stream()
            )
        elif "filetype" in request.args:
            file_docs = (
                db.collection("Files")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("reviewer", "==", user.get("dod"))
                .where("filetype", "==", filetype)
                .where("reviewer_visible", "==", True)
                .limit(page_limit)
                .stream()
            )
        else:
            file_docs = (
                db.collection("Files")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .where("reviewer", "==", user.get("dod"))
                .where("reviewer_visible", "==", True)
                .limit(page_limit)
                .stream()
            )

    for doc in file_docs:
        files.append(doc.to_dict())

    return jsonify(files), 200


@files.get("/get_recommend_files")
@check_token
def get_recommend_files() -> Response:
    """
    Get 10 unreviewed user files from Firebase.
    ---
    tags:
        - files
    summary: Get 10 unreviewed user files from Firebase.
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
        - in: query
          name: page_limit
          schema:
            type: integer
          required: false
    responses:
        200:
            content:
                application/json:
                    schema:
                        type: array
                        items:
                            $ref: '#/components/schemas/UserFiles'
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
    if user_ref.exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.to_dict()
    files: list = []

    # Get the page limits, filetype, status from the front-end if exists
    page_limit: int = request.args.get("page_limit", default=10, type=int)

    file_docs = (
        db.collection("Files")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .where("recommender", "==", user.get("dod"))
        .where("status", "in", [1, 2, 3])
        .limit(page_limit)
        .stream()
    )

    for doc in file_docs:
        files.append(doc.to_dict())

    return jsonify(files), 200


@files.put("/give_recommendation")
@check_token
def give_recommendation():
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
                    $ref: '#/components/schemas/RecommendFile'
    responses:
        200:
            description: "Recommendation is posted"
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
    data: dict = request.get_json()

    # exceptions
    if "file_id" not in data or not data.get("file_id").strip():
        return BadRequest("Missing the file id")

    if "file" not in data or not data.get("file").strip():
        return BadRequest("Missing the file")

    if "is_recommended" not in data:
        return BadRequest("Missing the recommendation result")

    # get the user table
    recommender_ref = db.collection("User").document(uid).get()
    if recommender_ref.exists == False:
        return NotFound("The user was not found")
    recommender: dict = recommender_ref.to_dict()

    # fetch the file data from firestore
    file_ref = db.collection("Files").document(data.get("file_id"))
    if not file_ref.get().exists:
        return NotFound("The file not found")
    file: dict = file_ref.get().to_dict()

    # Only the recommender have access to give recommendation of the file
    if recommender.get("dod") != file.get("recommender"):
        return Unauthorized(
            "The user is not authorized to retrieve this content"
        )

    if "comment" in data:
        file_ref.update({"comment": data.get("comment")})

    file_ref.update(
        {
            "is_recommended": data.get("is_recommended"),
            "reviewer_visible": True,
            "status": 2,
            "timestamp": firestore.SERVER_TIMESTAMP,
        }
    )

    # update the file from storage
    bucket = storage.bucket()
    file_path: str = "file/" + data.get("file_id")
    blob = bucket.blob(file_path)
    blob.upload_from_string(data.get("file"), content_type="application/pdf")

    # notified the user the decision
    try:
        if data.get("is_recommended"):
            create_notification(
                notification_type="positive recommendation",
                type=file.get("filetype"),
                sender=uid,
                id=data.get("file_id"),
                receiver_uid=file.get("author"),
                receiver_dod=None,
            )
        else:
            create_notification(
                notification_type="negative recommendation",
                type=file.get("filetype"),
                sender=uid,
                id=data.get("file_id"),
                receiver_uid=file.get("author"),
                receiver_dod=None,
            )
        # notified the reviewer to review this file
        create_notification(
            notification_type="review file",
            type=file.get("filetype"),
            sender=uid,
            id=data.get("file_id"),
            receiver_dod=file.get("reviewer"),
            receiver_uid=None,
        )
    except:
        return NotFound("The reviewer was not found")

    return Response("Recommend post", 200)
