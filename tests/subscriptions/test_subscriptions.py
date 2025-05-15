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


def test_allsites_gateway_down_message(client, utils):
    # make sure everything is identical to a real request (except the gateway URL) 
    omd_session_token = utils.get_omd_session_id()
    client.set_cookie("OMD_SESSION_ID", omd_session_token)
        
    # set the gateway URL to something fake
    import app.subscriptions.controllers as subscription_controllers
    real_omd_path = subscription_controllers.OMD_PATH
    subscription_controllers.OMD_PATH = "https://fakesite.pearsproject.org/"

    # do the request
    page = client.get("/subscriptions/allsites", headers={"Token":AUTH_TOKEN})

    # set the gateway URL back to the real one
    subscription_controllers.OMD_PATH = real_omd_path

    html = page.data.decode()

    assert "<b>A request exception occurred:" in html


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


# check that we get an error when trying to subscribe to an already subscribed site
# -> SIDE EFFECT: assumes that test_subscribe_to_site passed and we are subscribed to onmydisk
def test_subscribe_to_already_subscribed_site(client, utils):
    omd_session_token = utils.get_omd_session_id()
    client.set_cookie("OMD_SESSION_ID", omd_session_token)
    with client: # needed for accessing session
        page = client.get(f"/subscriptions/subscribe_to_site?sitename=onmydisk", headers={"Token":AUTH_TOKEN}, follow_redirects=True)
        flash = flask_session["_flashes"].pop()
    assert flash == ('message', f'Error: you were already subscribed to site onmydisk')
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
# SIDE EFFECT: unsubscribes us from 'onmydisk', assumes that test_subscribe_to_site was succesful
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
#   3) unsubscribe from onmydisk (if all tests succeed, this neutralizes the side effects)
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
            data={"sites": ["onmydisk"]},
            headers={"Token":AUTH_TOKEN}, 
            follow_redirects=True)
        html = page.data.decode()

        # check that we got rid of all the other subscriptions
        sites = db.session.query(Sites).filter_by(subscribed=True).all()
        assert len(sites) == 1

        # check that we were redirected to the index page
        assert page.status_code == 200
        assert "<b>Subscriptions: your websites</b>" in html

        # finally, unsubscribe from onmydisk
        client.get("/subscriptions/unsubscribe_from_site?sitename=onmydisk", headers={"Token":AUTH_TOKEN}, follow_redirects=True)
        flash = flask_session["_flashes"].pop()
        assert flash == ('message', 'Unsubscribed from site onmydisk')


# check that we can use update_subscriptions to unsubscribe from only one of two sites with the same name
# SIDE EFFECTS: 
#   1) unsubscribe from everything
#   2) subscribe to sites vegan-recipes-1 & vegan-recipes-2
#       (both with title "Vegan Recipes", make sure these exist before running the test)
#       (when publishing these tests, these are hosted on @gossminn's VPS, 
#       if these tests fail, first check if the sites are still online.)
#   3) simulate what happens when you check only one of the boxes of sites to stay subscribed to
#       (expectation: only one of the subscriptions is kept.)
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

        # step 2: subscribe to vegan-recipes-1 & vegan-recipes-2 
        # !! 
        client.get("/subscriptions/subscribe_to_site?sitename=vegan-recipes-1", headers={"Token":AUTH_TOKEN}, follow_redirects=True)
        client.get("/subscriptions/subscribe_to_site?sitename=vegan-recipes-2", headers={"Token":AUTH_TOKEN}, follow_redirects=True)        
        
        # step 3: delete just one but not the other
        page = client.post(
            "/subscriptions/update_site_subscriptions",
            data={"sites": ["vegan-recipes-1"]},
            headers={"Token":AUTH_TOKEN}, 
            follow_redirects=True)
        html = page.data.decode()

        # check that we got rid of all but one of the subscriptions
        # (make sure that the names don't interfere)
        sites = db.session.query(Sites).filter_by(subscribed=True).all()
        assert len(sites) == 1

        # check that we were redirected to the index page
        assert page.status_code == 200
        assert "<b>Subscriptions: your websites</b>" in html
