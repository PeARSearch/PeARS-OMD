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
from app.utils_db import update_sites_in_db, delete_urls_recursively
from app.forms import ChoiceObj, SiteForm
from app.indexer.controllers import run_indexing
from app.indexer.spider import process_html_links
from app.indexer.htmlparser import extract_html

# Define the blueprint:
subscriptions = Blueprint('subscriptions', __name__, url_prefix='/subscriptions')

dir_path = dirname(dirname(realpath(__file__)))

@subscriptions.route("/")
@login_required
def index():
    sites_in_db = db.session.query(Sites).all()
    sites_selected = [g.title for g in sites_in_db if g.subscribed]
    sites = ChoiceObj('sites', sites_selected)
    site_form = SiteForm(obj=sites)
    site_form.sites.choices =  [(c, c) for c in sites_selected]
    nosites = False
    if len(sites_selected) == 0:
        nosites = True
    return render_template("subscriptions/index.html", form=site_form, nosites=nosites)


@subscriptions.route("/allsites", methods=["GET","POST"])
@login_required
def show_all_sites():
    sites_in_db = db.session.query(Sites).all()
    all_sites = []
    for site in sites_in_db:
        all_sites.append({'url': site.url, 'title': site.title, 'owner': site.owner, 'description': site.description, 'subscribed': site.subscribed})
    print(all_sites)
    return render_template("subscriptions/allsites.html", sites=all_sites)


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
    return redirect(url_for('subscriptions.show_all_sites'))


@subscriptions.route("/subscribe_to_site", methods=['GET','POST'])
@login_required
def subscribe_to_site():
    site_name=request.args.get('sitename')
    access_token = request.cookies.get('OMD_SESSION_ID')
    data = {'action': 'subscribe', 'site': site_name}
    resp = requests.post(OMD_PATH, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
    s = db.session.query(Sites).filter_by(title=site_name).first()
    s.subscribed = True
    #html_links = process_html_links(s.url+'?direct')
    #print(s.url,html_links)
    #for link in html_links:
    #    title, body_str, snippet, _ = extract_html(link)
    #    description = ""
    #    pod_path = ""
    #    language = "en"
    #    run_indexing(link, pod_path, title, snippet, description, language, body_str)
    db.session.add(s)
    db.session.commit()
    flash(f"Subscribed to site {site_name}")
    return redirect(url_for('subscriptions.show_all_sites'))


@subscriptions.route("/unsubscribe_from_site", methods=['GET','POST'])
@login_required
def unsubscribe_from_site():
    """ This caters for unsubscribing from the website list page.
    """
    site_name=request.args.get('sitename')
    access_token = request.cookies.get('OMD_SESSION_ID')
    url = OMD_PATH
    data = {'action': 'unsubscribe', 'site': site_name}
    resp = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
    s = db.session.query(Sites).filter_by(title=site_name).first()
    s.subscribed = False
    #delete_urls_recursively(s.url)
    db.session.add(s)
    db.session.commit()
    flash(f"Unsubscribed from site {site_name}")
    return redirect(url_for('subscriptions.index'))

@subscriptions.route("/update_site_subscriptions/", methods=["POST"])
@login_required
def update_site_subscriptions():
    """ This caters for unsubscribing from the websites index page.
    """
    if request.method == "POST":
        subscriptions = request.form.getlist('sites')
        print(subscriptions)
        sites = db.session.query(Sites).all()
        for s in sites:
            if s.name in subscriptions:
                s.subscribed = True
            else:
                s.subscribed = False
            db.session.add(s)
            db.session.commit()
    return redirect(url_for('subscriptions.index'))

def subscribe_to_user(username):
    access_token = request.cookies.get('OMD_SESSION_ID')
    url = OMD_PATH
    data = {'action': 'subscribe', 'user': username}
    resp = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
    print(resp.status_code)
