# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import requests
from urllib.parse import urljoin
from langdetect import detect
from app.api.models import installed_languages
from app import LANGS, AUTH_TOKEN


def extract_from_url(url):
    """ Extract plain text from url"""
    logging.info(">> INDEXER: TXTPARSER: extract_from_url")
    title = url.split('/')[-1]
    body_str = ""
    snippet = ""
    cc = False
    language = LANGS[0]
    try:
        req = requests.get(url, timeout=10, headers={'Authorization': AUTH_TOKEN})
    except Exception:
        logging.error(">> ERROR: INDEXER: TXTPARSER: issue requesting url")
        return title, body_str, snippet, cc
    body_str = req.text
    try:
        language = detect(body_str)
        logging.info(f">> INDEXER: TXTPARSER: Language for {url}: {language}")
    except Exception:
        logging.error(">> ERROR: INDEXER: TXTPARSER: Couldn't detect page language for {url}.")
        return title, body_str, snippet, cc

    snippet = body_str[:200].replace(',', '-')
    return title, body_str, snippet, cc
