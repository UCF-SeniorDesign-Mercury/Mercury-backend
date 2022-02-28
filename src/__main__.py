# -*- coding: utf-8 -*-
"""
    src.__main__
    ~~~~~~~~~~~~
    Handles arguments from the cli and runs the app.
    Functions:
        page_not_found()
"""
from flask.wrappers import Response
from src.api.roles import roles
from src.api.events import events
from src.api.files import files
from src.api.notifications import notifications
from src.api.users import users
from flask import Flask, jsonify
from flask_cors import CORS
from flasgger import Swagger
from os import path, environ
import yaml
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

schemapath = path.join(path.abspath(path.dirname(__file__)), "schemas.yml")
schemastream = open(schemapath, "r")
schema = yaml.load(schemastream, Loader=yaml.FullLoader)
schemastream.close()

swagger_specs = {
    "openapi": "3.0.3",
    "swagger": "3.0.3",
    "info": {
        "title": "Mercury Backend API",
        "description": "Backend API for Mercury",
        "contact": {
            "name": "Mercury Backend Team",
            "url": "https://github.com/UCF-SeniorDesign-Mercury/Mercury-backend/issues",  # noqa: E501
        },
    },
    "servers": [
        {
            "url": "http://localhost:5000",
            "description": "Local Development server",
        }
    ],
    "basepath": "/apidocs",
    "schemes": ["http", "https"],
    "components": {
        "schemas": schema,
    },
}
swagger = Swagger(app, template=swagger_specs)

app.register_blueprint(events, url_prefix="/events")
app.register_blueprint(roles, url_prefix="/roles")
app.register_blueprint(files, url_prefix="/files")
app.register_blueprint(users, url_prefix="/users")
app.register_blueprint(notifications, url_prefix="/notifications")


@app.errorhandler(404)
def page_not_found(e) -> Response:
    return jsonify({"Message": "Endpoint doesn't exist"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(environ.get("PORT", 8080)), debug=True)
    # app.run(host="localhost", port=int(environ.get("PORT", 5000)), debug=True)
