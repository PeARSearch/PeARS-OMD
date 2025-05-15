import os
from tests import client
from flask import session
from app import AUTH_TOKEN


def test_anonymous_landing(client):
    landing = client.get("/")
    html = landing.data.decode()
    assert "id='searchform'" in html
    assert landing.status_code == 200

def test_anonymous_search(client):
    data = {"query": "pears"}
    response = client.post("/anonymous", data=data)
    html = response.data.decode()
    assert "No results" in html or "Search results" in html
    assert response.status_code == 200

def test_anonymous_to_user_search(client):
    data = {"query": "pears"}
    response = client.post("/user", data=data)
    html = response.data.decode()
    assert response.status_code == 401

def test_user_search(client):
    username = os.getenv('TEST_USERNAME')
    with client.session_transaction() as session:
        session['username'] = username
    data = {"query": "pears"}

    # Hacking the token to look signed in
    response = client.post("/user", data=data, headers={"Token":AUTH_TOKEN})
    html = response.data.decode()
    assert "Search results" in html
    assert response.status_code == 200
