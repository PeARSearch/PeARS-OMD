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
from app.indexer import mk_page_vector, spider
from app.utils import read_docs, read_urls, carbon_print
from app.utils_db import create_pod_in_db, create_pod_npz_pos, create_or_replace_url_in_db, delete_url, uptodate
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
    num_db_entries = 0
    pods = Pods.query.filter(Pods.name.startswith(f"{username}/")).all()
    for pod in pods:
        num_db_entries += len(Urls.query.filter_by(pod=pod.name).all())
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
        create_pod_npz_pos(username, device)

        for LANG in LANGS:
            create_pod_in_db(username, LANG, device)
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


def run_indexing(username, url, title, snippet, description, lang, doc, device):
    logging.debug(f"\t>>> INDEXER: CONTROLLER: PROGRESS CRAWL: INDEXING {url}")
    url_in_db = Urls.query.filter_by(url=url).first()
    if url_in_db:
        logging.info(f"\t>>> INDEXER: CONTROLLER: PROGRESS CRAWL: URL PREVIOUSLY KNOWN: {url}")
        delete_url(url)
    print(url, "SNIPPET", snippet, "DESCRIPTION", description)
    pod_name, idv, tokenized_text = mk_page_vector.compute_vectors_local_docs( \
        url, title, description, doc, username, lang, device)
    idx = create_or_replace_url_in_db(url, title, snippet, description, idv, username, lang, device)
    posix_doc(tokenized_text, idx, pod_name, lang, username)


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
                docs, urldir = spider.process_xml(links[0], username)
                c = 0
                m += len(docs)
                if tracker is not None:
                    task_name = "run indexing for "+str(len(docs))+" files"
                    tracker.start_task(task_name)
                for doc in docs:
                    url, process = spider.get_doc_url(doc, urldir)
                    print(f"\n>> {url}")
                    if not process:
                        continue
                    last_modified = spider.get_last_modified(doc)
                    if last_modified is not None and uptodate(url, last_modified):
                        continue
                    print(f"{url} is not up to date. Reindexing.")
                    convertible = spider.assess_convertibility(doc)
                    content_type, islink = spider.get_doc_content_type(doc, url)
                    title = spider.get_doc_title(doc, url)
                    description = spider.get_doc_description(doc, title)
                    snippet = ""
                    body_title, body_str, language = spider.get_doc_content(url, convertible, content_type)
                    if title is None:
                        title = body_title

                    logging.debug(f"\n{url}, convertible: {convertible}, content_type: {content_type}, islink: {islink}, title: {title}, description: {description}, body_str: {body_str}, language: {language}\n")
                    if body_str.startswith("<omd_index>"):
                        if description != title:
                            body_str = description
                        else:
                            body_str = f"Directory {title}"
                    if body_str == "":
                        description = description or "No description"
                    else:
                        snippet = ' '.join(body_str.split()[:50])
                    #print("DESCRIPTION",description)
                    #print("SNIPPET",snippet)
                    run_indexing(username, url, title, snippet, description, language, body_str, device)
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
