from firebase_admin import credentials, auth, firestore, initialize_app
from flask import Flask, Response, request, jsonify
from functools import wraps

app = Flask(__name__)
cred = credentials.Certificate('key.json')
firebase_app = initialize_app(cred)
db = firestore.client()

def check_token(f):
    """
    This decorator verifies user idToken for protected routes so that only valid idTokens may access them
    """
    @wraps(f)
    def wrap(*args, **kwargs):
        """
        Receives idToken from the front-end and attempts to verify idToken and if successful, then access to protected route is granted.
        If the idToken is invalid for any reason whether it's expired or revoked, a corresponding error message is returned instead and access to protected route is denied.
        """

        #token = request.args.get('token')

        #print(request.headers)
        token = request.headers['Authorization']

        try:
            auth.verify_id_token(token, check_revoked=True)

        except auth.ExpiredIdTokenError:
            return jsonify({'Error message': 'Token expired'}), 403

        except auth.InvalidIdTokenError:
            return jsonify({'Error message': 'Invalid token'}), 403

        except auth.RevokedIdTokenError:
            return jsonify({'Error message': 'Token revoked'}), 403
        
        except:
            try:
                token = request.args.get('token')
                auth.verify_id_token(token, check_revoked=True)
            except:
                return jsonify({'Error message': 'Invalid Token'}), 403

        return f(*args, **kwargs)
    return wrap


@app.route('/', methods=['GET'])
def home():
    return "Hello World"

@app.route('/test', methods=['GET'])
@check_token
def test():
    return jsonify({"Message": "It works!!!"})

if __name__ == '__main__':
    app.run(host='192.168.1.13', debug=True)