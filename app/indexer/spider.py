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
from app.indexer.htmlparser import extract_txt, extract_html, extract_links
from app import LANGS, OMD_PATH, AUTH_TOKEN, FILE_SIZE_LIMIT, IGNORED_EXTENSIONS, GATEWAY_TIMEZONE
from app.utils_db import uptodate, check_group_is_subscribed, create_pod
from app.utils import clean_comma_separated_name, mk_group_name, get_device_from_url

app_dir_path = dirname(dirname(realpath(__file__)))
user_app_dir_path = join(app_dir_path,'userdata')

def get_xml(xml_url, token=AUTH_TOKEN):
    ''' Get a pseudo-xml file from OnMyDisk, which will contain the content of a particular
    user directory.
    '''
    xml = None
    try:
        #xml = requests.get(xml_url, timeout=120, \
        #        headers={'Authorization': 'token:'+token}, stream =True).raw
        #print(xml.read())
        xml = requests.get(xml_url, timeout=120, headers={'Authorization': 'token:'+token}, stream =True).raw
    except RuntimeError as e:
        logging.error(">> ERROR: SPIDER: GET XML: Request failed. Moving on.")
        logging.error(">> MSG: %e", e)
    return xml

def read_xml(xml):
    ''' Read the xml for a particular user directory and parse the content into a dictionary.
    Return: a dictionary with an 'omd_index' key itself containing a 'doc' key.
    The 'doc' key is associated with a list containing all docs for that directory.
    '''
    parse = None
    try:
        xml_content = xml.read()
        xml_content = xml_content.replace(b'&',b' and ')
        parse = xmltodict.parse(xml_content)
    except RuntimeError as e:
        logging.error(">> ERROR: SPIDER: PARSE XML: File may have some bad XML. Could not parse.")
        logging.error(">> MSG: %e", e)
    return parse

def get_docs_from_xml_parse(parse):
    ''' Read the document list included in the XML.
    Return: list of dictionaries, one dictionary per document.
    '''
    docs = None
    try:
        docs = parse['omd_index']['doc']
    except RuntimeError as e:
        logging.error(">> ERROR: SPIDER: get docs from xml parse: No documents found in the XML.")
        logging.error(">> MSG: %e", e)
    return docs


def process_xml(xml_url):
    ''' Call xml processing functions to get metadata about documents in a given directory.
    Return: a list of documents for that directory as well as the directory of xml_url.
    '''
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
    ''' Process a document url in preparation for indexing.

    Args: the document url and the directory currently being processed.

    Return: the preprocessed url and a boolean indicating whether
    we actually want to process that document (see .pearsignore 
    list in the conf folder).
    '''
    url = ""
    process = True

    # Sites have urls starting with '/'
    if doc['@url'][0] == '/':
        url = doc['@url'][1:]
    else:
        url = doc['@url']

    # Shared urls and sites have urls missing the OMD_PATH
    if url.startswith('shared/') or url.startswith('sites/'):
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
    title = None
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
        if url.startswith(join(OMD_PATH,'shared')) or url.startswith(join(OMD_PATH,'sites')):
            title, body_str, _, language = extract_txt(url + "?direct")
        else:
            title, body_str, _, language = extract_txt(url)
    elif content_type in ['text/html']:
        #print(">> Calling extract_html")
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
    group = ""
    try:
        group = doc['@shared_with']
        group = clean_comma_separated_name(group)
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
    gt_tz = timezone(GATEWAY_TIMEZONE)
    last_modified = datetime.strptime(last_modified, '%Y-%m-%d %H:%M:%S')
    last_modified = gt_tz.localize(last_modified)
    return last_modified

def clean_url_and_snippets(url, body_str, description, title):
    if url.endswith('?direct'):
        url = url[:-7]
    snippet = ""
    if body_str.startswith("<omd_index>"):
        if description != title:
            body_str = description
        else:
            body_str = f"Directory {title}"
    if body_str == "":
        description = description or "No description"
    else:
        snippet = ' '.join(body_str.split()[:50])
    return url, title, description, snippet, body_str

def get_doc_info(doc, urldir):
    url, process = get_doc_url(doc, urldir)
    if not process:
        return None
    last_modified = get_last_modified(doc)
    owner = get_doc_owner(doc)
    shared_with = get_doc_shared_with(doc)
    group = mk_group_name(owner, shared_with)
    #print(f"\n>> {url} {group} {owner} {shared_with}")

    #If document belong to a group that is currently unsubscribed, ignore
    if owner != group and  not check_group_is_subscribed(group) and not url.startswith(join(OMD_PATH,"sites")):
        print(f">> {url} is in an unsubscribed group. Returning none.")
        return None
    if last_modified is not None and uptodate(url, last_modified, group):
        #print(f">> {url} is up to date. Returning none.")
        return None
    #print(f"{url} is not up to date. Reindexing.")
    convertible = assess_convertibility(doc)
    content_type, islink = get_doc_content_type(doc, url)
    title = get_doc_title(doc, url)
    description = get_doc_description(doc, title)
    body_title, body_str, language = get_doc_content(url, convertible, content_type)

    #Body title for a site is the open graph title, which we assume is the best title option
    if url.startswith(join(OMD_PATH,'sites')) and body_title:
        title = body_title
    if not title:
        title = ' '.join(body_str.split()[:7])
    url, title, description, snippet, body_str = clean_url_and_snippets(url, body_str, description, title)
    return url, group, islink, title, description, snippet, body_str, language

def process_html_links(url):
    links = extract_links(url)
    processed_links = [url[:-7]] #url ends in ?direct
    for link in links:
        if link not in processed_links:
            processed_links.append(link)
            links.extend(extract_links(link))
            links = list(set(links))
        if set(links) == set(processed_links):
            break
    return links

