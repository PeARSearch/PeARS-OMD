# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
import re
from math import ceil
from os import remove
from os.path import dirname, join, realpath, isfile
from flask import Blueprint, request, session, flash, render_template, Response, url_for

from app import app, tracker
from app import LANGS
from app.api.models import Urls, Pods
from app.indexer import mk_page_vector, spider
from app.utils import read_docs, read_urls, get_language, carbon_print
from app.utils_db import (create_pod_in_db, create_pod_npz_pos, create_or_replace_url_in_db, 
        add_to_idx_to_url, add_to_npz_to_idx)
from app.indexer.posix import posix_doc
from app.auth.controllers import login_required

app_dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(app_dir_path,'static','pods')
user_app_dir_path = join(app_dir_path,'static', 'userdata')

# Define the blueprint:
indexer = Blueprint('indexer', __name__, url_prefix='/indexer')


# Set the route and accepted methods
@indexer.route("/", methods=["GET"])
@login_required
def index():
    """Entry point for indexer.
    Returns the index template with the number of entries
    currently in the database for that user.
    """
    username = session['username']
    num_db_entries = 0
    pods = Pods.query.filter(Pods.name.contains('.u.'+username)).all()
    print("PODS",pods)
    for pod in pods:
        print(pod.name)
        num_db_entries += len(Urls.query.filter_by(pod=pod.name).all())
    return render_template("indexer/index.html", num_entries=num_db_entries)


@indexer.route("/from_crawl", methods=["GET","POST"])
@login_required
def from_crawl():
    """Entry point for crawl function.
    Argument: url to a directory to start the crawl from.
    Calls the crawler. GET method is for call from backend,
    POST for call from frontend.
    """

    def process_start_url(url, username):
        create_pod_npz_pos(username)
        for LANG in LANGS:
            create_pod_in_db(username, LANG)
        print(">> INDEXER: CONTROLLER: from_crawl: Now crawling", u)
        user_url_file = join(user_app_dir_path, username+".toindex")
        #Every contributor gets their own file to avoid race conditions
        with open(user_url_file, 'w', encoding="utf8") as f:
            f.write(url + "\n")
   
    def get_username_from_url(url):
        m = re.search(u'onmydisk.net/([^/]*)/', url)
        if m:
            username = m.group(1)
        return username

    if request.method == "POST":
        u = request.form['url']
        username = session['username']
        process_start_url(u, username)
        return render_template('indexer/progress_crawl.html', username=username)
    u = request.args['url']
    username = get_username_from_url(u)
    process_start_url(u, username)
    return progress_crawl(username=username)


@indexer.route("/progress_crawl")
@login_required
def progress_crawl(username=None):
    """ Crawl function, called by from_crawl.
    Reads the start URL given by the user and
    recursively crawls down directories from there.
    """
    print("Running progress crawl")
    if 'username' in session:
        username = session['username']
    # There will only be one path read, although we are using the standard
    # PeARS read_urls function. Hence the [0].
    url = read_urls(join(user_app_dir_path, username+".toindex"))[0]
    spider.write_docs(url, username) #Writing docs to corpus

    def generate():
        with app.app_context():
            print("\n\n>>> INDEXER: CONTROLLER: READING DOCS")
            corpus = join(user_app_dir_path, username+".corpus")
            urls, titles, snippets, descriptions, languages, docs = \
                    read_docs(corpus)
            if len(urls) == 0:
                yield "data:100\n\n"

            c = 0
            if tracker is not None:
                task_name = "run indexing for "+str(len(urls))+" files"
                tracker.start_task(task_name)
            for url, title, snippet, description, lang, doc in \
                    zip(urls, titles, snippets, descriptions, languages, docs):
                #print("\t>>> INDEXER: CONTROLLER: PROGRESS CRAWL: INDEXING", url)
                idx = add_to_idx_to_url(username, url)
                pod_name, vid, tokenized_text = mk_page_vector.compute_vectors_local_docs( \
                    url, title, description, doc, username, lang)
                posix_doc(tokenized_text, idx, pod_name, lang, username)
                add_to_npz_to_idx(pod_name, vid, idx)
                create_or_replace_url_in_db(url, title, snippet, description, username, lang)
                c += 1
                #print('###', str(ceil(c / len(urls) * 100)))
                yield "data:" + str(ceil(c / len(urls) * 100)) + "\n\n"
            if tracker is not None:
                search_emissions = tracker.stop_task()
                carbon_print(search_emissions, task_name)
            if isfile(join(user_app_dir_path, username+".corpus")):
                remove(join(user_app_dir_path, username+".corpus"))

    return Response(generate(), mimetype='text/event-stream')
