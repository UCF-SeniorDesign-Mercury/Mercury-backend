from flask.wrappers import Response
from api.roles import roles
from api.events import events
from flask import Flask, jsonify

app = Flask(__name__)


app.register_blueprint(events)
app.register_blueprint(roles)


@app.errorhandler(404)
def page_not_found(e) -> Response:
    return jsonify({'Message': "Endpoint doesn't exist"})


if __name__ == '__main__':
    app.run(host='127.0.0.1', debug=True)
