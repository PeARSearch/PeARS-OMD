# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import re
import numpy as np
import string
from app import db, LOCAL_RUN, VEC_SIZE, OMD_PATH
from app.api.models import Urls, installed_languages, sp
from app.indexer.htmlparser import extract_html
from app.indexer.vectorizer import vectorize_scale
from app.utils import convert_to_string, convert_dict_to_string, normalise
from app.utils_db import delete_url
from scipy.sparse import csr_matrix, vstack, save_npz, load_npz
from os.path import dirname, join, realpath, isfile


dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'static','pods')

def tokenize_text(lang, text):
    sp.load(f'app/api/models/{lang}/{lang}wiki.model')
    text = ' '.join([wp for wp in sp.encode_as_pieces(text.lower())])
    print("TOKENIZED",text)
    return text


def compute_vec(lang, text, pod_m):
    v = vectorize_scale(lang, text, 5, VEC_SIZE) #log prob power 5, top words 100
    pod_m = vstack((pod_m,csr_matrix(v)))
    print("VEC",v,pod_m.shape)
    return pod_m

def get_pod_name(target_url, username):
    pod_name = 'home.u.'+username
    if LOCAL_RUN:
        if 'http://localhost:9090/static/testdocs/shared' in target_url:
            pod_name = 'home.shared.u.'+username
    else:
        if join(OMD_PATH, 'shared') in target_url:
            pod_name = 'home.shared.u.'+username
    return pod_name

def compute_vectors_local_docs(target_url, title, snippet, description, doc, username, lang):
    cc = False
    pod_name = get_pod_name(target_url, username)
    pod_m = load_npz(join(pod_dir, pod_name+'.npz'))
    print("Computing vectors for", target_url, "(",pod_name,")",lang)
    entry = db.session.query(Urls).filter_by(url=target_url).first()
    if entry:
        u = db.session.query(Urls).filter_by(url=target_url).first()
    else:
        u = Urls(url=target_url)
    filename = target_url.split('/')[-1]
    text = filename + " " + title + " " + description + " " + doc
    text = tokenize_text(lang, text)
    #print(text)
    pod_m = compute_vec(lang, text, pod_m)
    u.title = title
    u.snippet = snippet
    u.description = description[:100]
    u.vector = str(pod_m.shape[0]-1)
    u.pod = pod_name
    u.cc = cc
    db.session.add(u)
    db.session.commit()
    save_npz(join(pod_dir,pod_name+'.npz'),pod_m)
    return True, text, u.vector



def compute_query_vectors(query, lang):
    """ Make distribution for query """
    text = tokenize_text(lang, query)
    v = vectorize_scale(lang, text, 5, len(text)) #log prob power 5
    return v, text
