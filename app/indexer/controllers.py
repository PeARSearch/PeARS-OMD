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
from app.utils_db import (create_pod_in_db, create_pod_npz_pos, create_or_replace_url_in_db,
        add_to_idx_to_url, add_to_npz_to_idx, rm_doc_from_pos, rm_from_npz_to_idx, rm_from_npz)
from app.indexer.posix import posix_doc
from app.auth.controllers import login_required

app_dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(app_dir_path,'pods')
user_app_dir_path = join(app_dir_path,'userdata')

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
<<<<<<< HEAD
    pods = Pods.query.filter(Pods.name.startswith(f"{username}/")).all()
=======
    pods = Pods.query.filter(Pods.name.contains('.u.'+username)).all()
>>>>>>> 36563dcaef6e2bb99ef4a72964b4217ec2129aaf
    for pod in pods:
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
<<<<<<< HEAD
        create_pod_npz_pos(username, device)

        for LANG in LANGS:
            create_pod_in_db(username, LANG, device)
=======
        create_pod_npz_pos(username)
        for LANG in LANGS:
            create_pod_in_db(username, LANG)
>>>>>>> 36563dcaef6e2bb99ef4a72964b4217ec2129aaf
        logging.debug(f">> INDEXER: CONTROLLER: from_crawl: Now crawling {u}")
        user_url_file = join(user_app_dir_path, username+".toindex")
        #Every contributor gets their own file to avoid race conditions
        with open(user_url_file, 'w', encoding="utf8") as f:
            f.write(url + "\n")
   
    def get_username_from_url(url):
        m = re.search(u'onmydisk.net/([^/]*)/', url)
        if m:
            username = m.group(1)
        return username
<<<<<<< HEAD

    def get_device_from_url(url):
        m = re.search(u'onmydisk.net/([^/]*)/([^/]*)/', url)
        if m:
            device = m.group(2)
        return device

    if request.method == "POST":
        u = request.form['url']
        device = get_device_from_url(u)
        username = session['username']
        process_start_url(u, username)
        return render_template('indexer/progress_crawl.html', username=username, device=device) 
    u = request.args['url']
    username = get_username_from_url(u)
    device = get_device_from_url(u)

    process_start_url(u, username, device)
    return progress_crawl(username=username, device=device)


def run_indexing(username, url, title, snippet, description, lang, doc, device):
    logging.debug("\t>>> INDEXER: CONTROLLER: PROGRESS CRAWL: INDEXING "+url)
    new, idx = add_to_idx_to_url(username, url)
    pod_name, _, tokenized_text = mk_page_vector.compute_vectors_local_docs( \
        url, title, description, doc, username, lang, device)
=======

    if request.method == "POST":
        u = request.form['url']
        username = session['username']
        process_start_url(u, username)
        return render_template('indexer/progress_crawl.html', username=username)
    u = request.args['url']
    username = get_username_from_url(u)
    process_start_url(u, username)
    return progress_crawl(username=username)


def run_indexing(username, url, title, snippet, description, lang, doc):
    logging.debug("\t>>> INDEXER: CONTROLLER: PROGRESS CRAWL: INDEXING "+url)
    new, idx = add_to_idx_to_url(username, url)
    pod_name, _, tokenized_text = mk_page_vector.compute_vectors_local_docs( \
        url, title, description, doc, username, lang)
>>>>>>> 36563dcaef6e2bb99ef4a72964b4217ec2129aaf
    if not new:
        logging.info("\t>>> INDEXER: CONTROLLER: PROGRESS CRAWL: URL PREVIOUSLY KNOWN: "+url)
        rm_doc_from_pos(idx, pod_name) #in case old version is there
        vid = rm_from_npz_to_idx(pod_name, idx)
        if vid != -1:
            rm_from_npz(vid, pod_name)
    posix_doc(tokenized_text, idx, pod_name, lang, username)
    add_to_npz_to_idx(pod_name, idx)
<<<<<<< HEAD
    create_or_replace_url_in_db(url, title, snippet, description, username, lang, device)
=======
    create_or_replace_url_in_db(url, title, snippet, description, username, lang)
>>>>>>> 36563dcaef6e2bb99ef4a72964b4217ec2129aaf


@indexer.route("/progress_crawl")
@login_required
<<<<<<< HEAD
def progress_crawl(username=None, device=None):

    def get_device_from_url(omd_url):
        m = re.search(u'onmydisk.net/([^/]*)/([^/]*)/', omd_url)
        if m:
            device = m.group(2)
        return device

=======
def progress_crawl(username=None):
>>>>>>> 36563dcaef6e2bb99ef4a72964b4217ec2129aaf
    """ Crawl function, called by from_crawl.
    Reads the start URL given by the user and
    recursively crawls down directories from there.
    """
    if 'username' in session:
        username = session['username']
<<<<<<< HEAD

=======
>>>>>>> 36563dcaef6e2bb99ef4a72964b4217ec2129aaf
    # There will only be one path read, although we are using the standard
    # PeARS read_urls function. Hence the [0].
    start_url = read_urls(join(user_app_dir_path, username+".toindex"))[0]
    logging.info(f">> INDEXER: Running progress crawl from {start_url}.")
<<<<<<< HEAD

    if device is None:
        device = get_device_from_url(start_url)
=======
>>>>>>> 36563dcaef6e2bb99ef4a72964b4217ec2129aaf

    def generate():
        with app.app_context():
            logging.debug("\n\n>>> INDEXER: CONTROLLER: READING DOCS")
            links = [start_url]
            while len(links) > 0:
                docs, urldir = spider.process_xml(links[0], username)

                c = 0
                if tracker is not None:
                    task_name = "run indexing for "+str(len(docs))+" files"
                    tracker.start_task(task_name)
                for doc in docs:
                    url, process = spider.get_doc_url(doc, urldir)
                    if not process:
                        continue
                    convertible = spider.assess_convertibility(doc)
                    content_type, islink = spider.get_doc_content_type(doc, url)
                    title = spider.get_doc_title(doc, url)
                    description = spider.get_doc_description(doc, title)
                    body_title, body_str, language = spider.get_doc_content(url, convertible, content_type)
                    if title is None:
                        title = body_title
                    logging.debug(f"\n{url}, convertible: {convertible}, content_type: {content_type}, islink: {islink}, title: {title}, description: {description}, body_str: {body_str}, language: {language}\n")
                    snippet = ' '.join(body_str.split()[:50])
<<<<<<< HEAD
                    run_indexing(username, url, title, snippet, description, language, body_str, device)
                    if islink:
                        links.append(url)
                    c += 1
                    try:                        
                        yield "data:" + str(ceil(c / len(docs) * 100)-1) + "\n\n"
                    except Exception as e:
                        print(e)
                        yield None
=======
                    run_indexing(username, url, title, snippet, description, language, body_str)
                    if islink:
                        links.append(url)
                    c += 1
                    yield "data:" + str(ceil(c / len(docs) * 100)-1) + "\n\n"
>>>>>>> 36563dcaef6e2bb99ef4a72964b4217ec2129aaf
                del(links[0])
                if len(links) == 0:
                    yield "data:100\n\n"
                    
                if tracker is not None:
                    search_emissions = tracker.stop_task()
                    carbon_print(search_emissions, task_name)

    return Response(generate(), mimetype='text/event-stream')
