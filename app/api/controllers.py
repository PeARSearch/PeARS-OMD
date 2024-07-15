# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


from os.path import dirname, join, realpath, basename
from flask import Blueprint, jsonify, request, session, flash, render_template
from app.utils_db import delete_url, rename_idx_to_url
from app.api.models import Urls, Pods
from app import db, LOCAL_RUN, OMD_PATH, AUTH_TOKEN
from app.auth.controllers import login_required

# Define the blueprint:
api = Blueprint('api', __name__, url_prefix='/api')

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'pods')


@api.route('/pods/')
@login_required
def return_pods():
    return jsonify(json_list=[p.serialize for p in Pods.query.all()])


@api.route('/urls/delete', methods=["GET"])
@login_required
def api_delete():
    path = request.args.get('path')
    success, message = return_url_delete(path)
    print(success, message)
    return render_template('search/user.html', welcome = message)


def return_url_delete(path):
    message =""
    try:
        u = db.session.query(Urls).filter_by(url=path).first()
        pod_name = u.pod
<<<<<<< HEAD
        pod_username = pod_name.split('/')[0]
=======
        pod_username = pod_name.split('.u.')[1]
>>>>>>> 36563dcaef6e2bb99ef4a72964b4217ec2129aaf
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
        assert pod_username == session['username']
    except AssertionError as err:
        message = "You cannot delete other users' documents."
        return False, message
    delete_url(u.url)
    message = "Deleted document with url "+u.url+'.'
    return True, message


