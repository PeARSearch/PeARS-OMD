# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import joblib
from shutil import copy2, copytree
from os.path import dirname, realpath, join
from datetime import datetime
from pathlib import Path
from random import shuffle
from flask import Blueprint
import click
from scipy.sparse import load_npz
from app import db, Urls, Pods
from app.indexer.posix import load_posix

pears = Blueprint('pears', __name__)

dir_path = dirname(dirname(dirname(realpath(__file__))))
pod_dir = join(dir_path,'app','static','pods')


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


def check_idx_to_url(username):
    print("\t>> CHECKING IDX_TO_URL")
    pod_path = join(pod_dir, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    if len(idx_to_url[0]) != len(idx_to_url[1]):
        print("\t\t> ERROR: the two lists in idx_to_url do not match in length", len(idx_to_url[0]), len(idx_to_url[1]))


def check_db_vs_idx_to_url(username):
    print("\t>> CHECKING DB VS IDX_TO_URL")
    urls = Urls.query.all()
    pod_path = join(pod_dir, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    if len(urls) != len(idx_to_url[0]):
        print("\t\t> ERROR: Length of URL list in DB != len(idx) in idx_to_url", len(urls), len(idx_to_url[0]))
    if len(urls) != len(idx_to_url[1]): 
        print("\t\t> ERROR: Length of URL list in DB != len(url) in idx_to_url", len(urls), len(idx_to_url[1]))


def check_duplicates_idx_to_url(username):
    print("\t>> CHECKING DUPLICATES IN IDX_TO_URL")
    pod_path = join(pod_dir, username+'.idx')
    idx_to_url = joblib.load(pod_path)
    if len(idx_to_url[1]) > len(list(set(idx_to_url[1]))):
        print("\t\t> ERROR: Duplicates in idx_to_url")


def check_npz_to_idx(pod):
    print("\t>> CHECKING NPZ_TO_IDX")
    pod_path = join(pod_dir, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    if len(npz_to_idx[0]) != len(npz_to_idx[1]):
        print("\t\t> ERROR: the two lists in npz_to_idx do not match in length", len(npz_to_idx[0]), len(npz_to_idx[1]))


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


def check_npz_vs_npz_to_idx(pod, username):
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
    check_duplicates_idx_to_url(username)
    check_db_vs_idx_to_url(username)
    print("\n")
    pods = [p for p in pods if p.name.split('.u.')[1] == username]
    for pod in pods:
        print(">> CLI: UNITTEST: CONSISTENCY: CHECKING POD:", pod.name)
        check_npz_to_idx(pod.name)
        check_npz_to_idx_vs_idx_to_url(pod.name, username)
        check_npz_vs_npz_to_idx(pod.name, username)
        check_pos_vs_npz_to_idx(pod.name)

        
@pears.cli.command('show')
@click.argument('username')
@click.argument('indexfile')
def showindexfile(username, indexfile):
    if indexfile == 'idx_to_url':
        pod_path = join(pod_dir, username+'.idx')
        idx_to_url = joblib.load(pod_path)
        for i in range(len(idx_to_url[0])):
            print(idx_to_url[0][i], idx_to_url[1][i])

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
