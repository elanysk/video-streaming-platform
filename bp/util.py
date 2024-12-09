from bson import ObjectId
from pymongo import MongoClient
from flask import make_response, request, current_app, render_template
import traceback
import json
import jwt
from config import MONGO_IP
from .log_util import get_logger

DOMAIN = "esk-pj-air.cse356.compas.cs.stonybrook.edu"
SUBMIT_ID = "66d216517f77bf55c5005074"

def connect_db():
    try:
        client = MongoClient(MONGO_IP, 27017)
        db = client.eskpj_airplanes
        return db
    except Exception as e:
        return error(str(e))

db = connect_db()

# error handling
def error(err_msg):
    traceback.print_exc()
    resp = json.dumps({"status":"ERROR","error":True,"message": err_msg}), 200, {'Content-Type': 'application/json', 'X-CSE356': SUBMIT_ID}
    resp = make_response(resp)
    return resp

# valid response handling
# @param data: dictionary of data to be returned
# @param token: token to be set in the cookie
def success(data, token=None):
    data["status"]="OK"
    body = json.dumps(data, separators=(',', ':')) # take out any spaces in json response
    response = make_response(body)
    if token:
        response.set_cookie("token", value=token, httponly=False)
    response.headers["X-CSE356"] = SUBMIT_ID
    return response

# validate session
def validate_session(token):
    with current_app.app_context():
        identity = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        user = db.users.find_one({"_id": ObjectId(identity["_id"])})
        if user and user["token"] == request.cookies["token"]: return user
        return None
