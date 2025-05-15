import os
from os.path import join
import numpy as np
from flask import session
from app import app, db, AUTH_TOKEN, VEC_SIZE
from app.utils_db import create_pod, create_url_in_db, delete_url, add_to_npz, rm_from_npz
from app.api.models import Urls, Pods, Sites
from app.cli.consistency import check_db_vs_npz, check_db_vs_pos
from app.indexer.controllers import run_indexing
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
            errors1, errors2 = check_db_vs_pos(pod)
            assert len(errors1) == 0
            assert len(errors2) == 0


def test_run_indexing(client):
    title = 'Testing run_indexing'
    snippet = 'This is a test of the run_indexing function.'
    description = ''
    lang = 'en'
    doc = title + ' ' + snippet

    with app.app_context():
        random_pod_url = db.session.query(Pods).first().url
        url = join(random_pod_url, 'test.txt')
        success, msg = run_indexing(url, random_pod_url, title, snippet, description, lang, doc)
        assert success is True
        assert isinstance(msg, str)
        delete_url(url)


def test_run_indexing_db_inconsistent(client):

    # Mock document
    title = 'Testing run_indexing'
    snippet = 'This is a test of the run_indexing function.'
    description = ''
    lang = 'en'
    doc = title + ' ' + snippet

    # Mock url and idv to add spurious extra url to pod
    fake_idv = 999999

    with app.app_context():
        random_pod_url = db.session.query(Pods).first().url
        spurious_url = join(random_pod_url, 'spurious.txt')
        url = join(random_pod_url, 'test.txt')
        create_url_in_db(spurious_url, title, snippet, description, fake_idv, random_pod_url)
        success, msg = run_indexing(url, random_pod_url, title, snippet, description, lang, doc)
        assert success is False
        assert "does not match" in msg
        u = db.session.query(Urls).filter_by(url=spurious_url).first()
        db.session.delete(u)
        db.session.commit()


def test_run_indexing_npz_inconsistent_with_db(client):

    # Mock document
    title = 'Testing run_indexing'
    snippet = 'This is a test of the run_indexing function.'
    description = ''
    lang = 'en'
    doc = title + ' ' + snippet

    # Spurious vector to add to .npz
    spurious_vector = np.ones((1, VEC_SIZE))

    with app.app_context():
        random_pod_url = db.session.query(Pods).first().url
        url = join(random_pod_url, 'test.txt')
        vid = add_to_npz(spurious_vector, random_pod_url)
        success, msg = run_indexing(url, random_pod_url, title, snippet, description, lang, doc)
        assert success is False
        assert "does not match" in msg
        rm_from_npz(vid - 1, random_pod_url)


