# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only


import logging
import requests
from os.path import dirname, realpath, join, isdir, exists
from flask import Blueprint, request, render_template, redirect, session, url_for, flash
from app import db, OMD_PATH, AUTH_TOKEN
from app.api.models import Sites
from app.auth.controllers import login_required
from app.utils_db import update_sites_in_db

# Define the blueprint:
subscriptions = Blueprint('subscriptions', __name__, url_prefix='/subscriptions')

dir_path = dirname(dirname(realpath(__file__)))

# Set the route and accepted methods
@subscriptions.route("/")
@login_required
def index():
    sites_in_db = db.session.query(Sites).all()
    all_sites = []
    for site in sites_in_db:
        all_sites.append({'url': site.url, 'title': site.title, 'owner': site.owner, 'description': site.description, 'subscribed': site.subscribed})
    print(all_sites)
    return render_template("subscriptions/index.html", sites=all_sites)


@subscriptions.route("/pull/", methods=["POST"])
@login_required
def pull_sites_from_gateway():
    all_sites = []
    url = join(OMD_PATH,'sites')
    data = {'action': 'list'}
    resp = requests.post(url, timeout=30, headers={'Authorization': 'token:'+AUTH_TOKEN}, json=data)
    json = resp.json()['list']
    for site in json:
        owner = site['owner']
        link = join(OMD_PATH, site['link'][1:])
        name = site['name']
        title = site['customAttributes']['title']
        description = site['customAttributes']['description']
        all_sites.append({'url': link, 'name': name, 'title': title, 'owner': owner, 'description': description})
    update_sites_in_db(all_sites)
    return redirect(url_for('subscriptions.index'))


@subscriptions.route("/subscribe_to_site", methods=['GET','POST'])
@login_required
def subscribe_to_site():
    site_name=request.args.get('sitename')
    access_token = request.cookies.get('OMD_SESSION_ID')
    url = OMD_PATH
    data = {'action': 'subscribe', 'site': site_name}
    resp = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
    s = db.session.query(Sites).filter_by(title=site_name).first()
    s.subscribed = True
    db.session.add(s)
    db.session.commit()
    flash(f"Subscribed to site {site_name}")
    return redirect(url_for('subscriptions.index'))

@subscriptions.route("/unsubscribe_from_site", methods=['GET','POST'])
@login_required
def unsubscribe_from_site():
    # TODO
    site_name=request.args.get('sitename')
    access_token = request.cookies.get('OMD_SESSION_ID')
    url = OMD_PATH
    data = {'action': 'unsubscribe', 'site': site_name}
    resp = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
    s = db.session.query(Sites).filter_by(title=site_name).first()
    s.subscribed = False
    db.session.add(s)
    db.session.commit()
    flash(f"Unsubscribed from site {site_name}")
    return redirect(url_for('subscriptions.index'))


def subscribe_to_user(username):
    access_token = request.cookies.get('OMD_SESSION_ID')
    url = OMD_PATH
    data = {'action': 'subscribe', 'user': username}
    resp = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
    print(resp.status_code)
