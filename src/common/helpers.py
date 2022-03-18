# -*- coding: utf-8 -*
"""
    src.common.helpers
    ~~~~~~~~~~~~~~~~~~
    Functions:
        send_invite_email()
"""
from smtplib import SMTP
from werkzeug.exceptions import NotFound
from firebase_admin import storage
import json


def send_invite_email(emails, document_id: str) -> None:

    # Change deep link when deployed as standalone app
    deep_link_url: str = f"exp://192.168.1.12:19000/--/invite/{document_id}"

    server: SMTP = SMTP("smtp.gmail.com", 587)
    server.ehlo()
    server.starttls()
    server.ehlo()

    server.login("YOUR_EMAIL_HERE", "PASSWORD_HERE")

    subject: str = "Mercury: Event Invite"
    body: str = f"You're invited to this event {deep_link_url}"
    signature: str = "-The Mercury Team"

    msg: str = f"Subject: {subject}\n\n{body}\n\n{signature}"

    for email in emails:
        server.sendmail("YOUR_EMAIL_HERE", "RECIPIENT_EMAIL_HERE", msg)
    server.quit()


def find_subordinates_by_dod(dod: str) -> list:
    bucket = storage.bucket()
    org_json_path: str = "org/org.json"
    blob = bucket.blob(org_json_path)
    if not blob.exists():
        return NotFound("The org chart file not found")
    # download the org tree
    org_file: str = blob.download_as_bytes().decode("utf-8")
    org: list = json.loads(org_file).get("org")

    for people in org:
        if people.get("dod") == dod:
            return people.get("sub")
        elif people.get("sub") != None:
            return find_subordinates_by_dod_recur(people.get("sub"), dod)
        else:
            continue


def find_subordinates_by_dod_recur(org: list, dod: str) -> list:
    for people in org:
        if people.get("dod") == dod:
            return people.get("sub")
        elif people.get("sub") != None:
            return find_subordinates_by_dod_recur(people.get("sub"), dod)
        else:
            continue
