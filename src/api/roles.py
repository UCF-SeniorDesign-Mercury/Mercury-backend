# -*- coding: utf-8 -*
"""
    src.api.roles
    ~~~~~~~~~~~~~
    Functions:
        grant_role()
        create_role()
        get_all_roles()
        get_all_permissions()
        get_role_permissions()
        assign_role()
        invite_role()
        revoke_role()
"""
from firebase_admin import auth, firestore
from firebase_admin.auth import UserRecord
from flask import Response, jsonify, request

from src.api import Blueprint
from src.common.decorators import check_token, admin_only
from src.common.helpers import send_invite_email
from src.common.database import db

from werkzeug.exceptions import NotFound

roles: Blueprint = Blueprint("roles", __name__)


@roles.route("/grant_role")
@check_token
def grant_role() -> Response:
    """
    Granted a role for newly registered user.
    ---
    tags:
        - role
    summary: Upon newly registering a user, they are granted a role if their email used is matched to one in Roles/roleList document.
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
    responses:
        200:
            description: Successfully added role.
        404:
            description: Fail added role.
    """

    # Decode token to obtain user's firebase id
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)

    email: str = decoded_token["email"]
    uid: str = decoded_token["uid"]

    # Reference to roles document
    doc = db.collection("Roles").document("roleList").get()

    # Get role map of predefined users to roles
    roles: dict = doc.to_dict()["role"]
    role_to_assign = roles[email]

    try:
        auth.set_custom_user_claims(uid, {role_to_assign: True})

        # Map this new entry to roles_to_user
        doc_allRoles = db.collection("Roles").document("allRoles")
        doc_allRoles.set(
            {"roles_to_user": {role_to_assign: firestore.ArrayUnion([email])}},
            merge=True,
        )

        return Response(response="Successfully added role", status=200)
    except:
        return Response(response="Fail added role", status=400)


@roles.post("/create_role")
@check_token
@admin_only
def create_role() -> Response:
    """
    Creating a new custom role globally for the client side application.
    ---
    tags:
        - role
    summary: Create role
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: '#/components/schemas/Role'
        description: Create a role by admin
        required: true
    responses:
        200:
            description: Successfully create a role.
        401:
            description: Unauthorized.
    """
    token: str = request.headers["Authorization"]
    decoded_token: dict = auth.verify_id_token(token)

    if decoded_token["admin"] is True:

        data = request.get_json()["data"]
        role: str = data["roleName"]
        level: str = data["level"]

        doc_ref = db.collection("Roles").document("allRoles")
        doc_ref.set({"roles": {role: level}}, merge=True)

        doc_ref.update({"roleArray": firestore.ArrayUnion([role])})

        return Response(response="Successfully create a role", status=200)
    else:
        return Response(response="Unauthorized", status=401)


@roles.get("/get_all_roles")
@check_token
def get_all_roles() -> Response:
    """
    Retrieve all base roles from Firebase.
    ---
    tags:
        - role
    summary: Gets all base roles
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
    responses:
        200:
            content:
                application/json:
                    schema:
                        type: array
                        items:
                            type: string
                        example:  ["ara", "basic", "bn_cdr"]
        401:
            description: Unauthorized.
    """
    try:
        doc = db.collection("Roles").document("base_roles").get()
        data = doc.to_dict()
        return jsonify(data), 200
    except:
        return Response(response="Unauthorized", status=401)


# @roles.get("/get_all_permissions")
# @check_token
# def get_all_permissions() -> Response:
#     """
#     Retrieve all permissions.
#     ---
#     tags:
#         - role
#     summary: Gets all permissions
#     parameters:
#         - in: header
#           name: Authorization
#           schema:
#             type: string
#           required: true
#     responses:
#         200:
#             content:
#                 application/json:
#                     schema:
#                         type: array
#                         items:
#                             type: string
#                         example:  ["nurse", "doctor", "frontdesk"]
#         401:
#             description: Unauthorized.
#     """
#     try:
#         docs = db.collection("Permissions").stream()
#         data = {doc.id: doc.to_dict() for doc in docs}
#         return jsonify(data), 200
#     except:
#         return Response(response="Unauthorized", status=401)


@roles.post("/check_role_permissions")
@check_token
def check_role_permissions() -> Response:
    """
    Retrieve the permissions for the given roles and checks if the requested
    permissions falls under the role.
    ---
    tags:
        - role
    summary: Check role permissions
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
              schema:
                name: permissions
                type: string
            required: true
    responses:
        200:
        500:
        401:
    """
    token: str = request.headers["Authorization"]
    decoded_token = auth.verify_id_token(token)
    uid: str = decoded_token.get("uid")

    # check if the user exists
    user_ref = db.collection("User").document(uid)
    if user_ref.get().exists == False:
        return NotFound("The user was not found")
    user: dict = user_ref.get().to_dict()

    data: dict = request.get_json()
    requested_perm = data.get("permission")

    user_role: str = user.get("role")
    split_role = user_role.split("/")

    try:
        if len(split_role) > 1:
            role_doc = split_role[0]
            role = split_role[1]
        else:
            role_doc = "base_roles"
            role = split_role[0]

        doc = db.collection("Roles").document(role_doc).get()
        data = doc.to_dict()

        permissions_list = data[role]

        if requested_perm in permissions_list:
            return Response(status=200)
        else:
            return Response(status=401)
    except:
        return Response(status=500)


@roles.post("/assign_role")
@check_token
@admin_only
def assign_role() -> Response:
    """
    Assigns a custom role to a user and updates their level access accordingly
    ---
    tags:
        - role
    summary: Assign role
    parameters:
        - in: header
          name: Authorization
          schema:
            type: string
          required: true
    requestBody:
        content:
            application/json:
                schema:
                    $ref: '#/components/schemas/AssignRole'
        description: Assign a role by admin
        required: true
    responses:
        200:
            description: Successfully Assign a role.
        401:
            description: Email doesn't exist.
    """
    token: str = request.headers["Authorization"]
    decoded_token = auth.verify_id_token(token)

    if decoded_token["admin"] is True:

        doc_ref = db.collection("Roles").document("allRoles")
        doc = doc_ref.get()
        roles_dict = doc.to_dict()["roles"]

        data: dict = request.get_json()["data"]
        email: str = data["email"]
        role: str = data["role"]
        level: str = roles_dict[role]

        try:
            user: UserRecord = auth.get_user_by_email(email)
            current_custom_claims = user.custom_claims

            # User has no previous role in their custom claims
            if current_custom_claims is None:
                auth.set_custom_user_claims(
                    user.uid, {role: True, "accessLevel": level}
                )
                return Response(
                    response="Successfully assign a role", status=200
                )
            # User has a role set previously
            else:
                if current_custom_claims["accessLevel"] >= level:
                    current_custom_claims[role] = True
                else:
                    current_custom_claims["accessLevel"] = level
                    current_custom_claims[role] = True

                auth.set_custom_user_claims(user.uid, current_custom_claims)

                # Map this new entry to roles_to_user
                doc_ref.set(
                    {"roles_to_user": {role: firestore.ArrayUnion([email])}},
                    merge=True,
                )

                return Response(
                    response="Successfully assign a role", status=200
                )
        except:
            return Response(response="Email doesn't exist", status=400)


@roles.post("/invite_role")
@check_token
def invite_role() -> Response:
    """
    For inviting users with specified roles to an event. Users with the selected role will be emailed a link that opens up to the invited event

    Returns;
        Response of 200
    """
    data: dict = request.get_json()["data"]
    role: str = data["role"]
    event_id: str = data["event_id"]

    # Retrieve m"ap of roles to user from DB
    role_docs = db.collection("Roles").document("allRoles").get()
    roles_to_user = role_docs.to_dict()["roles_to_user"]

    # Retrieve list of emails that have a specific from the map
    emails = roles_to_user[role]

    event_docs = (
        db.collection("Scheduled-Events").where("id", "==", event_id).stream()
    )
    for doc in event_docs:
        doc_id = doc.id
        send_invite_email(emails, doc_id)

    return jsonify({"Message": "Complete"}), 200


@roles.post("/revoke_role")
@check_token
@admin_only
def revoke_role() -> Response:
    """
    Remove a role from a specificed user. Level is also updated if it's affected by the removal of role

    Returns:
        Response of 200 for successfully removing role from DB
    """
    data: dict = request.get_json()["data"]
    email: str = data["email"]
    role_to_remove: str = data["role"]
    new_level: int = 0

    user: UserRecord = auth.get_user_by_email(email)
    current_custom_claims = user.custom_claims
    try:
        if current_custom_claims[role_to_remove] is True:
            del current_custom_claims[role_to_remove]
            all_keys = list(current_custom_claims.keys())

            # Get map of roles to level from DB
            doc_ref = db.collection("Roles").document("allRoles")
            doc = doc_ref.get()
            roles_map = doc.to_dict()["roles"]

            for key in all_keys:
                if key != "accessLevel":
                    role_level = roles_map[key]

                    # if current level status is equal to one of user's existing roles' level
                    if role_level == current_custom_claims["accessLevel"]:
                        auth.set_custom_user_claims(
                            user.uid, current_custom_claims
                        )
                        return jsonify({"Message": "Complete"})

                    if role_level > new_level:
                        new_level = role_level

            current_custom_claims["accessLevel"] = new_level
            auth.set_custom_user_claims(user.uid, current_custom_claims)

            # Map this new entry to roles_to_user
            doc_ref.set(
                {
                    "roles_to_user": {
                        role_to_remove: firestore.ArrayRemove([email])
                    }
                },
                merge=True,
            )

        return jsonify({"Message": "Complete"}), 200
    except ValueError:
        return jsonify(
            {"Error": "Specified user ID or the custom claims are invalid"}
        )
    except:
        return jsonify({"Error": "User has no role to remove"})
