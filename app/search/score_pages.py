# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import dirname, join, realpath
import multiprocessing
import math
from glob import glob
from flask import session
from joblib import Parallel, delayed
import numpy as np
from scipy.sparse import csr_matrix, load_npz
from scipy.spatial import distance
from app.api.models import Urls, Pods
from app import db, tracker
from app.search.overlap_calculation import generic_overlap, completeness, posix
from app.utils import cosine_similarity, hamming_similarity, convert_to_array, get_language, carbon_print
from app.indexer.mk_page_vector import compute_query_vectors

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'static','pods')

def compute_scores(query, query_vector, tokenized, pod_name):
    """ Compute different scores for a query.
    """
    url_scores = {}
    snippet_scores = {}
    vec_scores = {}
    completeness_scores = {}
    pod_m = load_npz(join(pod_dir,pod_name+'.npz'))
    m_cosines = 1 - distance.cdist(query_vector, pod_m.todense(), 'cosine')
    m_completeness = completeness(query_vector, pod_m.todense())
    posix_scores = posix(tokenized, pod_name)

    for u in db.session.query(Urls).filter_by(pod=pod_name).all():
        vec_scores[u.url] = m_cosines[0][int(u.vector)]
        completeness_scores[u.url] = m_completeness[0][int(u.vector)]
        snippet_scores[u.url] = generic_overlap(query, u.snippet)
    return vec_scores, completeness_scores, snippet_scores, posix_scores


def score_pods(query, query_vector, lang, username = None):
    """Score pods for a query.
    We score pods that have shared content in them, since the user's pod
    itself should always be returned. We first compute cosine between the 
    query and each podsum vector, resulting in a matrix of cosines for 
    each computation. Then, we hit the database to attach a pod
    name to each score.
  
    Parameters:
    query_vector: the numpy array for the query (dim = size of vocab)
    extended_q_vectors: a list of numpy arrays for the extended query
    lang: the language of the query
  
    Returns: a list of the best <max_pods: int> pods, or if all scores
    are under a certain threshold, the list of all pods.
    """
    print(">> SEARCH: SCORE PAGES: SCORE PODS")

    max_pods = 3 # How many pods to return
    pod_scores = {}
    
    best_pods = []
    if username is not None:
        best_pods.append('home.u.'+username)

    # Compute similarity of query to all pods
    podnames = []
    podsum = []
    npzs = glob(join(pod_dir,'*.shared.u.*npz'))
    if len(npzs) == 0:
        return best_pods
    for npz in npzs:
        podname = npz.split('/')[-1].replace('.npz','')
        s = np.sum(load_npz(npz).toarray(), axis=0)
        if np.sum(s) > 0:
            podsum.append(s)
            podnames.append(podname)
    podsum = csr_matrix(podsum)

    m_cosines = 1 - distance.cdist(query_vector, podsum.todense(), 'cosine')
    print(podnames)
    print(m_cosines)

    # For each pod, retrieve cosine to query
    pods = db.session.query(Pods).filter_by(language=lang).filter_by(registered=True).\
            filter(Pods.name.contains('.shared.u.')).all()
    for p in pods:
        if p.name in podnames:
            cosine_score = m_cosines[0][podnames.index(p.name)]
            print(">> Exact matches:", p.name, cosine_score)
            if math.isnan(cosine_score):
                cosine_score = 0
            pod_scores[p.name] = cosine_score
    print("POD SCORES:",pod_scores)
    for k in sorted(pod_scores, key=pod_scores.get, reverse=True):
        if len(best_pods) < max_pods + 1:
            print("Appending pod",k)
            best_pods.append(k)
        else:
            break
    return best_pods


def score_docs(query, query_vector, tokenized, pod_name):
    '''Score documents for a query'''
    document_scores = {}  # Document scores
    vec_scores, completeness_scores, snippet_scores, posix_scores = \
            compute_scores(query, query_vector, tokenized, pod_name)
    print("POSIX SCORES",posix_scores)
    for url in list(vec_scores.keys()):
        document_scores[url] = 0.0
        idx = db.session.query(Urls).filter_by(url=url).first().vector
        if idx in posix_scores:
            document_scores[url]+=posix_scores[idx]
        document_scores[url]+=completeness_scores[url]
        document_scores[url]+=snippet_scores[url]
        if snippet_scores[url] == 1:
            document_scores[url]+=1 #bonus points
        if math.isnan(document_scores[url]) or completeness_scores[url] < 0.3:
            document_scores[url] = 0
        else:
            print(url, document_scores[url], completeness_scores[url], snippet_scores[url])
    return document_scores



def return_best_urls(doc_scores, url_filter):
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
            pod = url.pod
            if pod not in pods:
                pods.append(pod)
    return results, pods


def run(query, url_filter=None):
    if tracker is not None:
        task_name = "run search"
        tracker.start_task(task_name)
    if 'username' in session:
        username = session['username']
    else:
        username = None
    document_scores = {}
    query, lang = get_language(query)
    q_dist, tokenized = compute_query_vectors(query, lang)
    best_pods = score_pods(query, q_dist, lang, username)
    print("Q:",query,"BEST PODS:",best_pods)

    max_thread = int(multiprocessing.cpu_count() * 0.5)
    with Parallel(n_jobs=max_thread, prefer="threads") as parallel:
        delayed_funcs = [delayed(score_docs)(query, q_dist, tokenized, pod) for pod in best_pods]
        scores = parallel(delayed_funcs)
    for dic in scores:
        document_scores.update(dic)
    best_urls = return_best_urls(document_scores, url_filter)
    results = output(best_urls)
    if tracker is not None:
        search_emissions = tracker.stop_task()
        carbon_print(search_emissions, task_name)
    return results
