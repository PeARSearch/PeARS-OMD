# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
from flask import Blueprint, request, render_template, send_from_directory, make_response
from flask import current_app
from flask_cors import cross_origin

# Import the database object from the main app module
from app import app
from app.api.models import Urls
from app.search import score_pages
from app.auth.controllers import login_required

# Import matrix manipulation modules
import numpy as np
from scipy import sparse

# Import utilities
import re
import requests
import logging
from os.path import dirname, join, realpath, isfile
from flask import jsonify, Response, session
from app.utils import init_podsum
from app import LOCAL_RUN

LOG = logging.getLogger(__name__)

# Define the blueprint:
search = Blueprint('search', __name__, url_prefix='')

dir_path = dirname(dirname(dirname(realpath(__file__))))
pod_dir = join(dir_path,'app','static','pods')


@search.route('/user', methods=['POST','GET'])
@cross_origin()
@login_required
def user(access_token):
    if LOCAL_RUN:
        url = 'http://localhost:9191/api' #Local test
    else:
        url = ' https://demo.onmydisk.net/'

    results = []
    if Urls.query.count() == 0:
        init_podsum()

    query = request.args.get('q')
    if not query:
        LOG.info("No query")
        return render_template("search/user.html"), 200
    else:

        results = []
        query = query.lower()
        pears = ['0.0.0.0']
        username = session['username']
        results, pods = score_pages.run(query, pears, url_filter=[ join(url,username), 'http://localhost:9090/static/']) #TODO: replace filter with correct OMD endpoint
        r = app.make_response(jsonify(results))
        r.mimetype = "application/json"
        return r


@search.route('/anonymous', methods=['POST','GET'])
@cross_origin()
def anonymous():  
    results = []
    if Urls.query.count() == 0:
        init_podsum()

    query = request.args.get('q')
    if not query:
        LOG.info("No query")
        return render_template("search/anonymous.html")
    else:
        results = []
        query = query.lower()
        pears = ['0.0.0.0']
        if LOCAL_RUN:
            url = 'http://localhost:9090/static/testdocs/shared' #Local test
        else:
            url = ' https://demo.onmydisk.net/shared'
        results, pods = score_pages.run(query, pears, url_filter=[url])
        r = app.make_response(jsonify(results))
        r.mimetype = "application/json"
        return r



@search.route('/', methods=['GET','POST'])
@search.route('/index', methods=['GET','POST'])
def index():
    if Urls.query.count() == 0:
        init_podsum()
    print("LOCAL",LOCAL_RUN)
    access_token = request.cookies.get('OMD_SESSION_ID')  
    if not access_token:
        return render_template('search/anonymous.html')
    else:
        if LOCAL_RUN:
            url = 'http://localhost:9191/api' #Local test
        else:
            url = ' https://demo.onmydisk.net/'
        print("CONNECTING TO:",url)
        data = {'action': 'getUserInfo', 'session_id': access_token}
        resp = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
        if resp.status_code == requests.codes.ok:
            username = resp.json()['username']
            # Create a new response object
            resp_frontend = make_response(render_template( 'search/user.html', welcome="Welcome "+username), 200)
            # Transfer the cookies from backend response to frontend response
            for name, value in request.cookies.items():
                print("SETTING COOKIE:",name,value)
                resp_frontend.set_cookie(name, value, samesite='Lax')
            return resp_frontend
        else:
            # Create a new response object
            resp_frontend = make_response(render_template( 'search/anonymous.html'), 401)
            resp_frontend.set_cookie('OMD_SESSION_ID', '', expires=0, samesite='Lax')
            return resp_frontend


