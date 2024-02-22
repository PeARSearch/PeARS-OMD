# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import joblib
from app import db, vocab, VEC_SIZE
from app.api.models import Urls, Pods
from app.api.models import installed_languages
from app.indexer.posix import load_posix, dump_posix
from app.utils import convert_to_array, convert_string_to_dict, convert_to_string, normalise
import numpy as np
from os.path import dirname, realpath, join
from scipy.sparse import csr_matrix, vstack, save_npz, load_npz

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'app','static','pods')

def delete_url(idx, pod):
    u = db.session.query(Urls).filter_by(pod=pod).filter_by(vector=idx).first()
    vid = int(u.vector)
    #Remove document row from .npz matrix
    pod_m = load_npz(join(pod_dir,pod+'.npz'))
    m1 = pod_m[:vid]
    m2 = pod_m[vid+1:]
    pod_m = vstack((m1,m2))
    save_npz(join(pod_dir,pod+'.npz'),pod_m)

    #Correct indices in DB
    urls = db.session.query(Urls).filter_by(pod=pod).all()
    for url in urls:
        if int(url.vector) > vid:
            url.vector = str(int(url.vector)-1) #Decrease ID now that matrix row has gone
        db.session.add(url)
        db.session.commit()

    #Remove doc from positional index
    posindex = load_posix(pod)
    new_posindex = []
    for token in vocab:
        token_id = vocab[token]
        tmp = {}
        for doc_id, posidx in posindex[token_id].items():
            if doc_id != str(vid):
                tmp[doc_id] = posidx
            #else:
            #    print("Deleting doc",doc_id,"from token",token,token_id)
        new_posindex.append(tmp)
    dump_posix(new_posindex,pod)

    #Delete from database
    db.session.delete(u)
    db.session.commit()
    return "Deleted document with vector id"+str(vid)



def compute_pod_summary(name):
    '''This function is very similar to 'self' in PeARS-pod'''
    DS_vector = np.zeros(VEC_SIZE) 
    for u in db.session.query(Urls).filter_by(pod=name).all():
        DS_vector += convert_to_array(u.vector)
    DS_vector = convert_to_string(normalise(DS_vector))
    c = 0
    return DS_vector


def url_from_json(url, pod):
    # print(url)
    if not db.session.query(Urls).filter_by(url=url['url']).all():
        u = Urls(url=url['url'])
        u.url = url['url']
        u.title = url['title']
        u.vector = url['vector']
        u.freqs = url['freqs']
        u.snippet = url['snippet']
        u.pod = pod
        if url['cc']:
            u.cc = True
        db.session.add(u)
        db.session.commit()


def pod_from_json(pod, url):
    if not db.session.query(Pods).filter_by(url=url).all():
        p = Pods(url=url)
        db.session.add(p)
        db.session.commit()
    p = Pods.query.filter(Pods.url == url).first()
    p.name = pod['name']
    p.description = pod['description']
    p.language = pod['language']
    p.DS_vector = pod['DSvector']
    p.word_vector = pod['wordvector']
    if not p.registered:
        p.registered = False
    db.session.commit()

def create_pod_in_db(contributor, lang):
    '''If the pod does not exist, create it in the database.'''

    def commit(url, name):
        if not db.session.query(Pods).filter_by(url=url).all():
            p = Pods(url=url)
            p.name = name
            p.description = name
            p.language = lang
            p.registered = True
            db.session.add(p)
            db.session.commit()

    name_personal = 'home.u.'+contributor
    name_shared = 'home.shared.u.'+contributor
    url_personal = "http://localhost:8080/api/pods/" + name_personal.replace(' ', '+')
    url_shared = "http://localhost:8080/api/pods/" + name_shared.replace(' ', '+')
    commit(url_personal, name_personal)
    commit(url_shared, name_shared)
