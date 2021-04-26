import smtplib
import os

def send_invite_email(emails, document_id):
    
    # Change deep link when deployed as standalone app
    deep_link_url = f"exp://192.168.1.12:19000/--/invite/{document_id}"


    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.ehlo()
    server.starttls()
    server.ehlo()

    server.login('YOUR_EMAIL_HERE', 'PASSWORD_HERE')

    subject = 'Mercury: Event Invite'
    body = f"You're invited to this event {deep_link_url}"
    signature = '-The Mercury Team'

    msg = f"Subject: {subject}\n\n{body}\n\n{signature}"

    for email in emails:
        server.sendmail('YOUR_EMAIL_HERE', 'RECIPIENT_EMAIL_HERE', msg)
    server.quit()