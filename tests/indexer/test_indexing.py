import os
from os.path import join
from flask import session
from app import app, db, AUTH_TOKEN
from app.api.models import Pods, Sites
from app.cli.controllers import check_db_vs_npz, check_db_vs_pos
from app.indexer.spider import get_xml, read_xml, get_docs_from_xml_parse, process_xml, get_doc_url

from tests import client


##################
# SPIDER: get_xml
##################

def test_spider_get_xml(client):
    xml_url = os.getenv('TEST_XML_URL')

    # Hacking the token to look signed in
    xml = get_xml(xml_url, token=AUTH_TOKEN)
    content = xml.read()
    assert b"<omd_index>" in content

def test_spider_get_xml_incorrect_token(client):
    xml_url = os.getenv('TEST_XML_URL')

    # The token is wrong, we shouldn't get xml
    xml = get_xml(xml_url, token='')
    content = xml.read()
    assert b"<omd_index>" not in content

def test_spider_get_xml_incorrect_url(client):
    xml_url = join(os.getenv('TEST_XML_URL'), 'dud')

    # The token is wrong, we shouldn't get xml
    xml = get_xml(xml_url, token=AUTH_TOKEN)
    content = xml.read()
    assert b"<omd_index>" not in content


##################
# SPIDER: read_xml
##################

def test_spider_read_xml(client):
    xml_url = os.getenv('TEST_XML_URL')

    # Hacking the token to look signed in
    xml = get_xml(xml_url, token=AUTH_TOKEN)
    d = read_xml(xml)
    assert 'omd_index' in d


#################################
# SPIDER: get_docs_from_xml_parse
#################################

def test_spider_get_docs_from_xml_parse(client):
    xml_url = os.getenv('TEST_XML_URL')

    # Hacking the token to look signed in
    xml = get_xml(xml_url, token=AUTH_TOKEN)
    parse = read_xml(xml)
    docs = get_docs_from_xml_parse(parse)

    # If there is only one doc in the docs, the dictionary is
    # returned without the wrapping list.
    assert isinstance(docs, list) or isinstance(docs, dict)

    if isinstance(docs, dict):
        docs = [docs]
    assert len(docs) > 0
    assert '@url' in docs[0]


#####################
# SPIDER: get_doc_url
#####################

def test_spider_get_doc_url(client):
    xml_url = os.getenv('TEST_XML_URL')
    urldir = '/'.join(xml_url.split('/')[:-1])


    # Hacking the token to look signed in
    xml = get_xml(xml_url, token=AUTH_TOKEN)
    parse = read_xml(xml)
    docs = get_docs_from_xml_parse(parse)

    doc = docs[0]
    url, process = get_doc_url(doc, urldir)
    assert url.startswith('http')
    assert isinstance(process, bool)


#####################
# CONSISTENCY CHECKS
#####################

def test_db_npz_consistency(client):
    with app.app_context():
        pods = db.session.query(Pods).all()
        for pod in pods:
            l1, l2 = check_db_vs_npz(pod)
            assert l1 +1 == l2

def test_db_pos_consistency(client):
    with app.app_context():
        pods = db.session.query(Pods).all()
        for pod in pods:
            errors = check_db_vs_pos(pod)
            assert len(errors) == 0
