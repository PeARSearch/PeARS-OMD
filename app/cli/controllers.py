# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import joblib
from collections import Counter
from shutil import copy2, copytree
from os.path import dirname, realpath, join
from datetime import datetime
from pathlib import Path
from random import shuffle
from flask import Blueprint
import click
from scipy.sparse import load_npz, save_npz
from app import db, Urls, Pods
from app.indexer.posix import load_posix
from app.utils_db import rm_from_idx_to_url, rm_from_npz, rm_doc_from_pos

pears = Blueprint('pears', __name__)

dir_path = dirname(dirname(dirname(realpath(__file__))))
pod_dir = join(dir_path,'app','pods')


@pears.cli.command('backup')
@click.argument('backupdir')
def backup(backupdir):
    '''Backup database and pods to specified directory'''
    #Check if directory exists, otherwise create it
    Path(backupdir).mkdir(parents=True, exist_ok=True)
    #Get today's date
    date = datetime.now().strftime('%Y-%m-%d-%Hh%Mm')
    dirpath = join(backupdir,'pears-'+date)
    Path(dirpath).mkdir(parents=True, exist_ok=True)
    #Copy database
    copy2('app.db',dirpath)
    #Copy pods folder
    copytree(pod_dir, join(dirpath,'pods'))

@pears.cli.command('deletedbonly')
def deletedbonly():
    pods = Pods.query.all()
    for pod in pods:
        urls = Urls.query.filter_by(pod=pod.name).all()
        for u in urls:
            db.session.delete(u)
            db.session.commit()


#####################
# UNIT TESTS
#####################

@pears.cli.command('unittest')
@click.argument('username')
def checkconsistency(username):
    print("\n>> CLI: UNITTEST: CONSISTENCY CHECKS")
    pods = Pods.query.all()
    usernames = [p.name.split('.u.')[1] for p in pods]
    if username not in usernames:
        print("\t> ERROR: no username",username)
        return 0
    check_idx_to_url(username)
    check_missing_docs_in_npz(username)
    check_duplicates_idx_to_url(username)
    check_db_vs_idx_to_url(username)
    print("\n")
    pods = [p for p in pods if p.name.split('.u.')[1] == username]
    for pod in pods:
        print(">> CLI: UNITTEST: CONSISTENCY: CHECKING POD:", pod.name)
        check_npz_to_idx(pod.name)
        check_npz_to_idx_vs_idx_to_url(pod.name, username)
        check_npz_vs_npz_to_idx(pod.name)
        check_pos_vs_npz_to_idx(pod.name)


def check_idx_to_url(username):
    print("\t>> CHECKING IDX_TO_URL")
    pod_path = join(pod_dir, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    if len(idx_to_url[0]) != len(idx_to_url[1]):
        print("\t\t> ERROR: the two lists in idx_to_url do not match in length", len(idx_to_url[0]), len(idx_to_url[1]))
    return idx_to_url


def check_db_vs_idx_to_url(username):
    print("\t>> CHECKING DB VS IDX_TO_URL")
    urls = []
    pods = Pods.query.all()
    pods = [p for p in pods if p.name.split('.u.')[1] == username]
    for pod in pods:
        urls.extend(Urls.query.filter_by(pod=pod.name).all())
    urls = [url.url for url in urls]
    pod_path = join(pod_dir, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    if len(set(urls)) != len(set(idx_to_url[1])):
        print("\t\t> ERROR: Length of URL set in DB != len(set(idx)) in idx_to_url", len(urls), len(idx_to_url[0]))
        return list(set(urls)-set(idx_to_url[1]))
    return []


def check_duplicates_idx_to_url(username):
    print("\t>> CHECKING DUPLICATES IN IDX_TO_URL")
    pod_path = join(pod_dir, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    if len(idx_to_url[0]) > len(list(set(idx_to_url[0]))):
        print("\t\t> ERROR: Duplicates in idx_to_url (idx)")
    if len(idx_to_url[1]) > len(list(set(idx_to_url[1]))):
        print("\t\t> ERROR: Duplicates in idx_to_url (urls)")


def check_missing_docs_in_npz(username):
    print("\t>> CHECKING DOCS IN IDX_TO_URL WITHOUT A VECTOR")
    pod_path = join(pod_dir, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    all_npz_idx = []
    pods = Pods.query.all()
    pods = [p for p in pods if p.name.split('.u.')[1] == username]
    for pod in pods:
        pod_path = join(pod_dir, pod.name+'.npz.idx')
        npz_to_idx = joblib.load(pod_path)
        all_npz_idx.extend(npz_to_idx[1][1:])
    #A URL can be in two pods (home+shared)
    if set(all_npz_idx) != set(idx_to_url[0]):
        diff = list(set(idx_to_url[0])-set(all_npz_idx))
        print("\t\t> ERROR: Some documents in idx_to_url do not have a vector associated with them.")
        print("\t\t>      :", diff)
        return diff
    return []


def check_npz_to_idx(pod):
    print("\t>> CHECKING NPZ_TO_IDX")
    pod_path = join(pod_dir, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    if len(npz_to_idx[0]) != len(npz_to_idx[1]):
        print("\t\t> ERROR: the two lists in npz_to_idx do not match in length", len(npz_to_idx[0]), len(npz_to_idx[1]))
    if len(npz_to_idx[0]) > len(list(set(npz_to_idx[0]))):
        print("\t\t> ERROR: Duplicates in npz_to_idx (npz)")
    if len(npz_to_idx[1]) > len(list(set(npz_to_idx[1]))):
        print("\t\t> ERROR: Duplicates in npz_to_idx (idx)")


def check_npz_to_idx_vs_idx_to_url(pod, username):
    print("\t>> CHECKING NPZ_TO_IDX VS IDX_TO_URL")
    pod_path = join(pod_dir, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    pod_path = join(pod_dir, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    idx1 = idx_to_url[0]
    idx2 = npz_to_idx[1][1:] #Ignore first value, which is -1
    if not set(idx2) <= set(idx1):
        print("\t\t> ERROR: idx in npz_to_idx is not a subset of idx in idx_to_url")


def check_npz_vs_npz_to_idx(pod):
    print("\t>> CHECKING NPZ_TO_IDX VS IDX_TO_URL")
    pod_path = join(pod_dir, pod+'.npz')
    pod_m = load_npz(pod_path)
    pod_path = join(pod_dir, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    if pod_m.shape[0] != len(npz_to_idx[0]):
        print("\t\t> ERROR: the npz matrix has shape[0]="+str(pod_m.shape[0])+" but npz_to_idx has length "+str(len(npz_to_idx[0])))


def check_pos_vs_npz_to_idx(pod):
    print("\t>> CHECKING POS VS NPZ_TO_IDX")
    pod_path = join(pod_dir, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    posindex = load_posix(pod)
    idx = []
    for token_id in posindex:
        for doc_id, _ in token_id.items():
            idx.append(doc_id)
    idx1 = list(set(idx))
    idx2 = npz_to_idx[1][1:] #Ignore first value, which is -1
    if set(idx2) != set(idx1):
        print("\t\t> ERROR: idx in npz_to_idx do not match doc list in positional index")
        print("\t\t> idx  :", set(idx1))
        print("\t\t> posix:", set(idx2))
    return set(idx1), set(idx2)


#####################
# BASIC REPAIR
#####################

@pears.cli.command('repair')
@click.argument('username')
def repair(username):
    print("\n>> CLI: REPAIR")
    pods = Pods.query.all()
    usernames = [p.name.split('.u.')[1] for p in pods]
    if username not in usernames:
        print("\t> ERROR: no username",username)
        return 0
    repair_duplicates_idx_to_url(username)
    repair_missing_docs_in_npz(username)
    repair_db_vs_idx_to_url(username)
    pods = Pods.query.all()
    pods = [p for p in pods if p.name.split('.u.')[1] == username]
    for pod in pods:
        print("\n>> CLI: REPAIR: ", pod.name)
        repair_duplicates_npz_to_idx(pod.name)
        repair_npz_to_idx_vs_idx_to_url(pod.name, username)
        repair_npz_vs_npz_to_idx(pod.name)
        repair_pos_vs_npz_to_idx(pod.name)


def repair_duplicates_idx_to_url(username):
    print("\t>> DELETE DUPLICATES IN IDX_TO_URL")
    pod_path = join(pod_dir, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    idx = idx_to_url[0]
    urls = idx_to_url[1]
    duplicate_urls = [k for k,v in Counter(urls).items() if v>1]
    for dup in duplicate_urls:
        while dup in urls:
            i = urls.index(dup)
            idx.pop(i)
            urls.pop(i)
    duplicate_idx = [k for k,v in Counter(idx).items() if v>1]
    for dup in duplicate_idx:
        while dup in idx: #several entries could have the same idx
            i = idx.index(dup)
            idx.pop(i)
            urls.pop(i)
    joblib.dump([idx,urls], pod_path)


def repair_missing_docs_in_npz(username):
    print("\t>> DELETE DOCS WITHOUT VECTORS FROM IDX_TO_URL")
    pod_path = join(pod_dir, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    idx = idx_to_url[0]
    urls = idx_to_url[1]
    diff = check_missing_docs_in_npz(username)
    for doc in diff:
        i = idx.index(doc)
        idx.pop(i)
        urls.pop(i)
    joblib.dump([idx,urls], pod_path)


def repair_db_vs_idx_to_url(username):
    print("\t>> DELETE DOCS IN DB WITHOUT AN IDX")
    diff = check_db_vs_idx_to_url(username)
    print(diff)
    for url in diff:
        u = db.session.query(Urls).filter_by(url=url).first()
        db.session.delete(u)
        db.session.commit()


def repair_duplicates_npz_to_idx(pod):
    print("\t>> DELETE DUPLICATES IN NPZ_TO_IDX")
    pod_path = join(pod_dir, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    npz = npz_to_idx[0]
    idx = npz_to_idx[1]
    duplicate_npz = [k for k,v in Counter(npz).items() if v>1]
    for dup in duplicate_npz:
        while dup in npz:
            i = npz.index(dup)
            npz.pop(i)
            idx.pop(i)
    duplicate_idx = [k for k,v in Counter(idx).items() if v>1]
    for dup in duplicate_idx:
        while dup in idx: #several entries could have the same idx
            i = idx.index(dup)
            npz.pop(i)
            idx.pop(i)
    joblib.dump([npz,idx], pod_path)


def repair_npz_to_idx_vs_idx_to_url(pod, username):
    print("\t>> DELETE NPZ_TO_IDX ENTRIES NOT IN IDX_TO_URL")
    pod_path = join(pod_dir, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    pod_path = join(pod_dir, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    idx1 = idx_to_url[0]
    idx2 = npz_to_idx[1][1:] #Ignore first value, which is -1
    idx = npz_to_idx[1]
    diff = list(set(idx2)-set(idx1))
    popped = []
    for d in diff:
        while d in idx:  #several entries could have the same idx
            i = idx.index(d)
            idx.pop(i)
            popped.append(i)
    if len(popped) > 0:
        print("\t   "+str(len(popped))+" entries popped. ("+' '.join([str(i) for i in popped])+')')
    npz = list(range(len(idx)))
    joblib.dump([npz, idx], pod_path)
    del_npz_rows(pod, popped)


def repair_npz_vs_npz_to_idx(pod):
    print("\t>> DELETE NPZ ENTRIES NOT IN NPZ_TO_IDX")
    pod_path = join(pod_dir, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    pod_path = join(pod_dir, pod+'.npz')
    pod_m = load_npz(pod_path)
    npz = npz_to_idx[0]
    pod_m = pod_m[:len(npz)]
    save_npz(pod_path, pod_m)

def repair_pos_vs_npz_to_idx(pod):
    idx1, idx2 = check_pos_vs_npz_to_idx(pod)
    if len(idx1) > len(idx2):
        orphans = list(idx1-idx2)
        del_pod_docs(pod, orphans)


def del_npz_rows(pod, todelete):
    print("\t>> DELETE NPZ ROWS", todelete)
    for i in todelete:
        rm_from_npz(i,pod)


def del_pod_docs(pod, todelete):
    print("\t>> DELETE POS DOCS", todelete)
    for i in todelete:
        rm_doc_from_pos(i,pod)


#####################
# SHOW INDEX FILES
#####################

@pears.cli.command('show')
@click.argument('username')
@click.argument('indexfile')
def showindexfile(username, indexfile):
    if indexfile == 'idx_to_url':
        print(">> CLI: SHOW: IDX TO URL: ")
        pod_path = join(pod_dir, username+'.idx')
        idx_to_url = joblib.load(pod_path)
        for i in range(len(idx_to_url[0])):
            print(idx_to_url[0][i], idx_to_url[1][i])

    if indexfile == 'npz_to_idx':
        pods = Pods.query.all()
        pods = [p for p in pods if p.name.split('.u.')[1] == username]
        for pod in pods:
            print("\n>> CLI: SHOW: NPZ TO IDX: ", pod.name)
            pod_path = join(pod_dir, pod.name+'.npz.idx')
            npz_to_idx = joblib.load(pod_path)
            for i in range(len(npz_to_idx[0])):
                print(npz_to_idx[0][i], npz_to_idx[1][i])

    if indexfile == 'posdocs':
        pods = Pods.query.all()
        pods = [p for p in pods if p.name.split('.u.')[1] == username]
        for pod in pods:
            print(">> CLI: SHOW: POS: ", pod.name)
            pod_path = join(pod_dir, pod.name+'.npz.idx')
            npz_to_idx = joblib.load(pod_path)
            posindex = load_posix(pod.name)
            for i in range(len(posindex)):
                token_id = posindex[i]
                if len(token_id) == 0:
                    continue
                idx = []
                for doc_id, _ in token_id.items():
                    idx.append(doc_id)
                print(str(i),':',idx)
