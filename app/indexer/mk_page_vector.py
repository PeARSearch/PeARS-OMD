# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import dirname, join, realpath
from scipy.sparse import csr_matrix, vstack, save_npz, load_npz
from app import db, VEC_SIZE
from app.api.models import sp
from app.indexer.vectorizer import vectorize_scale
from app.utils_db import get_pod_name

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'pods')

def tokenize_text(lang, text):
    sp.load(f'app/api/models/{lang}/{lang}wiki.model')
    text = ' '.join([wp for wp in sp.encode_as_pieces(text.lower())])
    #print("TOKENIZED",text)
    return text


def compute_vec(lang, text, pod_m):
    v = vectorize_scale(lang, text, 5, VEC_SIZE) #log prob power 5, top words 100
    pod_m = vstack((pod_m,csr_matrix(v)))
    #print("VEC",v,pod_m.shape)
    return pod_m


def compute_vectors_local_docs(target_url, title, description, doc, username, lang):
    pod_name = get_pod_name(target_url, lang, username)
    pod_m = load_npz(join(pod_dir, pod_name+'.npz'))
    #print("Computing vectors for", target_url, "(",pod_name,")",lang)
    filename = target_url.split('/')[-1]
    text = filename + " " + title + " " + description + " " + doc
    text = tokenize_text(lang, text)
    #print(text)
    pod_m = compute_vec(lang, text, pod_m)
    vid = pod_m.shape[0] - 1
    save_npz(join(pod_dir,pod_name+'.npz'),pod_m)
    return pod_name, vid, text


def compute_query_vectors(query, lang):
    """ Make distribution for query """
    text = tokenize_text(lang, query)
    v = vectorize_scale(lang, text, 5, len(text)) #log prob power 5
    return v, text
