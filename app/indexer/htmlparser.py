# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from urllib.parse import urljoin
import requests
import justext
from bs4 import BeautifulSoup
from langdetect import detect
from app import LANGS, AUTH_TOKEN
from app.indexer import detect_open
from app.api.models import installed_languages


def remove_boilerplates(response, lang):
    text = ""
    paragraphs = justext.justext(
        response.content,
        justext.get_stoplist("English"), #FIX FOR MULTIPLE LANGUAGES
        max_link_density=0.3,
        stopwords_low=0.1,
        stopwords_high=0.3,
        length_low=30,
        length_high=100)
    for paragraph in paragraphs:
        #if not paragraph.is_boilerplate:
        text += paragraph.text + " "
    return text


def BS_parse(url):
    req = None
    try:
        req = requests.get(url, allow_redirects=True, timeout=30, headers={'Authorization': AUTH_TOKEN})
        req.encoding = 'utf-8'
    except Exception:
        print("Request failed when trying to index", url, "...")
        return False, req
    if req.status_code != 200:
        logging.exception(
            "Warning: " + str(req.url) + ' has a status code of: ' +
            str(req.status_code) + ' omitted from database.\n')
        return False, req
    bs_obj = BeautifulSoup(req.text, "lxml")
    return bs_obj, req


def extract_links(url):
    links = []
    try:
        req = requests.get(url, timeout=10, headers={'Authorization': AUTH_TOKEN})
        if "text/html" not in req.headers["content-type"]:
            print("Not a HTML document...")
            return links
    except Exception:
        return links
    bs_obj, req = BS_parse(url)
    if not bs_obj:
        return links
    hrefs = bs_obj.findAll('a', href=True)
    for h in hrefs:
        if h['href'].startswith('http') and '#' not in h['href']:
            links.append(h['href'])
        else:
            links.append(urljoin(url, h['href']))
    return links


def extract_html(url):
    '''From history info, extract url, title and body of page,
    cleaned with BeautifulSoup'''
    title = ""
    body_str = ""
    snippet = ""
    language = LANGS[0]
    error = None
    bs_obj, req = BS_parse(url)
    if not bs_obj:
        logging.error(f"\t>> ERROR: extract_html: Failed to get BeautifulSoup object.")
        return title, body_str, snippet, language
    if hasattr(bs_obj.title, 'string'):
        if url.startswith('http'):
            og_title = bs_obj.find("meta", property="og:title")
            og_description = bs_obj.find("meta", property="og:description")
            logging.debug(f"OG TITLE {og_title}")
            logging.debug(f"OG DESC {og_description}")

            # Process title
            if not og_title:
                title = bs_obj.title.string
                if title is None:
                    title = ""
            else:
                title = og_title['content']
 
            # Get body string
            body_str = remove_boilerplates(req, LANGS[0]) #Problematic...
            try:
                language = detect(title + " " + body_str)
                logging.debug(f"\t>> INFO: Language for {url}: {language}")
            except Exception:
                title = ""
                logging.error(f"\t>> ERROR: extract_html: Couldn't detect page language.")
                return title, body_str, snippet, language

            # Process snippet
            if og_description:
                snippet = og_description['content'][:1000]
            else:
                snippet = ' '.join(body_str.split()[:10]) #10 to conform with EU regulations
    return title, body_str, snippet, language


def extract_txt(url):
    logging.info(f">> INDEXER: HTMLPARSER: extract_txt: url: {url}")
    title = url.split('/')[-1].split("?")[0] # read after the last slash, title is everything until any parameters (e.g. "?totext")
    body_str = ""
    snippet = ""
    language = LANGS[0]
    logging.debug(f">> INDEXER: HTMLPARSER: extract_txt: title: {title}")
    try:
        req = requests.get(url, timeout=120, headers={'Authorization': AUTH_TOKEN})
        req.encoding = 'utf-8'
    except Exception:
        return title, body_str, snippet, language
    body_str = req.text
    logging.debug(f">> INDEXER: HTMLPARSER: extract_txt: body: {body_str[:100]}")
    try:
        language = detect(body_str)
        logging.debug(f">> INDEXER: HTMLPARSER: extract_txt: language: {language}")
    except Exception:
        logging.error(f">> ERROR: INDEXER: HTMLPARSER: extract_txt: couldn't detect page language for {url}.")

    snippet = body_str[:200].replace(',', '-')
    return title, body_str, snippet, language
