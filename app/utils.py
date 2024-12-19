# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import hashlib
from os.path import join, realpath, dirname
import re
from datetime import datetime
from math import sqrt
import requests
import numpy as np
from scipy.spatial import distance
from app import LANGS, CARBON_DIR
from markupsafe import Markup, escape
from flask import session

app_dir_path = dirname(realpath(__file__))
user_app_dir_path = join(app_dir_path,'userdata')


def carbon_print(tracker_results, task_name):
    date = datetime.today().strftime('%Y-%m-%d')
    filename = 'carbon.'+date+'.txt'
    with open(join(CARBON_DIR,filename),'a', encoding="utf-8") as f:
        f.write(task_name+': '+str(tracker_results)+'\n')

def clean_comma_separated_name(name):
    name = ','.join([ind for ind in name.split(',') if not ind.isspace()])
    return name

def mk_group_name(owner, shared_with):
    if len(shared_with) > 0:
        group = [ind.strip() for ind in shared_with.split(',') if not ind.isspace()]
        if owner not in group:
            group.append(owner)
        group = ', '.join(group)
    else:
        group = owner
    return group

def hash_username(username):
    user_hash = hashlib.shake_256(username.encode()).hexdigest(8)
    return user_hash

def read_urls(url_file):
    with open(url_file, 'r', encoding="utf-8") as fd:
        urls = fd.read().splitlines()
    return urls

def get_device_from_url(omd_url):
    device = ''
    m = re.search(u'onmydisk.net/([^/]*)/([^/]*)/', omd_url)
    if m:
        device = m.group(2)
    return device

def get_username_from_url(url):
    username = None
    m = re.search(u'onmydisk.net/([^/]*)/', url)
    if m:
        username = m.group(1)
    return username

def init_crawl(username=None, start_urls=None):
    if not username and 'username' in session:
        username = session['username']
    if 'start_urls' in session:
        print("Start urls in session.")
        start_urls = session['start_urls']
        session.pop('start_urls')
    elif not start_urls and 'toindex' in session:
        print("Reading start urls from toindex field in session.")
        start_url = session['toindex'][1] 
        if start_url[-1] != '/':
            start_url+='/'
        start_urls = [start_url]
        session.pop('toindex')
    print("INIT CRAWL START URLS", start_urls)
    return username, start_urls

def read_docs(doc_file):
    """ Function to read the pre-processed documents, as obtained
    from crawling the OMD xml files.
    Argument: the path to the document file.
    Returns: paths, titles, snippets, descriptions and full bodies
    of documents in the input file.
    """

    # Initializations
    url = ""
    title = ""
    snippet = ""
    description = ""
    language = LANGS[0]

    urls = []
    titles = []
    snippets = []
    docs = []
    descriptions = []
    languages = []

    with open(doc_file, 'r', encoding="utf-8") as df:
        description = ""
        doc = ""
        for l in df:
            l=l.rstrip('\n')
            if l[:4] == "<doc":
                m = re.search('url=\'([^\']*)\'',l)
                url = m.group(1)
                m = re.search('title=\'([^\']*)\'',l)
                title = m.group(1)
                m = re.search('lang=\'([^\']*)\'',l)
                language = m.group(1)
            elif "</doc" not in l:
                if "{{DESCRIPTION}}" in l:
                    description = l.replace("{{DESCRIPTION}} ","")
                    logging.debug(f"DOC WITH DESCRIPTION: {description}")
                elif "{{BODY}}" in l:
                    l = l.replace("{{BODY}} ","")
                    doc+=l+' '
                else:
                    doc+=l+' '
            else:
                if url != "":
                    snippet = doc[:200]
                    urls.append(url)
                    titles.append(title)
                    snippets.append(snippet)
                    descriptions.append(description)
                    languages.append(language)
                    docs.append(description+' '+doc)
                    description = ""
                    url = ""
                    title = ""
                    snippet = ""
                    doc = ""
                    language = LANGS[0]
    return urls, titles, snippets, descriptions, languages, docs


def cosine_similarity(v1, v2):
    if len(v1) != len(v2):
        return 0.0
    num = np.dot(v1, v2)
    den_a = np.dot(v1, v1)
    den_b = np.dot(v2, v2)
    return num / (sqrt(den_a) * sqrt(den_b))


def hamming_similarity(v1, v2):
    return 1 - distance.hamming(v1,v2)


def get_pod_info(url):
    print("Fetching pod", join(url, "api/self/"))
    pod = None
    try:
        r = requests.get(join(url, "api/self/"))
        if r.status_code == 200:
            pod = r.json()
    except Exception:
        print("Problem fetching pod...")
    return pod


def get_language(query):
    lang = None
    m = re.search('(.*) -(..\s*)$',query)
    if m:
        print(m.group(1), m.group(2))
        query = m.group(1)
        lang = m.group(2)
        if lang not in LANGS:
            lang = None
    return query, lang

def beautify_title(title, doctype):
    title = title[:70]
    if doctype == 'stat':
        title = '📈 '+title
    if doctype == 'doc':
        title = '📝 '+title
    if doctype == 'url':
        title = '🌏 '+title
    if doctype == 'ind':
        title = '☺️  '+title
    if doctype == 'map':
        title = '📍 '+title
    return title

def beautify_snippet(snippet, query):
    if snippet == '':
        return snippet
    tmp_snippet = snippet
    for w in query.split():
        tmp_snippet = tmp_snippet.replace(w,'<b>'+w+'</b>')
        tmp_snippet = tmp_snippet.replace(w.title(),'<b>'+w.title()+'</b>')
    #Secure snippet
    els = re.split(r'<b>|</b>', tmp_snippet)
    tmp_snippet = ""
    tag = '<b>'
    for e in els:
        tmp_snippet+=escape(e)+Markup(tag)
        tag = '</b>' if tag == '<b>' else '<b>'
    # switch tag one last time to remove the correct end of string
    tag = '</b>' if tag == '<b>' else '<b>'
    tmp_snippet = tmp_snippet[:-len(tag)]
    return tmp_snippet
