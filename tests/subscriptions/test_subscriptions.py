import os
from app import AUTH_TOKEN

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


def test_user_allsites(client):
    username = os.getenv('TEST_USERNAME')
    with client.session_transaction() as session:
        session['username'] = username

    page = client.get("/subscriptions/allsites/", headers={"Token":AUTH_TOKEN})
    html = page.data.decode()
    
    assert "<b>All OMD sites:</b>" in html

    # assume we have at least the test blog in the results (adjust the test as needed if this changes)
    assert "href=\"https://onmydisk.net/sites/blog\"" in html
    
    assert page.status_code == 200