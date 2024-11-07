import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader
from flask import url_for
from dotenv import load_dotenv
import os

def send_participation_email(user_email, event_id, event_title, longitude, latitude):
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")


    subject = "Participation Confirmation"
    content = f"Thank you for participating in the event, you can browse more events in the link below."
    event_link = f"http://localhost:5000/"
    longitude = float(longitude)
    latitude = float(latitude)

    map_url = f"https://www.openstreetmap.org/export/embed.html?bbox={longitude-0.01},{latitude-0.01},{longitude+0.01},{latitude+0.01}&layer=mapnik"
    print(map_url)

    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('mailtemplate_2.html')  


    body = template.render(subject=subject, content=content, event_link=event_link,
                            event_id=event_id, event_title=event_title,
                            longitude=longitude, latitude=latitude, map_url=map_url)


    msg = MIMEMultipart()
    msg['From'] = "EventifySESAME"
    msg['To'] = user_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, user_email, msg.as_string())
            print("Confirmation email sent.")
    except Exception as e:
        print(f"Error sending email: {e}")





def send_confirmation_email(user_email, user_id):
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD") 

    subject = "Activate Your Account"
    content = "Please click the link below to activate your account."
    activation_link = f"http://localhost:5000/activate/{user_id}"

    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('mailtemplate.html') 

    body = template.render(subject=subject, content=content, activation_link=activation_link)

    msg = MIMEMultipart()
    msg['From'] = "EventifySESAME"
    msg['To'] = user_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, user_email, msg.as_string())
            print("Confirmation email sent.")
    except Exception as e:
        print(f"Error sending email: {e}")
