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
    sites_selected_names = [g.name for g in sites_in_db if g.subscribed]
    sites_selected_titles = [f"{g.title} [{g.name}]" for g in sites_in_db if g.subscribed]
    sites = ChoiceObj('sites', sites_selected_names)
    site_form = SiteForm(obj=sites)
    site_form.sites.choices =  [
        (name, title) 
        for name, title in zip(sites_selected_names, sites_selected_titles)
    ]
    nosites = False
    if len(sites_selected_titles) == 0:
        nosites = True
    return render_template("subscriptions/index.html", form=site_form, nosites=nosites)


@subscriptions.route("/allsites", methods=["GET","POST"])
@login_required
def show_all_sites():
    success, msg = pull_sites_from_gateway()
    if not success:
        flash(msg)
    sites_in_db = db.session.query(Sites).all()
    all_sites = []
    for site in sites_in_db:
        all_sites.append({'url': site.url, 'name': site.name, 'title': site.title, 'owner': site.owner, 'description': site.description, 'subscribed': site.subscribed})
    #print(all_sites)
    return render_template("subscriptions/allsites.html", sites=all_sites)


def pull_sites_from_gateway():
    all_sites = []
    url = join(OMD_PATH,'sites')
    access_token = request.cookies.get('OMD_SESSION_ID')
    data = {'action': 'list'}
    try:
        resp = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
    except requests.exceptions.RequestException as e:
        return False, e
    if resp.status_code >= 400:
        return False, f"Response status code {resp.status_code}."
    
    json = resp.json()['list']
    for site in json:
        owner = site['owner']
        link = join(OMD_PATH, site['link'][1:])
        name = site['name']
        title = site['customAttributes']['title']
        description = site['customAttributes']['description']
        all_sites.append({'url': link, 'name': name, 'title': title, 'owner': owner, 'description': description})
    update_sites_in_db(all_sites)
    return True, "Sites pulled from gateway."


@subscriptions.route("/subscribe_to_site", methods=['GET','POST'])
@login_required
def subscribe_to_site():
    site_name=request.args.get('sitename')
    s = db.session.query(Sites).filter_by(name=site_name).first()
    if s and not s.subscribed:
        # subscribe on the gateway
        access_token = request.cookies.get('OMD_SESSION_ID')
        data = {'action': 'subscribe', 'site': site_name}
        try:
            resp = requests.post(OMD_PATH, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
        except requests.exceptions.RequestException as e:
            flash(f"Error: {e}")
            return redirect(url_for('subscriptions.show_all_sites'))
        if resp.status_code >= 400:
            flash(f"Error: Connection to gateway failed.")
            return redirect(url_for('subscriptions.show_all_sites'))

        # subscribe PeARS-internally
        s.subscribed = True
        db.session.add(s)
        db.session.commit()
        flash(f"Subscribed to site {site_name}")
    elif s:  # we are already subscribed
        flash(f"Error: you were already subscribed to site {site_name}")
    else: # site does not exist
        flash(f'Error: site {site_name} does not exist')
    return redirect(url_for('subscriptions.show_all_sites'))


@subscriptions.route("/unsubscribe_from_site", methods=['GET','POST'])
@login_required
def unsubscribe_from_site():
    """ This caters for unsubscribing from the website list page.
    """
    print("\n\n>>>Calling unsubscribe_from_site")
    site_name=request.args.get('sitename')
    s = db.session.query(Sites).filter_by(name=site_name).first()
            
    if s and s.subscribed:
        # OMD unsubscribe action
        access_token = request.cookies.get('OMD_SESSION_ID')
        url = OMD_PATH
        data = {'action': 'unsubscribe', 'site': site_name}
        try:
            resp = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
        except requests.exceptions.RequestException as e:
            flash(f"Error: {e}")
            return redirect(url_for('subscriptions.show_all_sites'))
        if resp.status_code >= 400:
            flash(f"Error: Connection to gateway failed.")
            return redirect(url_for('subscriptions.show_all_sites'))

        # mark as unsubscribed internally and delete from index
        print(">> UNSUBSCRIBE from SITE: site info:", s.name, s.subscribed, s.url)
        s.subscribed = False
        delete_urls_recursively(s.url)
        db.session.add(s)
        db.session.commit()
        flash(f"Unsubscribed from site {site_name}")
    
    # site exists but we weren't subscribed -> do nothing
    elif s:
        flash(f'Error: you weren\'t subscribed to {site_name}, cannot unsubscribe')
    else:
        flash(f'Error: site {site_name} does not exist')

    print(">> NOW REDIRECTING TO SHOWING ALL SITES")
    return redirect(url_for('subscriptions.show_all_sites'))

@subscriptions.route("/update_site_subscriptions/", methods=["POST"])
@login_required
def update_site_subscriptions():
    """ This caters for unsubscribing from the websites index page.
    """
    if request.method == "POST":
        subscriptions = request.form.getlist('sites')
        print(">> UPDATE SITE SUBSCRIPTIONS", subscriptions)
        sites = db.session.query(Sites).all()
        for s in sites:
            if s.name in subscriptions:
                s.subscribed = True
            elif s.subscribed:
                url = OMD_PATH
                access_token = request.cookies.get('OMD_SESSION_ID')
                data = {'action': 'unsubscribe', 'site': s.name}
                try:
                    resp = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
                except requests.exceptions.RequestException as e:
                    flash(f"Error: {e}")
                    return redirect(url_for('subscriptions.index'))
                if resp.status_code >= 400:
                    flash(f"Error: Connection to gateway failed.")
                    return redirect(url_for('subscriptions.index'))

                s.subscribed = False
                delete_urls_recursively(s.url)
                db.session.add(s)
                db.session.commit()
    return redirect(url_for('subscriptions.index'))

def subscribe_to_user(username):
    access_token = request.cookies.get('OMD_SESSION_ID')
    url = OMD_PATH
    data = {'action': 'subscribe', 'user': username}
    try:
        resp = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
    except requests.exceptions.RequestException as e:
        flash(f"Error: {e}")
        return redirect(url_for('subscriptions.index'))
    if resp.status_code >= 400:
        flash(f"Error: Connection to gateway failed.")
        return redirect(url_for('subscriptions.index'))
