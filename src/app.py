from flask.wrappers import Response
from api.roles import roles
from api.events import events
from flask import Flask, jsonify
from flasgger import Swagger

app = Flask(__name__)

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
    ]
}
swagger = Swagger(app, template=swagger_specs)

app.register_blueprint(events)
app.register_blueprint(roles)


@app.errorhandler(404)
def page_not_found(e) -> Response:
    return jsonify({'Message': "Endpoint doesn't exist"})


if __name__ == '__main__':
    app.run(host='localhost', port=5000, debug=True)
