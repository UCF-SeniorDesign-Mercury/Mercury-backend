from flask.wrappers import Response
from src.api.roles import roles
from src.api.events import events
from src.api.files import files
from flask import Flask, jsonify
from flasgger import Swagger
from os import path
import yaml

app = Flask(__name__)

schemapath = path.join(path.abspath(path.dirname(__file__)), "src/schemas.yml")
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
            "url": "https://github.com/UCF-SeniorDesign-Mercury/Mercury-backend/issues"  # noqa: E501
        }
    },
    "servers": [
        {
            "url": "http://localhost:5000",
            "description": "Local Development server"
        }
    ],
    "basepath": "/apidocs",
    "schemes": [
        "http",
        "https"
    ],
    "components": {
        "schemas": schema,
    }
}
swagger = Swagger(app, template=swagger_specs)

app.register_blueprint(events)
app.register_blueprint(roles)
app.register_blueprint(files)


@app.errorhandler(404)
def page_not_found(e) -> Response:
    return jsonify({'Message': "Endpoint doesn't exist"})


if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=True)
