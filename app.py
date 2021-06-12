from firebase_admin import credentials, firestore, initialize_app
from flask import Flask, jsonify


app = Flask(__name__)
cred = credentials.Certificate('key.json')
firebase_app = initialize_app(cred)
db = firestore.client()

from Events.routes import events
from Roles.routes import roles

app.register_blueprint(events)
app.register_blueprint(roles)


@app.errorhandler(404)
def page_not_found(e):
    return jsonify({'Message': "Endpoint doesn't exist"})


if __name__ == '__main__':
    app.run(host='192.168.1.12', debug=True)