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
from flask.helpers import make_response
from werkzeug.exceptions import BadRequest, NotFound, UnsupportedMediaType
from firebase_admin import storage
from io import BytesIO

from src.common.database import db
from src.api import Blueprint

files: Blueprint = Blueprint('files', __name__)


@files.post('/upload_file')
def upload_file() -> Response:
    """
    Upload a PDF file to Firebase Storage.
    ---
    tags:
        - files
    summary: Uploads a file
    requestBody:
        content:
            multipart/form-data:
                schema:
                    type: object
                    properties:
                        file:
                            type: string
                            format: binary
                encoding:
                    file:
                        contentType: application/pdf
    responses:
        201:
            description: File uploaded
        400:
            description: Bad request - no file was provided
        415:
            description: Unsupported media type. Provide a valid PDF
        500:
            description: Internal API Error
    """
    if "file" in request.files:
        file = request.files["file"]
    else:
        raise BadRequest("There was no file provided")

    if file.content_type != "application/pdf":
        raise UnsupportedMediaType(
            "Unsupported media type. The endpoint only accepts PDFs"
        )

    bucket = storage.bucket()
    blob = bucket.blob(file.filename)
    blob.upload_from_string(file.read(), content_type=file.content_type)

    res = {
        "status": "Success",
        "message": "File was successfully uploaded"
    }

    return res, 201


@files.get('/get_file/<filename>/')
def get_file(filename: str) -> Response:
    """
    Get a file from Firebase Storage.
    ---
    tags:
        - files
    summary: Gets a file
    parameters:
        - name: filename
          in: path
          schema:
              type: string
          description: The filename
          required: true
    responses:
        200:
            content:
                application/pdf:
                    schema:
                        type: string
                        format: binary
        404:
            description: The file with the given filename was not found
        500:
            description: Internal API Error
    """
    bucket = storage.bucket()
    blob = bucket.blob(filename)
    if not blob.exists():
        return NotFound("The file with the given filename was not found.")

    data = blob.download_as_bytes()
    return send_file(BytesIO(data), attachment_filename=filename, as_attachment=True)


@files.delete('/delete_file/<filename>/')
def delete_file(filename: str) -> Response:
    """
    Delete a file from Firebase Storage.
    ---
    tags:
        - files
    summary: Deletes a file
    parameters:
        - name: filename
          in: path
          schema:
              type: string
          description: The filename
          required: true
    responses:
        200:
            description: File deleted
        404:
            description: The file with the given filename was not found
        500:
            description: Internal API Error
    """
    bucket = storage.bucket()
    blob = bucket.blob(filename)
    if not blob.exists():
        return NotFound("The file with the given filename was not found.")
    blob.delete()

    res = {
        "status": "Success",
        "message": "File was successfully deleted"
    }

    return res, 200
