# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import dirname, join, realpath
from urllib.parse import quote_plus
import logging
import requests
from flask import jsonify, session
from flask import Blueprint, request, render_template, make_response
from flask_cors import cross_origin

from app import app
from app.search.score_pages import run_search
from app.auth.controllers import login_required
from app import LOCAL_RUN, OMD_PATH

LOG = logging.getLogger(__name__)

# Define the blueprint:
search = Blueprint('search', __name__, url_prefix='')

dir_path = dirname(dirname(dirname(realpath(__file__))))
pod_dir = join(dir_path,'app','static','pods')


@search.route('/user', methods=['POST','GET'])
@cross_origin()
@login_required
def user():
    query = request.args.get('q')
    if not query:
        return render_template("search/user.html"), 200
    results = run_user_search(query)
    r = app.make_response(jsonify(results))
    r.mimetype = "application/json"
    return r

def run_user_search(query):
    if LOCAL_RUN:
        url = 'http://localhost:9191/api' #Local test
    else:
        url = OMD_PATH
    results = []
    query = query.lower()
    username = session['username']
    results = run_search(query, url_filter=[ join(url,username), 'http://localhost:9090/static/'])
    return results


@search.route('/anonymous', methods=['POST','GET'])
@cross_origin()
def anonymous():  
    query = request.args.get('q')
    if not query:
        return render_template("search/anonymous.html"), 200
    results = run_anonymous_search(query)
    r = app.make_response(jsonify(results))
    r.mimetype = "application/json"
    return r


def run_anonymous_search(query):
    if LOCAL_RUN:
        url = 'http://localhost:9090/static/testdocs/shared' #Local test
    else:
        url = join(OMD_PATH, 'shared')
    results = []
    query = query.lower()
    results = run_search(query, url_filter=[url])
    return results


@search.route('/', methods=['GET','POST'])
@search.route('/index', methods=['GET','POST'])
def index():
    access_token = request.cookies.get('OMD_SESSION_ID')
    if not access_token:
        return render_template('search/anonymous.html')
    return render_template('search/user.html')
