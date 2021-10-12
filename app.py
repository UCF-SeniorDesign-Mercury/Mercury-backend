from flask.wrappers import Response
from Roles.routes import roles
from Events.routes import events
from firebase_admin import credentials, firestore, initialize_app
from flask import Flask, jsonify


app = Flask(__name__)
cred = credentials.Certificate('key.json')
firebase_app = initialize_app(cred)
db = firestore.client()


app.register_blueprint(events)
app.register_blueprint(roles)


@app.errorhandler(404)
def page_not_found(e) -> Response:
    return jsonify({'Message': "Endpoint doesn't exist"})


if __name__ == '__main__':
    app.run(host='192.168.1.12', debug=True)
