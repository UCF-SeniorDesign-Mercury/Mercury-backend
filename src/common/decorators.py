# -*- coding: utf-8 -*
"""
    src.common.decorators
    ~~~~~~~~~~~~~~~~~~~~~
    Functions:
        check_token()
        admin_only()
"""
from functools import wraps
from flask import json, request, jsonify
from firebase_admin import auth
from werkzeug.exceptions import Unauthorized
import os


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
        if not request.headers.get("Authorization"):
            raise Unauthorized("Authorization token not provided")

        token: str = request.headers["Authorization"]

        try:
            auth.verify_id_token(token, check_revoked=True)

        except auth.ExpiredIdTokenError:
            raise Unauthorized("Token expired")

        except auth.InvalidIdTokenError:
            raise Unauthorized("Invalid token")

        except auth.RevokedIdTokenError:
            raise Unauthorized("Token revoked")

        except:
            raise Unauthorized("Invalid Token")

        return f(*args, **kwargs)

    return wrap


def admin_only(f):
    """
    This decorator ensures that the following resource is only available to Admins
    """

    @wraps(f)
    def wrap(*args, **kwargs):
        if os.getenv("FLASK_ENV") == "DEBUG":
            pass

        token: str = request.headers["Authorization"]
        decoded_token: dict = auth.verify_id_token(token)

        if decoded_token["admin"] is False:
            raise Unauthorized("You don't have the access rights")

        return f(*args, **kwargs)

    return wrap
