# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os.path import dirname, realpath, join, isfile, isdir
from os import remove
from pathlib import Path
from datetime import datetime
from pytz import timezone
import joblib
from app import db, models
from app import OMD_PATH, LANGS, VEC_SIZE, SERVER_HOST, GATEWAY_TIMEZONE
from app.utils import hash_username
from app.api.models import Urls, Pods, Locations, Groups, Sites
from app.api.models import installed_languages
from app.indexer.posix import load_posix, dump_posix
import numpy as np
from scipy.sparse import csr_matrix, vstack, save_npz, load_npz
from sqlalchemy import update

dir_path = dirname(realpath(__file__))
pod_dir = join(dir_path,'pods')

def get_permission_class(url, owner):
    """ Use document url and owner to determine
    whether the document is publicly shared ('others'),
    private ('user'), or shared with a group ('group').
    """
    if join(OMD_PATH, 'shared') in url:
        return 'others'
    elif ',' not in owner:
        return 'user'
    else:
        return 'group'

def uptodate(url, date, group):
    """ Compare last modified in database with given datetime.
    Also check for permission changes.
    """
    up_to_date = False
    u = db.session.query(Urls).filter_by(url=url).first()
    if u is None:
        return up_to_date
    utc_tz = timezone('UTC')
    db_datetime = utc_tz.localize(u.date_modified).astimezone(timezone(GATEWAY_TIMEZONE))
    #print(f"DB DATE: {db_datetime}, LAST MODIFIED: {date}")
    group_hash = hash_username(group)
    db_group_hash = u.pod.split('/')[0]
    if db_datetime >= date and group_hash == db_group_hash:
        up_to_date = True
    return up_to_date

def check_group_is_subscribed(group):
    """ Check whether the given group is marked as
    subscribed in the database.
    """
    g = db.session.query(Groups).filter_by(name=group).first()
    if g and g.subscribed:
        return True
    return False



##############
# CREATIONS
##############

def create_pod_npz_pos(path):
    """ Pod npz and pos initialisation.
    """
    user_dir = join(pod_dir, dirname(path))
    Path(user_dir).mkdir(exist_ok=True, parents=True)
    if not isfile(path+'.npz'):
        print("Making 0 CSR matrix for new pod")
        pod = np.zeros((1,VEC_SIZE))
        pod = csr_matrix(pod)
        save_npz(join(pod_dir, path+'.npz'), pod)

    if not isfile(path+'.pos'):
        print("Making empty positional index for new pod")
        posindex = [{} for _ in range(VEC_SIZE)]
        joblib.dump(posindex, join(pod_dir, path+'.pos'))


def create_pod(url, owner, lang, device):
    """ Pod initialisation.
    If the pod does not exist, create it in the database.
    Add .npz and .pos files
    """

    def commit(path, owner_hash):
        if not db.session.query(Pods).filter_by(url=path).all():
            print("Pod does not exist:",path,owner_hash)
            create_pod_npz_pos(path)
            p = Pods(url=path)
            p.name = owner_hash
            p.description = path
            p.language = lang
            p.owner = owner
            db.session.add(p)
            db.session.commit()
    
    permission_class = get_permission_class(url, owner)
    owner_hash = hash_username(owner)
    path = f"{owner_hash}/{device}/{lang}/{permission_class}"
    commit(path, owner_hash)
    return path


def create_url_in_db(target_url, title, snippet, description, idv, pod_path):
    u = Urls(url=target_url)
    u.title = title
    u.snippet = snippet
    u.description = description[:100]
    u.vector = idv
    u.pod = pod_path
    db.session.add(u)
    db.session.commit()
    #print(f"Adding URL {target_url}, {idv}, {pod_path}")
    return u.id


def subscribe_location(location):
    l = db.session.query(Locations).filter_by(name=location).first()
    if l:
        l.subscribed = True
        db.session.add(l)
        db.session.commit()
        print(f"Subscribing Location {location}")


def update_locations_in_db(locations, device=False):
    #Add locations not in the database
    for location in locations:
        l = db.session.query(Locations).filter_by(name=location).first()
        if l:
            continue
        l = Locations(name=location)
        l.device = device
        l.subscribed = False
        db.session.add(l)
        db.session.commit()
        print(f"Adding Location {location}")

    #Delete locations that do not exist anymore
    locations_in_db = db.session.query(Locations).all()
    for l in locations_in_db:
        if l.name not in locations:
            #Device case vs non-device case
            if (device and l.device) or (not device and not l.device):
                print(f">> {l.name} does not exist anymore.")
                db.session.delete(l)
                db.session.commit()


def update_groups_in_db(groups):
    #Add groups not in the database
    for group in groups:
        g = db.session.query(Groups).filter_by(name=group).first()
        if g:
            continue
        g = Groups(name=group)
        g.subscribed = True
        g.identifier = hash_username(group)
        db.session.add(g)
        db.session.commit()
        print(f"Adding Group {group}")

    #Delete groups that do not exist anymore
    groups_in_db = db.session.query(Groups).all()
    for g in groups_in_db:
        if g.name not in groups:
            print(f">> {g.name} does not exist anymore.")
            db.session.delete(g)
            db.session.commit()


def update_sites_in_db(sites):
    #Add sites not in the database
    site_urls = [s['url'] for s in sites]
    for site in sites:
        s = db.session.query(Sites).filter_by(url=site['url']).first()
        if not s:
            s = Sites(url=site['url'])
            s.subscribed = False
        s.name = site['name']
        s.title = site['title']
        s.owner = site['owner']
        s.description = site['description']
        db.session.add(s)
        db.session.commit()
        print(f"Adding Site {site}")

    #Delete sites that do not exist anymore
    sites_in_db = db.session.query(Sites).all()
    for s in sites_in_db:
        if s.url not in site_urls:
            print(f">> {s.url} does not exist anymore.")
            db.session.delete(s)
            db.session.commit()


##############
# ADDITIONS
##############

def add_to_npz(v, pod_path):
    """ Add new pre-computed vector to npz matrix.
    Arguments:
    v: the vector to add
    pod_path: the path to the target pod

    Returns:
    vid: the new row number for the vector
    """
    pod_path = join(pod_dir, pod_path+'.npz')
    pod_m = load_npz(pod_path)
    pod_m = vstack((pod_m,csr_matrix(v)))
    save_npz(pod_path, pod_m)
    vid = pod_m.shape[0]
    return vid

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



##############
# DELETIONS
##############

def rm_from_npz(vid, pod_path):
    """ Remove vector from npz file.
    Arguments:
    vid: the row number of the vector
    pod_path: the path to the pod containing the vector

    Returns: the deleted vector
    """
    pod_path = join(pod_dir, pod_path+'.npz')
    pod_m = load_npz(pod_path)
    #print(f"SHAPE OF NPZ MATRIX BEFORE RM: {vid} {pod_m.shape}")
    v = pod_m[vid]
    #print(f"CHECKING SHAPE OF DELETED VEC: {pod_m.shape}")
    m1 = pod_m[:vid]
    m2 = pod_m[vid+1:]
    pod_m = vstack((m1,m2))
    #print(f"SHAPE OF NPZ MATRIX AFTER RM: {pod_m.shape}")
    save_npz(pod_path, pod_m)
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
    u = db.session.query(Urls).filter_by(url=url).first()
    return "Deleted document with url "+url

def delete_pod(pod_path):
    pod = db.session.query(Pods).filter_by(url=pod_path).first()
    if pod is not None:
        urls = db.session.query(Urls).filter_by(pod=pod_path).all()
        if urls is not None:
            for u in urls:
                #This is going to be slow for many urls...
                db.session.delete(u)
                db.session.commit()
        npz_path = join(pod_dir, pod_path+'.npz')
        if isfile(npz_path):
            remove(npz_path)
        pos_path = join(pod_dir, pod_path+'.pos')
        if isfile(pos_path):
            remove(pos_path)
        db.session.delete(pod)
        db.session.commit()
    return "Deleted pod with path "+pod_path

def delete_old_urls(start_urls, urls):
    """Compare set of urls in a folder with
    current state of database and delete urls
    that do not exist anymore.
    """
    print(">> DELETING OLD URLS")
    urls_in_db = db.session.query(Urls).all()
    for u in urls_in_db:
        if any(u.url.startswith(s) for s in start_urls) and u.url not in urls:
            print(f">> {u.url} does not exist anymore.")
            delete_url(u.url)

def delete_unsubscribed():
    """Delete urls which now belong to an
    unsubscribed location.
    """
    print(">> DELETING UNSUBSCRIBED URLS")
    urls = db.session.query(Urls).all()
    if urls is not None:
        for u in urls:
            #This is going to be slow for many urls...
            url = u.url
            if url[-1] == '/':
                loc = url
            else:
                loc = '/'.join(url.split('/')[:-1])+'/'
            l = db.session.query(Locations).filter_by(name=loc).first()
            if l and not l.subscribed:
                print(f">> {u.url} has been unsubscribed.")
                db.session.delete(u)
                db.session.commit()

