# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
import re
import logging
from math import ceil
from os import remove
from os.path import dirname, join, realpath, isfile
from flask import Blueprint, request, session, render_template, Response

from app import app, tracker
from app import LANGS
from app.api.models import Urls, Pods
from app.indexer import mk_page_vector
from app.indexer.spider import process_xml, get_doc_info
from app.utils import read_docs, read_urls, carbon_print, hash_username
from app.utils_db import create_pod, create_url_in_db, delete_url, delete_old_urls
from app.indexer.posix import posix_doc
from app.auth.controllers import login_required
from app.forms import IndexerForm

app_dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(app_dir_path,'pods')
user_app_dir_path = join(app_dir_path,'userdata')

# Define the blueprint:
indexer = Blueprint('indexer', __name__, url_prefix='/indexer')


def get_num_db_entries():
    username = session['username']
    user_hash = hash_username(username)
    num_db_entries = 0
    pods = Pods.query.filter(Pods.url.startswith(f"{user_hash}/")).all()
    for pod in pods:
        num_db_entries += len(Urls.query.filter_by(pod=pod.url).all())
    return num_db_entries

# Set the route and accepted methods
@indexer.route("/", methods=["GET"])
@login_required
def index():
    """Entry point for indexer.
    Returns the index template with the number of entries
    currently in the database for that user.
    """
    num_db_entries = get_num_db_entries()
    form = IndexerForm(request.form)
    return render_template("indexer/index.html", num_entries=num_db_entries, form=form)


@indexer.route("/from_crawl", methods=["GET","POST"])
@login_required
def from_crawl():
    """Entry point for crawl function.
    Argument: url to a directory to start the crawl from.
    Calls the crawler. GET method is for call from backend,
    POST for call from frontend.
    """

    def process_start_url(url, username):
        logging.debug(f">> INDEXER: CONTROLLER: from_crawl: Now crawling {u}")
        user_url_file = join(user_app_dir_path, username+".toindex")
        #Every contributor gets their own file to avoid race conditions
        with open(user_url_file, 'w', encoding="utf8") as f:
            f.write(url + "\n")
   
    def get_username_from_url(url):
        username = None
        m = re.search(u'onmydisk.net/([^/]*)/', url)
        if m:
            username = m.group(1)
        return username

    def get_device_from_url(url):
        device = None
        m = re.search(u'onmydisk.net/([^/]*)/([^/]*)/', url)
        if m:
            device = m.group(2)
        return device

    if request.method == "POST":
        form = IndexerForm(request.form)
        if form.validate_on_submit():
            u = request.form['url']
            device = get_device_from_url(u)
            username = session['username']
            if not device or not username:
                #The url given by the user is missing a username or device name
                num_db_entries = get_num_db_entries() 
                messages = ["Please ensure the entered URL contains both your username and one of your devices' names."]
                return render_template("indexer/index.html", num_entries=num_db_entries, form=form, messages=messages)
            process_start_url(u, username)
            return render_template('indexer/progress_crawl.html', username=username, device=device)
        num_db_entries = get_num_db_entries() 
        return render_template("indexer/index.html", num_entries=num_db_entries, form=form)
    u = request.args['url']
    username = get_username_from_url(u)
    device = get_device_from_url(u)

    process_start_url(u, username)
    return progress_crawl(username=username, device=device)


def run_indexing(url, pod_path, title, snippet, description, lang, doc):
    print(f"\t>>> INDEXER: CONTROLLER: PROGRESS CRAWL: INDEXING {url}")
    url_in_db = Urls.query.filter_by(url=url).first()
    if url_in_db:
        print(f"\t>>> INDEXER: CONTROLLER: PROGRESS CRAWL: URL PREVIOUSLY KNOWN: {url}")
        delete_url(url)
    #print(url, "SNIPPET", snippet, "DESCRIPTION", description)
    idv, tokenized_text = mk_page_vector.compute_vectors_local_docs(url, pod_path, title, description, doc, lang)
    idx = create_url_in_db(url, title, snippet, description, idv, pod_path)
    posix_doc(tokenized_text, idx, pod_path)


@indexer.route("/progress_crawl")
@login_required
def progress_crawl(username=None, device=None):

    def get_device_from_url(omd_url):
        device = ''
        m = re.search(u'onmydisk.net/([^/]*)/([^/]*)/', omd_url)
        if m:
            device = m.group(2)
        return device

    """ Crawl function, called by from_crawl.
    Reads the start URL given by the user and
    recursively crawls down directories from there.
    """
    if 'username' in session:
        username = session['username']
    # There will only be one path read, although we are using the standard
    # PeARS read_urls function. Hence the [0].
    start_url = read_urls(join(user_app_dir_path, username+".toindex"))[0]
    if start_url[-1] != '/':
        start_url+='/'
    logging.info(f">> INDEXER: Running progress crawl from {start_url}.")

    if device is None:
        device = get_device_from_url(start_url)

    def generate():
        with app.app_context():
            logging.debug("\n\n>>> INDEXER: CONTROLLER: READING DOCS")
            links = [start_url]
            m = 0
            c = 0
            while len(links) > 0:
                print(f"\n\nProcessing {links[0]}.")
                docs, urldir = process_xml(links[0], username)
                urls = [join(urldir,doc['@url'].split('?')[0]) for doc in docs]
                print(">>>>>>>>>>>>>>>>>>>>>>\n",urls)
                delete_old_urls(urls, urldir)
                c = 0
                m += len(docs)
                if tracker is not None:
                    task_name = "run indexing for "+str(len(docs))+" files"
                    tracker.start_task(task_name)
                for doc in docs:
                    doc_info = get_doc_info(doc, urldir)
                    if doc_info is None:
                        continue
                    url, owner, islink, title, description, snippet, body_str, language = doc_info
                    print(f"\n{url}, owner: {owner}, islink: {islink}, title: {title}, description: {description[:20]}, body_str: {body_str[:20]}, language: {language}\n")
                    pod_path = create_pod(url, owner, language, device)
                    run_indexing(url, pod_path, title, snippet, description, language, body_str)
                    if islink:
                        links.append(url)
                    c += 1
                    p = ceil(c / m * 100)
                    if p == 0:
                       p += 1
                    if p == 100:
                       p -= 1

                    yield "data:" + str(p) + "\n\n"
                del(links[0])
                if len(links) == 0:
                    yield "data:100\n\n"
                    
                if tracker is not None:
                    search_emissions = tracker.stop_task()
                    carbon_print(search_emissions, task_name)

    return Response(generate(), mimetype='text/event-stream')
