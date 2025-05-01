import os
from app import db, AUTH_TOKEN
from app.api.models import Sites
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

# check that we can access the page listing all subscriptable sites
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


# check that we can subscribe to an existing site
# -> SIDE EFFECT: will subscribe to the 'onmydisk' site
def test_subscribe_to_site(client, utils):
    omd_session_token = utils.get_omd_session_id()
    client.set_cookie("OMD_SESSION_ID", omd_session_token)
    with client: # needed for accessing session
        page = client.get("/subscriptions/subscribe_to_site?sitename=onmydisk", headers={"Token":AUTH_TOKEN}, follow_redirects=True)
        flash = flask_session["_flashes"].pop()
    assert flash == ('message', 'Subscribed to site onmydisk')
    html = page.data.decode()
    assert "<b>All OMD sites:</b>" in html # check that we got back to the /allsites page
    assert page.status_code == 200


# check that we get an error when trying to subscribe to a non-existent site
def test_subscribe_to_nonexistent_site(client, utils):
    omd_session_token = utils.get_omd_session_id()
    client.set_cookie("OMD_SESSION_ID", omd_session_token)
    fakename = "daskjdkuj2uyhe9i3dkjhfasd"
    with client: # needed for accessing session
        page = client.get(f"/subscriptions/subscribe_to_site?sitename={fakename}", headers={"Token":AUTH_TOKEN}, follow_redirects=True)
        flash = flask_session["_flashes"].pop()
    assert flash == ('message', f'Error: site {fakename} does not exist')
    html = page.data.decode()
    assert "<b>All OMD sites:</b>" in html # check that we got back to the /allsites page
    assert page.status_code == 200


# check that we can unsubscribe from a site that we're subscribed to
# SIDE EFFECT: unsubscribes us from 'onmydisk'
def test_unsubscribe_from_site(client, utils):
    omd_session_token = utils.get_omd_session_id()
    client.set_cookie("OMD_SESSION_ID", omd_session_token)
    with client: # needed for accessing session
        page = client.get("/subscriptions/unsubscribe_from_site?sitename=onmydisk", headers={"Token":AUTH_TOKEN}, follow_redirects=True)
        flash = flask_session["_flashes"].pop()
    assert flash == ('message', 'Unsubscribed from site onmydisk')
    html = page.data.decode()
    assert "<b>All OMD sites:</b>" in html # check that we got back to the /allsites page
    assert page.status_code == 200


# check that we get an error trying to unsubscribe from a site that doesn't exist
def test_unsubscribe_from_non_subscribed_site(client, utils):
    omd_session_token = utils.get_omd_session_id()
    client.set_cookie("OMD_SESSION_ID", omd_session_token)
    with client: # needed for accessing session
        page = client.get("/subscriptions/unsubscribe_from_site?sitename=cleanblog", headers={"Token":AUTH_TOKEN}, follow_redirects=True)
        flash = flask_session["_flashes"].pop()
    assert flash == ('message', 'Error: you weren\'t subscribed to cleanblog, cannot unsubscribe')
    html = page.data.decode()
    assert "<b>All OMD sites:</b>" in html # check that we got back to the /allsites page
    assert page.status_code == 200

# check that we get an error trying to unsubscribe from a site that doesn't exist
def test_unsubscribe_from_nonexistent_site(client, utils):
    omd_session_token = utils.get_omd_session_id()
    client.set_cookie("OMD_SESSION_ID", omd_session_token)
    fakename = "daskjdkuj2uyhe9i3dkjhfasd"
    with client: # needed for accessing session
        page = client.get(f"/subscriptions/unsubscribe_from_site?sitename={fakename}", headers={"Token":AUTH_TOKEN}, follow_redirects=True)
        flash = flask_session["_flashes"].pop()
    assert flash == ('message', f'Error: site {fakename} does not exist')
    html = page.data.decode()
    assert "<b>All OMD sites:</b>" in html # check that we got back to the /allsites page
    assert page.status_code == 200


# check that we can use update_subscriptions to unsubscribe from all of our sites
# SIDE EFFECTS: 
#   1) subscribe to onmydisk (to be sure we have at least one subscribed site)
#   2) unsubscribe from everything
def test_update_subscriptions_unsubscribe_all(client, utils):
    omd_session_token = utils.get_omd_session_id()
    client.set_cookie("OMD_SESSION_ID", omd_session_token)
    
    with client:
        # step 1: (re)subscribe to onmydisk
        client.get("/subscriptions/subscribe_to_site?sitename=onmydisk", headers={"Token":AUTH_TOKEN}, follow_redirects=True)
        flash = flask_session["_flashes"].pop()
        assert flash == ('message', 'Subscribed to site onmydisk')
        
        # step 2: send empty site list to update_subscriptions
        page = client.post(
            "/subscriptions/update_site_subscriptions",
            data={"sites": []},
            headers={"Token":AUTH_TOKEN}, 
            follow_redirects=True)
        html = page.data.decode()

        # check that we got rid of all the subscriptions
        sites = db.session.query(Sites).filter_by(subscribed=True).all()
        assert sites == []

        # check that we were redirected to the index page
        assert page.status_code == 200
        assert "<b>Subscriptions: your websites</b>" in html


# check that we can use update_subscriptions to unsubscribe from all *but one* of our sites
# SIDE EFFECTS: 
#   1) subscribe to onmydisk (to be sure we have at least one subscribed site)
#   2) unsubscribe from everything except onmydisk
def test_update_subscriptions_unsubscribe_all_except_one(client, utils):
    omd_session_token = utils.get_omd_session_id()
    client.set_cookie("OMD_SESSION_ID", omd_session_token)
    
    with client:
        # step 1: (re)subscribe to onmydisk
        client.get("/subscriptions/subscribe_to_site?sitename=onmydisk", headers={"Token":AUTH_TOKEN}, follow_redirects=True)
        flash = flask_session["_flashes"].pop()
        assert flash == ('message', 'Subscribed to site onmydisk')
        
        # step 2: send OMD site to update_subscriptions
        page = client.post(
            "/subscriptions/update_site_subscriptions",
            data={"sites": ["New On My Disk website"]},
            headers={"Token":AUTH_TOKEN}, 
            follow_redirects=True)
        html = page.data.decode()

        # check that we got rid of all the subscriptions
        sites = db.session.query(Sites).filter_by(subscribed=True).all()
        assert len(sites) == 1

        # check that we were redirected to the index page
        assert page.status_code == 200
        assert "<b>Subscriptions: your websites</b>" in html


# check that we can use update_subscriptions to unsubscribe from only one of two sites with the same name
# SIDE EFFECTS: 
#   1) unsubscribe from everything
#   2) subscribe to sites terrible_recipes_1 and terrible_recipes_2 
#       (both with title "Terrible Recipes", make sure these exist before running the test)
#   3) simulate what happens when you check only one of the boxes of sites to stay subscribed to
#       (expectation: only one of the subscriptions is kept | currently this doesn't work!)
def test_update_subscriptions_unsubscribe_equal_title(client, utils):
    omd_session_token = utils.get_omd_session_id()
    client.set_cookie("OMD_SESSION_ID", omd_session_token)
    
    with client:
        # step 1: send empty site list to update_subscriptions
        page = client.post(
            "/subscriptions/update_site_subscriptions",
            data={"sites": []},
            headers={"Token":AUTH_TOKEN}, 
            follow_redirects=True)
        html = page.data.decode()

        # step 2: subscribe to terrible_recipes_1 and terrible_recipes_2
        client.get("/subscriptions/subscribe_to_site?sitename=terrible_recipes_1", headers={"Token":AUTH_TOKEN}, follow_redirects=True)
        client.get("/subscriptions/subscribe_to_site?sitename=terrible_recipes_2", headers={"Token":AUTH_TOKEN}, follow_redirects=True)        
        
        # step 3: send 'terrible recipes' site to update_subscriptions
        page = client.post(
            "/subscriptions/update_site_subscriptions",
            data={"sites": ["terrible recipes"]},
            headers={"Token":AUTH_TOKEN}, 
            follow_redirects=True)
        html = page.data.decode()

        # check that we got rid of all the subscriptions
        sites = db.session.query(Sites).filter_by(subscribed=True).all()
        assert len(sites) == 1

        # check that we were redirected to the index page
        assert page.status_code == 200
        assert "<b>Subscriptions: your websites</b>" in html
