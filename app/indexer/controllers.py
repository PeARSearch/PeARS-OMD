# SPDX-FileCopyrightText: 2025 PeARS Project, <pears@possible-worlds.eu> 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
import logging
from math import ceil
from os.path import dirname, join, realpath
from flask import Blueprint, request, session, render_template, Response, redirect, url_for, flash

from app import app, db, tracker
from app import OMD_PATH
from app.api.models import Urls, Locations, Groups, Sites
from app.indexer import mk_page_vector
from app.indexer.spider import process_xml, process_html_links, get_doc_info
from app.utils import carbon_print, get_device_from_url, get_username_from_url, init_crawl
from app.utils_db import create_pod, create_url_in_db, delete_url, delete_old_urls, delete_unsubscribed, delete_old_pods, subscribe_location, check_consistency
from app.indexer.posix import posix_doc
from app.auth.controllers import login_required
from app.forms import IndexerForm, FoldersForm, GroupForm, ChoiceObj
from app.settings.controllers import get_user_devices, get_locations_and_groups
from app.indexer.htmlparser import extract_html

app_dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(app_dir_path,'pods')
user_app_dir_path = join(app_dir_path,'userdata')

# Define the blueprint:
indexer = Blueprint('indexer', __name__, url_prefix='/indexer')


def get_num_db_entries():
    num_db_entries = len(Urls.query.all())
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
    crawl_form = IndexerForm(request.form)

    devices_in_db = db.session.query(Locations).filter_by(device=True).all()
    all_devices = [l.name for l in devices_in_db]
    devices_selected = [l.name for l in devices_in_db if l.subscribed]
    print("DEVICES SELECTED", devices_selected)
    devices = ChoiceObj('folders', devices_selected)
    devices_form = FoldersForm(obj=devices)
    devices_form.folders.choices =  [(c, c) for c in all_devices]

    groups_in_db = db.session.query(Groups).all()
    all_groups = [g.name for g in groups_in_db]
    groups_selected = [g.name for g in groups_in_db if g.subscribed]
    groups = ChoiceObj('groups', groups_selected)
    group_form = GroupForm(obj=groups)
    group_form.groups.choices =  [(c, c) for c in all_groups]

    return render_template("indexer/index.html", num_entries=num_db_entries, form1=crawl_form, form2=devices_form, form3=group_form)

@indexer.route("/pull/", methods=["POST"])
@login_required
def pull_from_gateway():
    username = session['username']
    start_urls = get_user_devices(username)
    get_locations_and_groups(username=username, start_urls=start_urls)
    return redirect(url_for('indexer.index'))


@indexer.route("/update_all/", methods=["GET","POST"])
@login_required
def update_all():
    username = session['username']
    locations = db.session.query(Locations).filter_by(subscribed=True).all()
    sites = db.session.query(Sites).filter_by(subscribed=True).all()
    start_urls = [l.name for l in locations]
    start_urls.extend([s.url for s in sites])
    session['start_urls'] = start_urls
    print("UPDATE", start_urls)
    return render_template('indexer/progress_crawl.html', username=username)


@indexer.route("/update_folder_subscriptions/", methods=["POST"])
@login_required
def update_folder_subscriptions():
    if request.method == "POST":
        subscriptions = request.form.getlist('folders')
        print("SUBSCRIBING:", subscriptions)
        locations = db.session.query(Locations).all()
        for l in locations:
            l.subscribed = False
            for sub in subscriptions:
                if l.name.startswith(sub):
                    l.subscribed = True
            db.session.add(l)
            db.session.commit()
    #return redirect(url_for('indexer.index'))
    return redirect(url_for('indexer.update_all'))


@indexer.route("/update_group_subscriptions/", methods=["POST"])
@login_required
def update_group_subscriptions():
    if request.method == "POST":
        subscriptions = request.form.getlist('groups')
        print("SUBSCRIBING:", subscriptions)
        groups = db.session.query(Groups).all()
        for g in groups:
            if g.name in subscriptions:
                g.subscribed = True
            else:
                g.subscribed = False
            db.session.add(g)
            db.session.commit()
    #return redirect(url_for('indexer.index'))
    return redirect(url_for('indexer.update_all'))


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
        session["toindex"] = [username, url]
        subscribe_location(url)
   
    if request.method == "POST":
        form = IndexerForm(request.form)
        if form.validate_on_submit():
            u = request.form['url']
            device = get_device_from_url(u)
            username = get_username_from_url(u)
            is_site = True if u.startswith(join(OMD_PATH, 'sites')) else False
            if not is_site and (not device or not username):
                #The url given by the user is missing a username or device name
                num_db_entries = get_num_db_entries() 
                messages = ["Please ensure the entered URL contains both your username and one of your devices' names."]
                return render_template("indexer/index.html", num_entries=num_db_entries, form=form, messages=messages)
            process_start_url(u, username)
            return render_template('indexer/progress_crawl.html', username=username)
        num_db_entries = get_num_db_entries() 
        return render_template("indexer/index.html", num_entries=num_db_entries, form=form)
    u = request.args['url']
    username = get_username_from_url(u)
    process_start_url(u, username)
    return progress_crawl(username=username)



def run_indexing(url, pod_path, title, snippet, description, lang, doc):
    print(f"\t>>> INDEXER: CONTROLLER: RUN_INDEXING: INDEXING {url}")
    url_in_db = Urls.query.filter_by(url=url).first()
    if url_in_db:
        print(f"\t>>> INDEXER: CONTROLLER: RUN_INDEXING: URL PREVIOUSLY KNOWN: {url}")
        delete_url(url)
    
    success, msg = check_consistency(pod_path)
    if not success:
        print(f"\t>>> INDEXER:CONTROLLER: RUN_INDEXING: INDEXING CANCELLED: {msg}")
        return success, msg
    
    idv, tokenized_text = mk_page_vector.compute_vectors_local_docs(url, pod_path, title, description, doc, lang)
    idx = create_url_in_db(url, title, snippet, description, idv, pod_path)
    posix_doc(tokenized_text, idx, pod_path)
    return success, msg


@indexer.route("/progress_crawl")
@login_required
def progress_crawl(username=None, start_urls=None):

    """ Crawl function, called by from_crawl.
    Reads the start URL given by the user and
    recursively crawls down directories from there.
    """

    username, links = init_crawl(username, start_urls)
    #print("USERNAME", username, "LINKS",links)
    init_links = links.copy()
    for link in links:
        subscribe_location(link)

    def generate(links):
        with app.app_context():
            logging.debug("\n\n>>> INDEXER: CONTROLLER: READING DOCS")
            m = 0
            c = 0
            recorded_urls = []
            if not links:
                yield "data:100|Finished!\n\n"
            while links and len(links) > 0:
                start_link = links[0]
                print(f"\n\nProcessing {start_link}.")
                device = get_device_from_url(start_link)
                docs, urldir = process_xml(start_link)
                urls = [join(urldir,doc['@url'].split('?')[0]) for doc in docs]
                urls = [join(OMD_PATH, url[1:]) if url.startswith('/shared') or url.startswith('/sites') else url for url in urls]
                recorded_urls.extend(urls)
                #print(">>>>>>>>>>>>>>>>>>>>>>\n",urls)
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
                    #print(f"\n{url}, owner: {owner}, islink: {islink}, title: {title}, description: {description[:20]}, body_str: {body_str[:20]}, language: {language}\n")
                    pod_path = create_pod(url, owner, language, device)
                    success, msg = run_indexing(url, pod_path, title, snippet, description, language, body_str)
                    if not success:
                        continue
                    if islink:
                        print("Appending link to list:",url)
                        links.append(url)
                        subscribe_location(url)
                    html_links = process_html_links(url+'?direct')
                    #print(url,html_links)
                    for link in html_links:
                        title, body_str, snippet, _ = extract_html(link)
                        description = ""
                        success, msg = run_indexing(link, pod_path, title, snippet, description, language, body_str)

                    c += 1
                    p = ceil(c / m * 100)
                    if p == 0:
                       p += 1
                    if p == 100:
                       p -= 1

                    yield "data:" + str(p) + "|" + start_link + "\n\n"
                del(links[0])
            if len(links) == 0:
                yield "data:90|Cleaning up...\n\n"
                #print("START URLS", init_links)
                #delete_old_urls(init_links, recorded_urls)
                delete_old_pods()
                delete_unsubscribed()
                yield "data:100|Finished!\n\n"
                
            if tracker is not None:
                search_emissions = tracker.stop_task()
                carbon_print(search_emissions, task_name)

    return Response(generate(links), mimetype='text/event-stream')
