# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import re
import numpy as np
import string
from app import db, VEC_SIZE
from app.api.models import Urls, installed_languages, sp
from app.indexer.htmlparser import extract_html
from app.indexer.vectorizer import vectorize_scale
from app.utils import convert_to_string, convert_dict_to_string, normalise
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


def compute_vectors_local_docs(target_url, title, snippet, description, doc, keyword, lang):
    cc = False
    pod_m = load_npz(join(pod_dir,keyword+'.npz'))
    f = open(join(pod_dir,'corpus.tok'),'a')
    #if not db.session.query(Urls).filter_by(title=title).all():
    print("Computing vectors for", target_url, "(",keyword,")",lang)
    u = Urls(url=target_url)
    text = title + " " + description + " " + doc
    #print(text)
    text = tokenize_text(lang, text)
    f.write('\n\n'+title+'\n')
    f.write(text)
    pod_m = compute_vec(lang, text, pod_m)
    u.title = title
    u.snippet = snippet
    u.description = description[:100]
    u.vector = str(pod_m.shape[0]-1)
    u.keyword = keyword
    u.pod = keyword
    u.cc = cc
    db.session.add(u)
    db.session.commit()
    save_npz(join(pod_dir,keyword+'.npz'),pod_m)
    podsum = np.sum(pod_m, axis=0)
    return True, podsum, text, u.vector



def compute_query_vectors(query, lang):
    """ Make distribution for query """
    text = tokenize_text(lang, query)
    v = vectorize_scale(lang, text, 5, len(text)) #log prob power 5
    return v, text
