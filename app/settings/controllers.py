# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


# Import flask dependencies
import logging
import requests
import xmltodict
from glob import glob
from os import rename, getenv
from os.path import dirname, realpath, join, isdir, exists
from flask import Blueprint, request, render_template, redirect, session
from app import db, OMD_PATH, AUTH_TOKEN
from app.auth.controllers import login_required
from app.api.models import Urls, Locations
from app.utils import clean_comma_separated_name, init_crawl, mk_group_name
from app.utils_db import update_locations_in_db, update_groups_in_db
from app.indexer.spider import process_xml, get_doc_info, get_doc_owner, get_doc_shared_with, get_doc_url, get_doc_content_type

# Define the blueprint:
settings = Blueprint('settings', __name__, url_prefix='/settings')

dir_path = dirname(dirname(realpath(__file__)))

# Set the route and accepted methods
@settings.route("/")
@login_required
def index():
    username = session.get('username')
    num_user_files = len(Urls.query.filter(Urls.url.contains(f'/{username}/')).all())
    num_shared_files = len(Urls.query.filter(Urls.url.contains(f'/shared/')).all())
    tree = return_location_graph()
    return render_template("settings/index.html", username=username, num_user_files=num_user_files, num_shared_files=num_shared_files, tree=tree)

@settings.route("/toggle-theme")
def toggle_theme():
    current_theme = session.get("theme")
    print(current_theme, request.args.get('current_page'))
    if current_theme == "dark":
        session["theme"] = "light"
    else:
        session["theme"] = "dark"
    return redirect(request.args.get('current_page'))


def get_user_devices(username):
    xml_url = join(OMD_PATH, username)
    xml = requests.get(xml_url, timeout=30, headers={'Authorization': AUTH_TOKEN}, stream=True).raw
    xml_content = xml.read()
    parse = xmltodict.parse(xml_content)
    folders = []
    try:
        docs = parse['omd_index']['doc']
    except:
        logging.error(">> ERROR: SETTINGS: get docs from xml parse: No documents found in the XML.")
    for d in docs:
        if '@url' in d:
            url = d['@url']
            if url != '?description' and not url.startswith('/shared/'):
                url = join(xml_url, url)
                folders.append(url)
    update_locations_in_db(folders, device=True)
    return folders

def get_locations_and_groups(username=None, start_urls=None):
    username, links = init_crawl(username, start_urls)
    locations = []
    groups = []
    while len(links) > 0:
        start_link = links[0]
        docs, urldir = process_xml(start_link, username)
        for doc in docs:
            url, _ = get_doc_url(doc, urldir)
            _, islink = get_doc_content_type(doc, url)
            owner = get_doc_owner(doc)
            shared_with = get_doc_shared_with(doc)
            group = mk_group_name(owner, shared_with)
            if group not in groups:
                groups.append(group)
            if islink:
                locations.append(url)
                links.append(url)
        del(links[0])
    update_locations_in_db(locations, device=False)
    update_groups_in_db(groups)
    return locations, groups

def get_user_links(username):
    xml_url = join(OMD_PATH, username, 'links')
    xml = requests.get(xml_url, timeout=30, headers={'Authorization': AUTH_TOKEN}, stream=True).raw
    xml_content = xml.read()
    docs = []
    links = []
    try:
        parse = xmltodict.parse(xml_content)
        print("LINKS")
        print(parse)
        docs = parse['omd_index']['doc']
    except:
        logging.error(">> ERROR: SETTINGS: get docs from xml parse: No documents found in the XML.")
    for d in docs:
        print(d)
    return links


def return_tree(paths, min_length):
    tree = []
    for path in paths:
        path_length = len(path.split('/')) - 4 # -4 because of https:// and end slash
        spacing = '|'+(path_length - min_length) * '_ _ _ '
        tree.append(spacing+path)
    return tree


def return_location_graph():
    locations_in_db = db.session.query(Locations).all()
    path_length_to_locations = {}
    for l in locations_in_db:
        path_length = len(l.name.split('/')) - 4 # -4 because of https:// and end slash
        if path_length in path_length_to_locations:
            path_length_to_locations[path_length].append(l.name)
        else:
            path_length_to_locations[path_length] = [l.name]
    min_length = min(list(path_length_to_locations.keys()))
    max_length = max(list(path_length_to_locations.keys()))

    paths = []
    username = session['username']
    for i in range(max_length, min_length,-1):
        locs = path_length_to_locations[i]
        for loc in locs:
            l = loc
            reverse_path = []
            while l != join(OMD_PATH, username)+'/':
                if l not in paths:
                    reverse_path.append(l)
                l = '/'.join(l.split('/')[:-2])+'/'
            paths.extend(reverse_path[::-1])
            if loc not in paths:
                paths.append(loc)

    tree = return_tree(paths, min_length)
    return tree
