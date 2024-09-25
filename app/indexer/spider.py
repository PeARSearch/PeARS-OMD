# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os.path import join, dirname, realpath
from flask import url_for
import xmltodict
import requests
from datetime import datetime
from pytz import timezone
from langdetect import detect
from app.indexer.htmlparser import extract_txt, extract_html
from app import (LANGS, OMD_PATH, 
        AUTH_TOKEN, FILE_SIZE_LIMIT, IGNORED_EXTENSIONS, GATEWAY_TIMEZONE)

app_dir_path = dirname(dirname(realpath(__file__)))
user_app_dir_path = join(app_dir_path,'userdata')

def get_xml(xml_url):
    xml = None
    try:
        xml = requests.get(xml_url, timeout=120, \
            headers={'Authorization': AUTH_TOKEN}, stream =True).raw
        print(xml.read())
        xml = requests.get(xml_url, timeout=60, \
            headers={'Authorization': AUTH_TOKEN}, stream =True).raw
    except RuntimeError as error:
        logging.error(">> ERROR: SPIDER: GET XML: Request failed. Moving on.")
        logging.error(error)
    return xml

def read_xml(xml):
    parse = None
    try:
        xml_content = xml.read()
        parse = xmltodict.parse(xml_content)
    except:
        logging.error(">> ERROR: SPIDER: PARSE XML: File may have some bad XML. Could not parse.")
    return parse

def get_docs_from_xml_parse(parse):
    docs = None
    try:
        docs = parse['omd_index']['doc']
    except:
        logging.error(">> ERROR: SPIDER: get docs from xml parse: No documents found in the XML.")
    return docs


def process_xml(xml_url, username):
    logging.info("\n>> INDEXER: SPIDER: xml_parse: Running OMD parse on "+xml_url)
    urldir = '/'.join(xml_url.split('/')[:-1])
    docs = []

    xml = get_xml(xml_url)
    if xml is None:
        return docs, urldir
    
    parse = read_xml(xml)
    if parse is None:
        return docs, urldir

    docs = get_docs_from_xml_parse(parse)
    if docs is None:
        return docs, urldir

    if not isinstance(docs, list):
        docs = [docs]
    return docs, urldir


def get_doc_url(doc, urldir):

    url = ""
    process = True

    if doc['@url'][0] == '/':
        url = doc['@url'][1:]
    else:
        url = doc['@url']
    if url.startswith('shared/'):
        url = join(OMD_PATH, url)
    else:
        url = join(urldir, url)
    logging.info(">> INDEXER: SPIDER: get url from doc: doc url: "+url)
   
   # Is this item a folder description?
    is_folder_description = url.endswith("?description")
    if is_folder_description:
        url = url.replace("?description", "")

    # Check item extension: should we process it?
    extension = '.'+url.split('/')[-1].split('.')[-1]
    if extension in IGNORED_EXTENSIONS:
        process = False

    return url, process


def assess_convertibility(doc):
    convertible = False
    try:
        logging.info(f">> SPIDER: ASSESS CONVERTIBILITY: {doc.get('@convertible')}")
        convertible_str = doc.get("@convertible")
        assert convertible_str in ["True", "False", None]
        convertible = True if convertible_str == "True" else False 
  
    except RuntimeError as error:
        logging.info(">> SPIDER: ASSESS CONVERTIBILITY: No convertibility found.")
        logging.info(error)
    return convertible


def get_doc_content_type(doc, url):
    content_type = None
    islink = False
    try:
        logging.info(f">> SPIDER: GET DOC CONTENTTYPE: {doc['@contentType']}")
        content_type = doc['@contentType']
        if content_type in ['folder','desktop']:
            if join(OMD_PATH,'shared') not in url:
                islink = True
    except RuntimeError as error:
        logging.info(">> SPIDER: OMD_PARSE: DOC CONTENTTYPE: No contentType")
        logging.info(error)
    return content_type, islink


def get_doc_title(doc, url):
    title = ""
    try:
        logging.info(f">> SPIDER: GET DOC TITLE: {doc['title']}")
        title = doc['title']
    except RuntimeError as error:
        logging.info(">> SPIDER: GET DOC TITLE: No title")
        logging.info(error)
    if title is None:
        is_folder_description = url.endswith("?description")
        if is_folder_description:
            title = doc["description"]
    return title


def get_doc_description(doc, title):
    description = ""
    try:
        logging.info(f">> SPIDER: GET DOC DESCRIPTION: {doc['description'][:100]}")
        if title != doc['description']:
            description = title + ' ' + doc['description']
        else:
            description = doc['description']
        logging.info("\t"+description+"\n")
    except:
        logging.info(">> SPIDER: GET DOC DESCRIPTION: No description")
    return description


def get_doc_content(url, convertible, content_type):
    title = ""
    body_str = ""
    language = LANGS[0]
    is_folder_description = url.endswith("?description")
    
    if convertible:
        title, body_str, _, language = extract_txt(url + "?totext")
    elif is_folder_description:
        _, body_str, _, language = extract_txt(url + "?description")
    elif content_type in ['text/plain', 'text/x-tex']:
        title, body_str, _, language = extract_txt(url)
    elif content_type in ['text/html']:
        title, body_str, _, language = extract_html(url)

    # Hack. Revert to main language if language is not installed
    if language not in LANGS:
        logging.info(">> SPIDER: LANGUAGE: language is not in LANGS, reverting to default.")
        language = LANGS[0]

    return title, body_str, language

def get_doc_owner(doc):
    owner = ""
    try:
        owner = doc['@owner']
    except:
        logging.info(">> SPIDER: GET DOC OWNER: No owner found.")
    return owner

def get_doc_shared_with(doc):
    group = []
    try:
        group = doc['shared_with'].split(',')
    except:
        logging.info(">> SPIDER: GET DOC SHARED_WITH: No group found.")
    return group

def get_last_modified(doc):
    last_modified = ""
    try:
        last_modified = doc['@last_modified']
    except:
        logging.info(">> SPIDER: GET LAST MODIFIED: No date found.")
        return None
    last_modified = datetime.strptime(last_modified, '%Y-%m-%d %H:%M:%S').astimezone(timezone(GATEWAY_TIMEZONE))
    return last_modified
