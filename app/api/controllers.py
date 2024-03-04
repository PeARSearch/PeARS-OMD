# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


from os.path import dirname, join, realpath, basename
from flask import Blueprint, jsonify, request, session, flash, render_template
from app.utils_db import delete_url, rename_idx_to_url, move_npz_pos
from app.api.models import Urls, Pods
from app import db, LOCAL_RUN, OMD_PATH
from app.auth.controllers import login_required

# Define the blueprint:
api = Blueprint('api', __name__, url_prefix='/api')

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'static','pods')


@api.route('/pods/')
@login_required
def return_pods():
    return jsonify(json_list=[p.serialize for p in Pods.query.all()])


@api.route('/pods/<pod>/')
@login_required
def return_pod(pod):
    pod = pod.replace('+', ' ')
    p = db.session.query(Pods).filter_by(name=pod).first()
    return jsonify(p.serialize)


@api.route('/urls/')
@login_required
def return_urls():
    return jsonify(json_list=[i.serialize for i in Urls.query.all()])


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
        pod_username = pod_name.split('.u.')[1]
    except AttributeError as err:
        message = "URL not found in the database"
        return False, message
    try:
        assert pod_username == session['username']
    except AssertionError as err:
        message = "You cannot delete other users' documents."
        return False, message
    delete_url(u.url)
    message = "Deleted document with url "+u.url+'.'
    return True, message


@api.route('/urls/move', methods=["GET","POST"])
@login_required
def api_move():
    src = request.args.get('src')
    target = request.args.get('target')
    username = session['username']
    success, message = return_move(src, target, username)
    print(success, message)
    return render_template('search/user.html', welcome = message)


def return_move(src, target, username):
    """ TODO: 
    - case where user is admin
    - moving between pods
    - filename changes
    """
    message = ""
    
    if LOCAL_RUN:
        path_personal = 'http://localhost:9090/static/testdocs/'+username
        path_shared = 'http://localhost:9090/static/testdocs/shared'
    else:
        path_personal = join(OMD_PATH, username)
        path_shared = join(OMD_PATH, 'shared')

    #Check source url is in the database
    u = db.session.query(Urls).filter_by(url=src).first()
    if u is None:
        print(">>ERROR The source url was not found in the database.")
        message = "The source url was not found in the database."
        return False, message

    #Check source url belongs to user
    pod_name = u.pod
    pod_username = pod_name.split('.u.')[1]
    try:
        assert pod_username == username
    except AssertionError as err:
        print(">>ERROR You cannot move other users' documents.")
        message = "You cannot move other users' documents."
        return False, message

    #Check target url belongs to user or is shared
    try:
        assert path_personal in target or path_shared in target
    except AssertionError as err:
        print(">>ERROR You cannot move files to another user's directory.")
        message = "You cannot move other users' documents."
        return False, message
  
    #Check case where target is a directory
    src_name = basename(src)
    if target[-1] == '/':
        target = join(target,src_name)
    target_name = basename(target)

    #The simple case: the file name has not changed and there is
    #no moving between private and shared pods
    if src_name == target_name:
        print("Names are the same.")
        print(src,target,path_personal)
        if (path_personal in src and path_personal in target) or \
            (path_shared in src and path_shared in target):
            print("No moving across pods.")
            rename_idx_to_url(username, src, target)
            u.url = target
            db.session.add(u)
            db.session.commit()
            message = "Moved file "+src+" to "+target+'.'
            return True, message
    message = "This is a complicated case. Ignoring it for now."
    return False, message
