# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import re
from os.path import dirname, join, realpath
import numpy as np
from flask import jsonify, session
from flask import Blueprint, request, render_template
from flask_cors import cross_origin

from app import app
from app.utils import get_language, beautify_snippet, beautify_title
from app.search.score_pages import run_search
from app.auth.controllers import login_required
from app import LOCAL_RUN, OMD_PATH, LANGS

LOG = logging.getLogger(__name__)

# Define the blueprint:
search = Blueprint('search', __name__, url_prefix='')

dir_path = dirname(dirname(dirname(realpath(__file__))))
pod_dir = join(dir_path,'app','pods')


@search.route('/', methods=['GET','POST'])
@search.route('/index', methods=['GET','POST'])
def index():
    access_token = request.cookies.get('OMD_SESSION_ID')
    if not access_token:
        return render_template('search/anonymous.html')
    return render_template('search/user.html')


@search.route('/user', methods=['POST','GET'])
@cross_origin()
@login_required
def user():
    query = request.args.get('q')
    gui = request.args.get('gui')
    if not query:
        return render_template("search/user.html"), 200
    results = run_user_search(query)
    if gui:
        displayresults = prepare_gui_results(query, results)
        return render_template('search/results.html', query=query, results=displayresults)
    r = app.make_response(jsonify(results))
    r.mimetype = "application/json"
    return r


@search.route('/anonymous', methods=['POST','GET'])
@cross_origin()
def anonymous():  
    query = request.args.get('q')
    gui = request.args.get('gui')
    if not query:
        return render_template("search/anonymous.html"), 200
    results = run_anonymous_search(query)
    if len(results) == 0:
        results = None
    if gui:
        displayresults = prepare_gui_results(query, results)
        return render_template('search/results.html', query=query, results=displayresults)
    r = app.make_response(jsonify(results))
    r.mimetype = "application/json"
    return r


def run_user_search(query):
    if LOCAL_RUN:
        url = 'http://localhost:9191/api' #Local test
    else:
        url = OMD_PATH
    results = {}
    scores = []
    username = session['username']
    query, lang = get_language(query.lower())
    if lang is None:
        languages = LANGS
    else:
        languages = [lang]
    for lang in languages:
        r, s = run_search(query+' -'+lang, url_filter=[join(url,username), join(url,'shared'), 'http://localhost:9090/'])
        for k,v in r.items():
            if v is not None:
                i = list(r.keys()).index(k)
                #print(i,k,s[i])
                results[k] = v
                scores.append(s[i])
    #print("UNIT TEST LEN RESULTS",len(results), "LEN SCORES", len(scores))
    results = order_results(results, scores)
    return results



def run_anonymous_search(query):
    if LOCAL_RUN:
        url = 'http://localhost:9090/testdocs/shared' #Local test
    else:
        url = join(OMD_PATH, 'shared')
    results = {}
    scores = []
    query, lang = get_language(query.lower())
    if lang is None:
        languages = LANGS
    else:
        languages = [lang]
    for lang in languages:
        r, s = run_search(query+' -'+lang, url_filter=[url])
        results.update(r)
        scores.extend(s)
    results = order_results(results, scores)
    return results


def order_results(results, scores):
    sorted_scores = np.argsort(scores)[::-1]
    sorted_results = {}
    for i in sorted_scores:
        try:
            url = list(results.keys())[i]
            sorted_results[url] = results[url]
        except:
            logging.error(f">> ERROR: SEARCH: CONTROLLERS: sorted scores and results list do not have the same length.")
    return sorted_results


def remove_username_from_url(url):
    # remove whatever comes immediately after "onmydisk.net/", until the next slash 
    return re.sub(r"^(https://onmydisk.net/).+?/(.+)", r"\1\2", url)


def prepare_gui_results(query, results):
    if results is None:
        return None
    displayresults = []
    for _, r in results.items():
        r['title'] = r['title'][:70]
        r['snippet'] = beautify_snippet(r['snippet'], query)
        # remove username from URL so that link to OMD works correctly
        r['url'] = remove_username_from_url(r['url'])
        displayresults.append(list(r.values()))
    return displayresults

