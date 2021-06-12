from firebase_admin import auth, firestore
from flask import Blueprint, Response, jsonify, request

from decorators import check_token, admin_only
from helpers import send_invite_email
from app import db

roles = Blueprint('roles', __name__)


@roles.route('/grantRole')
@check_token
def grantRole():
    """
    Upon newly registering a user, they are granted a role if their email used is matched to one in Roles/roleList document.

    Returns: 
        Response of 200 of successfully adding role to user
    """

    # Decode token to obtain user's firebase id
    token = request.headers['Authorization']
    decoded_token = auth.verify_id_token(token)
    
    email = decoded_token['email']
    uid = decoded_token['uid']

    # Reference to roles document
    doc = db.collection(u'Roles').document(u'roleList').get()
    
    # Get role map of predefined users to roles
    roles = doc.to_dict()['role']
    role_to_assign = roles[email]

    try:
        auth.set_custom_user_claims(uid, {role_to_assign: True})

        # Map this new entry to roles_to_user
        doc_allRoles = db.collection(u'Roles').document(u'allRoles')
        doc_allRoles.set({
            u'roles_to_user': {
                role_to_assign: firestore.ArrayUnion([email])
            }
        }, merge=True)

        return Response(response="Successfully added role", status=200)
    except:
        return jsonify({"Message": "Not assigned a role"})




@roles.route('/createRole', methods=['POST'])
@check_token
@admin_only
def createRole():
    """
    Creating a new custom role globally for the client side application

    Returns:
        Returns 200
    """
    token = request.headers['Authorization']
    decoded_token = auth.verify_id_token(token)

    if decoded_token['admin'] is True:

        data = request.get_json()["data"]
        role = data['roleName']
        level = data['level']

        doc_ref = db.collection(u'Roles').document(u'allRoles')
        doc_ref.set({
            u'roles': {
                role:level
            }
        }, merge=True)

        doc_ref.update({u'roleArray': firestore.ArrayUnion([role])})
        

        return jsonify({"Message": "Complete"}), 200
    else:
        return jsonify({"Message": "Unauthorized"}), 401


@roles.route('/getAllRoles', methods=['GET'])
@check_token
def getAllRoles():
    """
    Retrieve all custom roles created by admins in /createRole to the app

    Returns:
        Array of custom roles created by admins
    """
    try:
        doc = db.collection(u'Roles').document(u'allRoles').get()
        data = doc.to_dict()['roleArray']
        return jsonify(data)
    except:
        return jsonify({"Message": "Unauthorized"}), 401


@roles.route('/assignRole', methods=['POST'])
@check_token
@admin_only
def assignRole():
    """
    Assigns a custom role to a user and updates their level access accordingly

    Returns:
        Success response of 200
    """
    token = request.headers['Authorization']
    decoded_token = auth.verify_id_token(token)

    if decoded_token['admin'] is True:

        doc_ref = db.collection(u'Roles').document(u'allRoles')
        doc = doc_ref.get()
        roles_dict = doc.to_dict()['roles']

        data = request.get_json()['data']
        email = data['email']
        role = data['role']
        level = roles_dict[role]

        try:
            user = auth.get_user_by_email(email)
            current_custom_claims = user.custom_claims

            # User has no previous role in their custom claims
            if current_custom_claims is None:
                auth.set_custom_user_claims(user.uid, {
                    role: True,
                    "accessLevel": level
                })
                return jsonify({"Message": "Complete"}), 200
            # User has a role set previously
            else:              
                if current_custom_claims["accessLevel"] >= level:
                    current_custom_claims[role] = True
                else:
                    current_custom_claims["accessLevel"] = level
                    current_custom_claims[role] = True
                
                auth.set_custom_user_claims(user.uid, current_custom_claims) 

               
                # Map this new entry to roles_to_user
                doc_ref.set({
                    u'roles_to_user': {
                    role: firestore.ArrayUnion([email])
                    }
                }, merge=True)
                

                return jsonify({"Message": "Complete"}), 200
        except:
            return jsonify({"Error": "Email doesn't exist"}), 400



@roles.route('/inviteRole', methods=['POST'])
@check_token
def inviteRole():
    """
    For inviting users with specified roles to an event. Users with the selected role will be emailed a link that opens up to the invited event

    Returns;
        Response of 200
    """
    data = request.get_json()['data']
    role = data['role']
    event_id = data['event_id']
    
    # Retrieve map of roles to user from DB
    role_docs = db.collection(u'Roles').document(u'allRoles').get()
    roles_to_user = role_docs.to_dict()['roles_to_user']

    # Retrieve list of emails that have a specific from the map
    emails = roles_to_user[role]

    event_docs = db.collection(u'Scheduled-Events').where(u'id', u'==', event_id).stream()
    for doc in event_docs:
        doc_id = doc.id
        send_invite_email(emails, doc_id)


    return jsonify({"Message": "Complete"}), 200




@roles.route('/revokeRole', methods=['POST'])
@check_token
@admin_only
def revokeRole():
    """
    Remove a role from a specificed user. Level is also updated if it's affected by the removal of role

    Returns:
        Response of 200 for successfully removing role from DB
    """
    data = request.get_json()['data']
    email = data['email']
    role_to_remove = data['role']
    new_level = 0

    user = auth.get_user_by_email(email)
    current_custom_claims = user.custom_claims
    try:        
        if current_custom_claims[role_to_remove] is True:
            del current_custom_claims[role_to_remove]
            all_keys = list(current_custom_claims.keys())
            
            # Get map of roles to level from DB
            doc_ref = db.collection(u'Roles').document(u'allRoles')
            doc = doc_ref.get()
            roles_map = doc.to_dict()['roles']
        
            for key in all_keys:
                if key != "accessLevel":
                    role_level = roles_map[key]

                    # if current level status is equal to one of user's existing roles' level
                    if role_level == current_custom_claims['accessLevel']:
                        auth.set_custom_user_claims(user.uid, current_custom_claims)
                        return jsonify({"Message": "Complete"})
                    
                    if role_level > new_level:
                        new_level = role_level

            current_custom_claims['accessLevel'] = new_level
            auth.set_custom_user_claims(user.uid, current_custom_claims)

            # Map this new entry to roles_to_user
            doc_ref.set({
                u'roles_to_user': {
                role_to_remove: firestore.ArrayRemove([email])
                }
            }, merge=True)

        return jsonify({"Message": "Complete"}), 200
    except ValueError:
        return jsonify({'Error': 'Specified user ID or the custom claims are invalid'})
    except:
        return jsonify({'Error': 'User has no role to remove'})