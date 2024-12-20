# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


import logging
import requests
from os.path import dirname, realpath, join, isdir, exists
from flask import Blueprint, request, render_template, redirect, session, url_for
from app import db, OMD_PATH, AUTH_TOKEN
from app.api.models import Sites
from app.auth.controllers import login_required
from app.utils_db import update_sites_in_db

# Define the blueprint:
websites = Blueprint('websites', __name__, url_prefix='/websites')

dir_path = dirname(dirname(realpath(__file__)))

# Set the route and accepted methods
@websites.route("/")
@login_required
def index():
    sites_in_db = db.session.query(Sites).all()
    all_sites = []
    for site in sites_in_db:
        all_sites.append({'url': site.url, 'title': site.title, 'owner': site.owner, 'description': site.description})
    print(all_sites)
    return render_template("websites/index.html", sites=all_sites)


@websites.route("/pull/", methods=["POST"])
@login_required
def pull_sites_from_gateway():
    all_sites = []
    url = join(OMD_PATH,'sites')
    data = {'action': 'list'}
    resp = requests.post(url, timeout=30, headers={'Authorization': AUTH_TOKEN}, json=data)
    json = resp.json()['list']
    for site in json:
        owner = site['owner']
        link = join(OMD_PATH, site['link'][1:])
        name = site['name']
        description = site['customAttributes']['description']
        all_sites.append({'url': link, 'title': name, 'owner': owner, 'description': description})
    update_sites_in_db(all_sites)
    return redirect(url_for('websites.index'))
