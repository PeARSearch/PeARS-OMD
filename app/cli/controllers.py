# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections import Counter
from shutil import copy2, copytree
from os.path import dirname, realpath, join
from datetime import datetime
from pathlib import Path
import joblib
from flask import Blueprint
import click
from scipy.sparse import load_npz, save_npz
from app import db, Urls, Pods
from app.indexer.posix import load_posix
from app.utils_db import rm_from_npz, rm_doc_from_pos

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
    bckpath = join(backupdir,'pears-'+date)
    Path(bckpath).mkdir(parents=True, exist_ok=True)
    #Copy database
    copy2(join(dir_path, 'app', 'db', 'app.db'), bckpath)
    #Copy pods folder
    copytree(pod_dir, join(bckpath,'pods'))

@pears.cli.command('deletedbonly')
def deletedbonly():
    pods = Pods.query.all()
    for pod in pods:
        urls = Urls.query.filter_by(pod=pod.name).all()
        for u in urls:
            db.session.delete(u)
            db.session.commit()

#####################
# QUERIES
#####################

@pears.cli.command('showurls')
@click.argument('username')
@click.argument('device')
@click.argument('lang')
def showurls(username, device, lang):
    from app.cli import dbquery
    dbquery.show_user_urls(username, device, lang)

@pears.cli.command('shownpz')
@click.argument('username')
@click.argument('device')
@click.argument('lang')
def shownpz(username, device, lang):
    pod_path = join(pod_dir, username, device, lang, 'private.npz')
    pod_m = load_npz(pod_path)
    print(f"LEN NPZ, {pod_m.shape[0]}")

@pears.cli.command('showallurls')
def showallurls():
    pods = Pods.query.all()
    for pod in pods:
        print('\n\n',pod.as_dict())
        urls = Urls.query.filter_by(pod=pod.url).all()
        for u in urls:
            print(u.id, u.url, u.pod)

#####################
# UNIT TESTS
#####################

@pears.cli.command('utsearch')
def run_unit_test_search_module():
    from app.cli import searchtests
    searchtests.test_compute_scores()


@pears.cli.command('consistency')
def checkconsistency():
    print("\n>> CLI: UNITTEST: CONSISTENCY CHECKS")
    pods = Pods.query.all()
    for pod in pods:
        print(">> CLI: UNITTEST: CONSISTENCY: CHECKING POD:", pod.name)
        check_db_vs_npz(pod)
        check_db_vs_pos(pod)

def check_db_vs_npz(pod):
    print(f"\t>> CHECKING DB VS NPZ FOR POD: {pod.name}")
    urls = Urls.query.filter_by(pod=pod.url).all()
    urls = [url.url for url in urls]
    npz_path = join(pod_dir, pod.url+'.npz')
    vectors = load_npz(npz_path)
    if len(set(urls)) + 1 != vectors.shape[0]:
        print("\t\t> ERROR: Length of URL set in DB != number of rows in npz matrix", len(urls), vectors.shape[0])
    return len(set(urls)), vectors.shape[0]

def check_db_vs_pos(pod):
    print(f"\t>> CHECKING DB VS POS FOR POD: {pod.name}")
    urls = Urls.query.filter_by(pod=pod.url).all()
    urls = [url.id for url in urls]
    posix_path = join(pod_dir, pod.url+'.pos')
    posindex = joblib.load(posix_path)
    unique_docs = []
    for token_id in posindex:
        for doc_id, _ in token_id.items():
            unique_docs.append(doc_id)
    unique_docs = list(set(unique_docs))
    db_docs_not_in_pos = []
    for i in urls:
        if i not in unique_docs:
            print(f"\t\t> ERROR: URL {i} is not in positional index.")
            db_docs_not_in_pos.append(i)
    return db_docs_not_in_pos




#####################
# BASIC REPAIR
#####################

@pears.cli.command('repair')
@click.argument('username')
def repair(username):
    print("\n>> CLI: REPAIR")
    pods = Pods.query.all()
    usernames = [p.name.split('/')[0] for p in pods]
    if username not in usernames:
        print("\t> ERROR: no username",username)
        return 0
    repair_missing_docs_in_npz(username)


def repair_missing_docs_in_npz(username):
    print("\t>> DELETE DOCS WITHOUT VECTORS FROM IDX_TO_URL")
    pod_path = join(pod_dir, username, 'user.idx')
    idx_to_url = joblib.load(pod_path)
    idx = idx_to_url[0]
    urls = idx_to_url[1]
    diff = check_missing_docs_in_npz(username)
    for doc in diff:
        i = idx.index(doc)
        idx.pop(i)
        urls.pop(i)
    joblib.dump([idx,urls], pod_path)


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
        pod_path = join(pod_dir, username, 'user.idx')
        idx_to_url = joblib.load(pod_path)
        for i in range(len(idx_to_url[0])):
            print(idx_to_url[0][i], idx_to_url[1][i])

    if indexfile == 'npz_to_idx':
        pods = Pods.query.all()
        pods = [p for p in pods if p.name.split('/')[0] == username]
        for pod in pods:
            print("\n>> CLI: SHOW: NPZ TO IDX: ", pod.name)
            pod_path = join(pod_dir, pod.name+'.npz.idx')
            npz_to_idx = joblib.load(pod_path)
            for i in range(len(npz_to_idx[0])):
                print(npz_to_idx[0][i], npz_to_idx[1][i])

    if indexfile == 'posdocs':
        pods = Pods.query.all()
        pods = [p for p in pods if p.name.split('/')[0] == username]
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
