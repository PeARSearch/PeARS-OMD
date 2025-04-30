import os
from app import AUTH_TOKEN
from flask import session as flask_session

from tests import client, utils


##################
# SUBSCRIPTIONS: index_page (not logged in)
##################


def test_anonymous_landing(client, utils):
    page = client.get("/subscriptions/")
    utils.test_authentication_failed(page)


##################
# SUBSCRIPTIONS: index_page (logged in)
##################


def test_user_landing(client):
    username = os.getenv('TEST_USERNAME')
    with client.session_transaction() as session:
        session['username'] = username

    page = client.get("/subscriptions/", headers={"Token":AUTH_TOKEN})
    html = page.data.decode()
    assert "<b>Subscriptions: your websites</b>" in html
    assert page.status_code == 200


##################
# SUBSCRIPTIONS: all sites (logged in)
##################


def test_user_allsites(client, utils):

    omd_session_token = utils.get_omd_session_id()
    client.set_cookie("OMD_SESSION_ID", omd_session_token)
    page = client.get("/subscriptions/allsites", headers={"Token":AUTH_TOKEN})
    html = page.data.decode()
    
    assert "<b>All OMD sites:</b>" in html

    # assume we have at least the OMD official site in the results 
    # (also used in test_subscribe_to_site, change BOTH tests if the site becomes unavailable)
    assert "href=\"https://onmydisk.net/sites/onmydisk\"" in html
    
    assert page.status_code == 200


def test_subscribe_to_site(client, utils):
    omd_session_token = utils.get_omd_session_id()
    client.set_cookie("OMD_SESSION_ID", omd_session_token)
    with client: # needed for accessing session
        page = client.get("/subscriptions/subscribe_to_site?sitename=onmydisk", headers={"Token":AUTH_TOKEN}, follow_redirects=True)
        flash = flask_session["_flashes"].pop()
    assert flash == ('message', 'Subscribed to site onmydisk')
    html = page.data.decode()
    assert "<b>All OMD sites:</b>" in html
    assert page.status_code == 200
