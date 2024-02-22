# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


from os.path import dirname, join, realpath, basename
from flask import Blueprint, jsonify, request
from app.utils_db import delete_url
from app.api.models import Urls, Pods
from app import db
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
def return_delete(idx=None):
    if idx is None:
        path = request.args.get('path')
    else:
        path = None
    #try:
    if not path:
        u = db.session.query(Urls).filter_by(vector=idx).first()
    else:
        u = db.session.query(Urls).filter_by(url=path).first()
    pod = u.pod
    vid = int(u.vector)
    delete_url(vid)
    #except:
    #    return "Deletion failed"
    return "Deleted document with vector id"+str(vid)+'\n'


@api.route('/urls/move', methods=["GET","POST"])
@login_required
def return_rename():
    src = request.args.get('src')
    target = request.args.get('target')
    try:
        u = db.session.query(Urls).filter_by(url=src).first()

        #Rename in DB
        src_name = basename(src)
        print(src_name)
        if target[-1] == '/':
            target = join(target,src_name)
        target_name = basename(target)
        print(target_name)
        u.url = target
        if u.title == src_name:
            u.title = target_name

        db.session.add(u)
        db.session.commit()
    except:
        return "Moving failed"
    return "Moved file "+src+" to "+target+'\n'
