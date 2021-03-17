from functools import wraps
from flask import request, jsonify
from firebase_admin import auth

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
        if "Authorization" not in request.headers:
            return jsonify({'Error Message': 'Authorization token not provided'})

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