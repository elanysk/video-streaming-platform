import logging

from bson import ObjectId
from flask import Blueprint, current_app, render_template, make_response, request, g
import os
from email_validator import validate_email
from urllib.parse import quote
from .log_util import get_logger
import smtplib
from email.mime.text import MIMEText
from email import charset
from .util import db, error, success, validate_session, DOMAIN
from .routes import check_session
from .collaborative_filtering import rec_algo
from config import POSTFIX_IP

import jwt

auth = Blueprint('auth', __name__)
logger = get_logger("/api/adduser")

@auth.route('/testmail', methods=['GET'])
def testmail():
    try:
        email = request.args["email"]
        print(email + '\n')
        from_addr = "root@esk-pj-air.cse356.compas.cs.stonybrook.edu"
        to_addr = email
        verify_key = os.urandom(12).hex()
        body = f"http://{DOMAIN}/verify?email={quote(email)}&key={verify_key}"
        cs = charset.Charset('utf-8')
        cs.body_encoding = charset.QP
        msg = MIMEText(body, 'plain', cs)
        print(msg.as_string())
        s = smtplib.SMTP('localhost', 25)
        s.sendmail(from_addr, to_addr, msg.as_string())
        s.quit()
        return success({})
    except Exception as e:
        return error(str(e))


@auth.route('/api/adduser', methods=['POST'])
def add_user():
    users = db.users
    try:
        username = request.json['username']
        password = request.json['password']
        email = request.json['email']
        if username and password and validate_email(email):
            existing_user = users.find_one({"username": username})
            existing_email = users.find_one({"email": email})
            if existing_user or existing_email:
                raise Exception("User or email already exists")
            # verify_key = create_access_token(identity=email, expires_delta=False)
            verify_key = os.urandom(12).hex()
            user_id = users.insert_one({"username": username,
                              "password": password,
                              "email": email,
                              "validated": False,
                              "videos": [],
                              "watched": [],
                              "verify-key": verify_key}).inserted_id
            rec_algo.add_user(str(user_id))

            cs = charset.Charset('utf-8')
            cs.body_encoding = charset.QP
            from_addr = "root@esk-pj-air.cse356.compas.cs.stonybrook.edu"
            to_addr = email
            body = f"Please verify your email for eskpj-airplanes video viewer at the following link: https://{DOMAIN}/api/verify?email={quote(email)}&key={verify_key}"
            msg = MIMEText(body, 'plain', cs)
            msg['From'] = from_addr
            msg['To'] = to_addr
            msg['Subject'] = "Verify your email with ESKPJ"
            msg['Message-ID'] = f"<{os.urandom(12).hex()}@esk-pj-air.cse356.compas.cs.stonybrook.edu>"
            s = smtplib.SMTP(POSTFIX_IP, 25)
            s.sendmail(from_addr, to_addr, msg.as_string())
            s.quit()
            return success({'message': "Email sent"})
        return success({"message": "User successfully added"})
    except Exception as e:
        return error(str(e))


@auth.route('/api/login', methods=['POST'])
def login():
    users = db.users
    try:
        username = request.json['username']
        password = request.json['password']
        if not (username and password and (user := users.find_one({"username": username}))):
            raise Exception("username not found")
        if user["password"] == password and user["validated"]:
            success_msg = {"message" :"Login successful"}
            access_token = jwt.encode({"_id": str(user['_id'])}, current_app.config["SECRET_KEY"], algorithm="HS256")
            users.update_one({"_id": user['_id']}, {"$set": {"token": access_token, "login": True}})
            return success(success_msg, access_token)
        else:
            if user["password"] != password:
                raise Exception("Invalid password")
            else:
                raise Exception("User not validated")
    except Exception as e:
        print(e)
        return error(str(e))

# He specifies to use query string params for the verify endpoint
@auth.route('/api/verify', methods=['GET'])
def verify():
    users = db.users
    try:
        email = request.args["email"]
        verify_key = request.args["key"]
        user = users.find_one({"email": email})
        if not user:
            raise Exception("User not found")
        saved_token = user["verify-key"]
        if saved_token == verify_key:
            users.update_one({"email": email}, {"$set": {"validated": True}})
            return success({})
        else:
            raise Exception("Invalid verification key")
        return
    except Exception as e:
        return error(str(e))


@auth.route('/api/logout', methods=["POST"])
@check_session
def logout():
    try:
        db.users.update_one({"_id": ObjectId(g.user["id"])}, {"$set": {"token": None, "login": False}})
        response = success({"message": "Logout successful"})
        response.delete_cookie("token")
        return response
    except Exception as e:
        return error(str(e))


@auth.route('/api/check-auth', methods=["POST"])
def check_auth():
    try:
        if "token" not in request.cookies:
            raise Exception("You do not have an active session token")
        if user := validate_session(request.cookies["token"]):
            return success({"isLoggedIn": user["login"], "userId": str(user["_id"])})
    except Exception as e:
        return error(str(e))
