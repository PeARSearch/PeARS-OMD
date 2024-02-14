# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import multiprocessing
from joblib import Parallel, delayed
from urllib.parse import urlparse
import re
import math
from app.api.models import Urls, Pods
from app import db, tracker
from app.utils_db import (
    get_db_url_snippet, get_db_url_title, get_db_url_cc, get_db_url_pod, get_db_url_notes)

from .overlap_calculation import score_url_overlap, generic_overlap, completeness, posix
from app.search import term_cosine
from app.utils import cosine_similarity, hamming_similarity, convert_to_array, get_language, carbon_print
from app.indexer.mk_page_vector import compute_query_vectors
from scipy.sparse import csr_matrix, load_npz
from scipy.spatial import distance
from os.path import dirname, join, realpath, isfile
import numpy as np

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'static','pods')

def score(query, query_dist, tokenized, kwd):
    URL_scores = {}
    snippet_scores = {}
    DS_scores = {}
    completeness_scores = {}
    pod_m = load_npz(join(pod_dir,kwd+'.npz'))
    m_cosines = 1 - distance.cdist(query_dist, pod_m.todense(), 'cosine')
    m_completeness = completeness(query_dist, pod_m.todense())
    posix_scores = posix(tokenized, kwd)

    for u in db.session.query(Urls).filter_by(pod=kwd).all():
        DS_scores[u.url] = m_cosines[0][int(u.vector)]
        completeness_scores[u.url] = m_completeness[0][int(u.vector)]
        snippet_scores[u.url] = generic_overlap(query, u.snippet)
    return DS_scores, completeness_scores, snippet_scores, posix_scores


def score_pods(query, query_dist, lang):
    '''Score pods for a query'''
    pod_scores = {}
    score_sum = 0.0
    podsum = load_npz(join(pod_dir,'podsum.npz'))
    print("DEBUG CDIST:",query_dist.shape, podsum.shape)
    m_cosines = 1 - distance.cdist(query_dist, podsum.todense(), 'cosine')

    pods = db.session.query(Pods).filter_by(language=lang).filter_by(registered=True).all()
    for p in pods:
        score = m_cosines[0][int(p.DS_vector)]
        if math.isnan(score):
            score = 0
        pod_scores[p.name] = score
        score_sum += score
    print("POD SCORES:",pod_scores)
    '''If all scores are rubbish, search entire pod collection
    (we're desperate!)'''
    if score_sum < 0.9: #FIX FOR FRUIT FLY VERSION
        return list(pod_scores.keys())
    else:
        best_pods = []
        for k in sorted(pod_scores, key=pod_scores.get, reverse=True):
            if len(best_pods) < 5: 
                print("Appending pod",k)
                best_pods.append(k)
            else:
                break
        return best_pods


def score_docs(query, query_dist, tokenized, kwd):
    '''Score documents for a query'''
    document_scores = {}  # Document scores
    DS_scores, completeness_scores, snippet_scores, posix_scores = score(query, query_dist, tokenized, kwd)
    print("POSIX SCORES",posix_scores)
    for url in list(DS_scores.keys()):
        document_scores[url] = 0.0
        idx = db.session.query(Urls).filter_by(url=url).first().vector
        if idx in posix_scores:
            document_scores[url]+=posix_scores[idx]
        document_scores[url]+=completeness_scores[url]
        document_scores[url]+=snippet_scores[url]
        if snippet_scores[url] == 1:
            document_scores[url]+=1 #bonus points
        if math.isnan(document_scores[url]) or completeness_scores[url] < 0.3:  # Check for potential NaN -- messes up with sorting in bestURLs.
            document_scores[url] = 0
        else:
            print(url, document_scores[url], completeness_scores[url], snippet_scores[url])
    return document_scores



def bestURLs(doc_scores, url_filter):
    best_urls = []
    c = 0
    for url in sorted(doc_scores, key=doc_scores.get, reverse=True):
        if c < 20:
            if doc_scores[url] > 0:
                for f in url_filter:
                    if f in url:
                        best_urls.append(url)
                        c += 1
            else:
                break
        else:
            break
    return best_urls


def output(best_urls):
    print(best_urls)
    results = {}
    pods = []
    if len(best_urls) > 0:
        for u in best_urls:
            url = db.session.query(Urls).filter_by(url=u).first().as_dict()
            results[u] = url
            pod = get_db_url_pod(u)
            if pod not in pods:
                pods.append(pod)
    return results, pods


def run(query, pears, url_filter=None):
    if tracker != None:
        task_name = "run search"
        tracker.start_task(task_name)
    
    
    document_scores = {}
    query, lang = get_language(query)
    q_dist, tokenized = compute_query_vectors(query, lang)
    best_pods = score_pods(query, q_dist, lang)
    print("Q:",query,"BEST PODS:",best_pods)

    max_thread = int(multiprocessing.cpu_count() * 0.5)
    with Parallel(n_jobs=max_thread, prefer="threads") as parallel:
        delayed_funcs = [delayed(score_docs)(query, q_dist, tokenized, pod) for pod in best_pods]
        scores = parallel(delayed_funcs)
    for dic in scores:
        document_scores.update(dic)
    best_urls = bestURLs(document_scores, url_filter)
    results = output(best_urls)
    if tracker != None:
        search_emissions = tracker.stop_task()
        carbon_print(search_emissions, task_name)
    return results
