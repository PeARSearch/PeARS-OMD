# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import joblib
from os.path import dirname, realpath, join, isfile, isdir
import os
from datetime import datetime
from pytz import timezone
from app import db, models
from app import OMD_PATH, LANGS, VEC_SIZE, SERVER_HOST, GATEWAY_TIMEZONE
from app.api.models import Urls, Pods
from app.api.models import installed_languages
from app.indexer.posix import load_posix, dump_posix
import numpy as np
from scipy.sparse import csr_matrix, vstack, save_npz, load_npz
from sqlalchemy import update

dir_path = dirname(realpath(__file__))
pod_dir = join(dir_path,'pods')

def get_pod_name(target_url, lang, username, device):
    """ Retrieve correct pod given url and username.
    In particular, checks whether the private or shared
    pod should be used.
    """
    pod_name = f"{username}/{device}/{lang}/private"
    if join(OMD_PATH, 'shared') in target_url:
        pod_name = f"{username}/{device}/{lang}/shared"
    return pod_name


def create_pod_npz_pos(contributor, device):
    """ Pod npz and pos initialisation.
    This should only happens once in the OMD setup, when
    the user indexes for the first time.
    """
    # One idx to url dictionary per user
    user_dir = join(pod_dir, contributor)
    if not isdir(user_dir):
        os.mkdir(user_dir)

    # Separate private from shared for other representations
    for lang in LANGS:
        user_pod_dir = join(user_dir, device, lang)
        if not isdir(user_pod_dir):
            os.makedirs(user_pod_dir)
        pod_path_private = join(user_pod_dir, "private")
        pod_path_shared = join(user_pod_dir, "shared")
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


def create_pod_in_db(contributor, lang, device):
    """ Pod database initialisation.
    If the pod does not exist, create it in the database.
    """

    def commit(path):
        if not db.session.query(Pods).filter_by(url=path).all():
            p = Pods(url=path)
            p.name = path
            p.description = path
            p.language = lang
            db.session.add(p)
            db.session.commit()

    path_private = f"{contributor}/{device}/{lang}/private"
    path_shared = f"{contributor}/{device}/{lang}/shared"
    commit(path_private)
    commit(path_shared)


def create_or_replace_url_in_db(target_url, title, snippet, description, idv, username, lang, device):
    pod_name = get_pod_name(target_url, lang, username, device)
    entry = db.session.query(Urls).filter_by(url=target_url).first()
    if entry:
        u = db.session.query(Urls).filter_by(url=target_url).first()
    else:
        u = Urls(url=target_url)
    u.title = title
    u.snippet = snippet
    u.description = description[:100]
    u.vector = idv
    u.pod = pod_name
    db.session.add(u)
    db.session.commit()
    print(f"Adding URL {target_url}, {idv}, {pod_name}")
    return u.id


def rm_from_npz(vid, pod_name):
    """ Remove vector from npz file.
    Arguments:
    vid: the row number of the vector
    pod_path: the path to the pod containing the vector

    Returns: the deleted vector
    """
    pod_path = join(pod_dir, pod_name+'.npz')
    pod_m = load_npz(pod_path)
    logging.debug(f"SHAPE OF NPZ MATRIX BEFORE RM: {pod_m.shape}")
    v = pod_m[vid]
    logging.debug(f"CHECKING SHAPE OF DELETED VEC: {pod_m.shape}")
    m1 = pod_m[:vid]
    m2 = pod_m[vid+1:]
    pod_m = vstack((m1,m2))
    logging.debug(f"SHAPE OF NPZ MATRIX AFTER RM: {pod_m.shape}")
    save_npz(pod_path, pod_m)
    return vid

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
    lang = pod.split('/')[2]  # pod = "user/device/lang/pod_name"
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
    lang = pod.split('/')[2]  # pod = "user/device/lang/pod_name"
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


def update_db_idvs_after_npz_delete(idv, pod):
    condition = (Urls.pod == pod) & (Urls.vector > idv)
    update_stmt = update(Urls).where(condition).values(vector=Urls.vector-1)
    db.session.execute(update_stmt)


def delete_url(url):
    """ Delete url with some url on some pod.
    """
    u = db.session.query(Urls).filter_by(url=url).first()
    pod = u.pod
    username = pod.split('/')[0]  # pod = "user/device/lang/pod_name"
    print("POD",pod,"USER",username)

    #Remove document row from .npz matrix
    idv = rm_from_npz(u.vector, pod)

    #Remove doc from positional index
    rm_doc_from_pos(u.id, pod)

    #Update database idvs
    update_db_idvs_after_npz_delete(idv, pod)

    #Delete from database
    db.session.delete(u)
    db.session.commit()
    return "Deleted document with url "+url

def uptodate(url, date):
    """ Compare last modified in database with given datetime
    """
    up_to_date = False
    u = db.session.query(Urls).filter_by(url=url).first()
    if u is None:
        return up_to_date
    db_datetime = u.date_modified.astimezone(timezone(GATEWAY_TIMEZONE))
    print(f"DB DATE: {db_datetime}, LAST MODIFIED: {date}")
    if db_datetime >= date:
        up_to_date = True
    return up_to_date
