# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import joblib
from app import db, models
from app import LOCAL_RUN, OMD_PATH, LANGS, VEC_SIZE
from app.api.models import Urls, Pods
from app.api.models import installed_languages
from app.indexer.posix import load_posix, dump_posix
from app.utils import convert_to_array, convert_string_to_dict, convert_to_string, normalise
import numpy as np
from os.path import dirname, realpath, join, isfile
from scipy.sparse import csr_matrix, vstack, save_npz, load_npz

dir_path = dirname(realpath(__file__))
pod_dir = join(dir_path,'pods')

def get_pod_name(target_url, lang, username):
    """ Retrieve correct pod given url and username.
    In particular, checks whether the private or shared
    pod should be used.
    """
    pod_name = 'home.'+lang+'.u.'+username
    if LOCAL_RUN:
        if 'http://localhost:9090/testdocs/shared' in target_url:
            pod_name = 'home.'+lang+'.shared.u.'+username
    else:
        if join(OMD_PATH, 'shared') in target_url:
            pod_name = 'home.'+lang+'.shared.u.'+username
    return pod_name




def create_pod_npz_pos(contributor):
    """ Pod npz and pos initialisation.
    This should only happens once in the OMD setup, when
    the user indexes for the first time.
    """
    # One idx to url dictionary per user
    pod_path = join(pod_dir, contributor+'.idx')
    if not isfile(pod_path):
        print("Making idx dictionaries for new pod")
        idx_to_url = [[],[]]
        joblib.dump(idx_to_url, pod_path)

    # Separate private from shared for other representations
    for lang in LANGS:
        pod_path_private = join(pod_dir,'home.'+lang+'.u.'+contributor)
        pod_path_shared = join(pod_dir,'home.'+lang+'.shared.u.'+contributor)
        for pod_path in [pod_path_private, pod_path_shared]:
            if not isfile(pod_path+'.npz'):
                print("Making 0 CSR matrix for new pod")
                pod = np.zeros((1,VEC_SIZE))
                pod = csr_matrix(pod)
                save_npz(pod_path+'.npz', pod)

            if not isfile(pod_path+'.pos'):
                print("Making empty positional index for new pod")
                posindex = [{} for _ in range(VEC_SIZE)]
                joblib.dump(posindex, pod_path+'.pos')

            if not isfile(pod_path+'.npz.idx'):
                print("Making idx dictionaries for new pod")
                # Lists of lists to make deletions easier
                npz_to_idx = [[0],[-1]] # For row 0 of the matrix
                joblib.dump(npz_to_idx, pod_path+'.npz.idx')


def create_pod_in_db(contributor, lang):
    """ Pod database initialisation.
    If the pod does not exist, create it in the database.
    """

    def commit(url, name):
        if not db.session.query(Pods).filter_by(url=url).all():
            p = Pods(url=url)
            p.name = name
            p.description = name
            p.language = lang
            p.registered = True
            db.session.add(p)
            db.session.commit()

    name_private = 'home.'+lang+'.u.'+contributor
    name_shared = 'home.'+lang+'.shared.u.'+contributor
    url_private = "http://localhost:8080/api/pods/" + name_private.replace(' ', '+')
    url_shared = "http://localhost:8080/api/pods/" + name_shared.replace(' ', '+')
    commit(url_private, name_private)
    commit(url_shared, name_shared)


def create_or_replace_url_in_db(target_url, title, snippet, description, username, lang):
    cc = False
    pod_name = get_pod_name(target_url, lang, username)
    entry = db.session.query(Urls).filter_by(url=target_url).first()
    if entry:
        u = db.session.query(Urls).filter_by(url=target_url).first()
    else:
        u = Urls(url=target_url)
    u.title = title
    u.snippet = snippet
    u.description = description[:100]
    u.pod = pod_name
    u.cc = cc
    db.session.add(u)
    db.session.commit()

def rename_idx_to_url(contributor, src, tgt):
    pod_path = join(pod_dir, contributor+'.idx')
    idx_to_url = joblib.load(pod_path)
    i = idx_to_url[1].index(src)
    idx_to_url[1][i] = tgt
    joblib.dump(idx_to_url, pod_path)


def add_to_idx_to_url(contributor, url):
    pod_path = join(pod_dir, contributor+'.idx')
    idx_to_url = joblib.load(pod_path)
    idx = idx_to_url[0]
    urls = idx_to_url[1]
    new = True #was there an old version of this URL in the index?
    if url in urls:
        i = idx[urls.index(url)]
        new = False
        return new, i
    if len(idx_to_url[0]) > 0:
        i = max(idx_to_url[0])+1
    else:
        i = 0
    idx_to_url[0].append(i)
    idx_to_url[1].append(url)
    joblib.dump(idx_to_url, pod_path)
    return new, i


def rm_from_idx_to_url(contributor, url):
    pod_path = join(pod_dir, contributor+'.idx')
    idx_to_url = joblib.load(pod_path)
    logging.debug("IDX_TO_URL BEFORE RM",idx_to_url)
    i = idx_to_url[1].index(url)
    idx = idx_to_url[0][i]
    idx_to_url[0].pop(i)
    idx_to_url[1].pop(i)
    logging.debug("IDX_TO_URL AFTER RM",idx_to_url)
    logging.debug("INDEX OF REMOVED ITEM",idx)
    joblib.dump(idx_to_url, pod_path)
    return idx


def add_to_npz_to_idx(pod_name, idx):
    """Record the ID of the document given
    its position in the npz matrix.
    NB: the lists do not have to be in the
    order of the matrix.
    """
    pod_path = join(pod_dir, pod_name+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    if idx not in npz_to_idx[1]:
        npz_to_idx[1].append(idx)
        npz_to_idx[0] = list(range(len(npz_to_idx[1])))
        joblib.dump(npz_to_idx, pod_path)


def rm_from_npz_to_idx(pod_name, idx):
    """Remove doc from npz to idx record.
    NB: the lists do not have to be in the
    order of the matrix.
    """
    pod_path = join(pod_dir, pod_name+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    if idx in npz_to_idx[1]:
        logging.debug("NPZ_TO_IDX BEFORE RM:",npz_to_idx)
        i = npz_to_idx[1].index(idx)
        npz_to_idx[1].pop(i)
        npz_to_idx[0] = list(range(len(npz_to_idx[1])))
        logging.debug("NPZ_TO_IDX AFTER RM:",npz_to_idx)
        logging.debug("INDEX OF REMOVED ITEM",i)
        joblib.dump(npz_to_idx, pod_path)
        return i
    return -1


def rm_from_npz(vid, pod_name):
    """ Remove vector from npz file.
    Arguments:
    vid: the row number of the vector
    pod_path: the path to the pod containing the vector

    Returns: the deleted vector
    """
    pod_path = join(pod_dir, pod_name+'.npz')
    pod_m = load_npz(pod_path)
    logging.debug("SHAPE OF NPZ MATRIX BEFORE RM:",pod_m.shape)
    v = pod_m[vid]
    logging.debug("CHECKING SHAPE OF DELETED VEC:",pod_m.shape)
    m1 = pod_m[:vid]
    m2 = pod_m[vid+1:]
    pod_m = vstack((m1,m2))
    logging.debug("SHAPE OF NPZ MATRIX AFTER RM:",pod_m.shape)
    save_npz(pod_path, pod_m)
    return v

def add_to_npz(v, pod_path):
    """ Add new pre-computed vector to npz matrix.
    Arguments:
    v: the vector to add
    pod_path: the path to the target pod

    Returns:
    vid: the new row number for the vector
    """
    pod_m = load_npz(pod_path)
    pod_m = vstack((pod_m,csr_matrix(v)))
    save_npz(pod_path, pod_m)
    vid = pod_m.shape[0]
    return vid

def rm_doc_from_pos(vid, pod):
    """ Remove wordpieces from pos file.
    Arguments:
    vid: the ID of the document recording the wordpieces
    pod: the name of the pod

    Returns: the content of the positional index for that vector.
    """
    lang = pod.split('.')[1]
    vocab = models[lang]['vocab']
    posindex = load_posix(pod)
    remaining_posindex = []
    deleted_posindex = []
    for token in vocab:
        token_id = vocab[token]
        tmp_remaining = {}
        tmp_deleted = {}
        for doc_id, posidx in posindex[token_id].items():
            if doc_id != vid:
                tmp_remaining[doc_id] = posidx
            else:
                tmp_deleted[doc_id] = posidx
        remaining_posindex.append(tmp_remaining)
        deleted_posindex.append(tmp_deleted)
    dump_posix(remaining_posindex,pod)
    return deleted_posindex


def add_doc_to_pos(mini_posindex, pod):
    """ Add positional info to a pod.
    Arguments:
    pos: the positional info to be added (like
    a mini positional index).
    pod: the name of the target pod.
    """
    lang = pod.split('.')[1]
    vocab = models[lang]['vocab']
    posindex = load_posix(pod)
    for token in vocab:
        token_id = vocab[token]
        if len(mini_posindex[token_id]) == 0:
            continue
        for doc_id, posidx in mini_posindex[token_id].items():
            # Add new doc_id
            posindex[token_id][doc_id] = posidx
    dump_posix(posindex,pod)


def delete_url(url):
    """ Delete url with some url on some pod.
    """
    u = db.session.query(Urls).filter_by(url=url).first()
    pod = u.pod
    username = pod.split('.u.')[1]
    print("POD",pod,"USER",username)
    idx = rm_from_idx_to_url(username, url)
    vid = rm_from_npz_to_idx(pod, idx)

    #Remove document row from .npz matrix
    rm_from_npz(vid, pod)

    #Remove doc from positional index
    rm_doc_from_pos(idx, pod)

    #Delete from database
    db.session.delete(u)
    db.session.commit()
    return "Deleted document with url "+url


