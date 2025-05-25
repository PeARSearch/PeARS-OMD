# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections import Counter
from shutil import copy2, copytree, rmtree
from os.path import dirname, realpath, join, exists
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
def backup():
    '''Backup database and pods to .backups directory'''
    backupdir = join(dir_path, '.backups')
    Path(backupdir).mkdir(parents=True, exist_ok=True)
    #Get today's date
    date = datetime.now().strftime('%Y-%m-%d-%Hh%Mm')
    bckpath = join(backupdir,'pears-'+date)
    Path(bckpath).mkdir(parents=True, exist_ok=True)
    #Copy database
    copy2(join(dir_path, 'app', 'db', 'app.db'), bckpath)
    #Copy pods folder
    copytree(pod_dir, join(bckpath,'pods'))

@pears.cli.command('restore')
@click.argument('snapshot')
def restore(snapshot):
    '''Restore particular snapshot from backups'''
    confirm = input(f"\nWARNING: this will override your current database with snapshot {snapshot}. Do you want to continue? (y/n): ")
    if confirm == 'y':
        #Copy database
        bck_db = join(dir_path, '.backups', snapshot, 'app.db')
        copy2(bck_db, join(dir_path, 'app', 'db', 'app.db'))
        #Copy pods folder
        bck_pods = join(dir_path, '.backups', snapshot, 'pods')
        if exists(pod_dir):
            rmtree(pod_dir)
        copytree(bck_pods, pod_dir)


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
            print(u.id, u.vector, u.url, u.pod)

#####################
# CONSISTENCY CHECKS
#####################

@pears.cli.command('consistency')
def checkconsistency():
    print("\n>> CLI: UNITTEST: CONSISTENCY CHECKS")
    from app.cli.consistency import check_db_vs_npz, check_db_vs_pos
    pods = Pods.query.all()
    for pod in pods:
        print(">> CLI: UNITTEST: CONSISTENCY: CHECKING POD:", pod.name)
        check_db_vs_npz(pod)
        check_db_vs_pos(pod)

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

def del_npz_rows(pod, todelete):
    print("\t>> DELETE NPZ ROWS", todelete)
    for i in todelete:
        rm_from_npz(i,pod)


def del_pod_docs(pod, todelete):
    print("\t>> DELETE POS DOCS", todelete)
    for i in todelete:
        rm_doc_from_pos(i,pod)


