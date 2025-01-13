# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


from os.path import dirname, join, realpath, basename
from flask import Blueprint, jsonify, request, session, flash, render_template
from app.utils_db import delete_url, delete_pod
from app.api.models import Urls, Pods
from app import db, OMD_PATH, AUTH_TOKEN
from app.auth.controllers import login_required

# Define the blueprint:
api = Blueprint('api', __name__, url_prefix='/api')

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'pods')


@api.route('/urls/delete', methods=["GET"])
@login_required
def api_delete():
    path = request.args.get('path')
    success, message = return_url_delete(path)
    print(success, message)
    return render_template('search/user.html', welcome = message)


def return_url_delete(path):
    message =""
    pod = None
    try:
        u = db.session.query(Urls).filter_by(url=path).first()
        pod_address = u.pod
        pod = db.session.query(Pods).filter_by(url=pod_address).first()
    except AttributeError as err:
        message = "URL not found in the database"
        return False, message
    access_token = request.headers.get('Token') #Get token from request header
    print(">> return_url_delete: access_token: OMD_SESSION_ID", access_token)
    if access_token:
        if access_token == AUTH_TOKEN: #if it equals to system-wide security token, then it is call from OMD backend
            delete_url(u.url)
            message = "Deleted document with url "+u.url+'.'
            return True, message
    try:
        print(session['username'], pod.owner.split(','))
        assert session['username'] in pod.owner.split(',') or path.startswith(join(OMD_PATH,'shared/')) or path.startswith(join(OMD_PATH,'sites/'))
    except AssertionError as err:
        message = "You cannot delete other users' documents."
        return False, message
    delete_url(u.url)
    message = "Deleted document with url "+u.url+'.'
    return True, message


def return_pod_delete(path):
    message =""
    try:
        p = db.session.query(Pods).filter_by(url=path).first()
    except AttributeError as err:
        message = "URL not found in the database"
        return False, message
    access_token = request.headers.get('Token') #Get token from request header
    print(">> return_url_delete: access_token: OMD_SESSION_ID", access_token)
    if access_token:
        if access_token == AUTH_TOKEN: #if it equals to system-wide security token, then it is call from OMD backend
            delete_pod(p.url)
            message = "Deleted pod with path "+p.url+'.'
            return True, message
    try:
        print(session['username'], p.owner.split(','))
        assert session['username'] in p.owner.split(',')
    except AssertionError as err:
        message = "You cannot delete other users' pods."
        return False, message
    delete_pod(p.url)
    message = "Deleted pod with path "+p.url+'.'
    return True, message


