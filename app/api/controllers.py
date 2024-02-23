# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


from os.path import dirname, join, realpath, basename
from flask import Blueprint, jsonify, request, session, flash
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


@api.route('/urls/delete', methods=["GET","POST"])
@login_required
def return_url_delete(path=None):
    if not path:
        path = request.args.get('path')
    try:
        u = db.session.query(Urls).filter_by(url=path).first()
        pod_name = u.pod
        pod_username = pod_name.split('.u.')[1]
    except AttributeError as err:
        flash("URL not found in the database")
        return False
    try:
        assert pod_username == session['username']
    except AssertionError as err:
        flash("You cannot delete other users' documents.")
        return False
    delete_url(u.url)
    print("Deleted document with url "+u.url)
    return True


@api.route('/urls/move', methods=["GET","POST"])
@login_required
def return_rename():
    """ TODO: fix npz and posix when moving from personal to shared
    """
    src = request.args.get('src')
    target = request.args.get('target')
    username = session['username']

    print("SRC",src)
    print("TARGET",target)
    
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
        flash("The source url was not found in the database.")
        return False

    #Check source url belongs to user
    pod_name = u.pod
    pod_username = pod_name.split('.u.')[1]
    try:
        assert pod_username == username
    except AssertionError as err:
        print(">>ERROR You cannot move other users' documents.")
        flash("You cannot move other users' documents.")
        return False

    #Check target url belongs to user or is shared
    try:
        assert path_personal in target or path_shared in target
    except AssertionError as err:
        print(">>ERROR You cannot move files to another user's directory.")
        flash("You cannot move other users' documents.")
        return False
  
    #Check case where target is a directory
    src_name = basename(src)
    if target[-1] == '/':
        target = join(target,src_name)

    #If url has moved between shared and non shared locations,
    #we must change the npz and pos files
    if (src in path_personal and target in path_shared) or \
            (src in path_shared and target in path_personal):
        move_npz_pos(src, target)
    else:
        rename_idx_to_url(username, src, target)

    #Rename in DB
    target_name = basename(target)
    print(target_name)
    u.url = target
    if u.title == src_name:
        u.title = target_name

    db.session.add(u)
    db.session.commit()
    print("Moved file "+src+" to "+target)
    return True
