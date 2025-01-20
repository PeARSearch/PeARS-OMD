# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import dirname, join, realpath
import multiprocessing
import math
import hashlib
from glob import glob
from flask import session
import joblib
from joblib import Parallel, delayed
import numpy as np
from scipy.sparse import csr_matrix, load_npz
from scipy.spatial import distance
from app.api.models import Urls, Pods, Groups, Sites
from app import app, db, tracker
from app.utils import get_language, carbon_print, hash_username
from app.indexer.mk_page_vector import compute_query_vectors
from app.search.overlap_calculation import generic_overlap, completeness, posix

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'pods')

def compute_scores(query, query_vector, tokenized, pod_name):
    """ Compute different scores for a query.
    """
    vec_scores = {}
    completeness_scores = {}
    posix_scores = {}

    # Compute cosines and completeness using npz file
    try:
        pod_m = load_npz(join(pod_dir,pod_name+'.npz'))
    except:
        print(">> SEARCH: SCORE_PAGES: compute_scores: pod does not exist.")
        return vec_scores, completeness_scores, posix_scores
    m_cosines = 1 - distance.cdist(query_vector, pod_m.todense(), 'cosine')
    m_completeness = completeness(query_vector, pod_m.todense())

    # Compute posix scores
    try:
        posix_scores = posix(tokenized, pod_name)
    except:
        print(">> SEARCH: SCORE_PAGES: compute_scores: issue in posix computation.")

    #If no document were found through posix, just exit
    if len(posix_scores) == 0:
        print(">> SEARCH: SCORE_PAGES: compute_scores: no documents found via posix.")
        return vec_scores, completeness_scores, posix_scores

    #try:
    for i in range(pod_m.shape[0]):
        cos =  m_cosines[0][i]
        if  cos == 0 or math.isnan(cos):
            continue
        #Get doc idx for row i of the matrix
        #Retrieve corresponding URL
        #print(f"Looking for vector {i} on {pod_name}")
        url = Urls.query.filter_by(pod=pod_name).filter_by(vector=i).first().url
        #print(url)
        vec_scores[url] = cos
        completeness_scores[url] = m_completeness[0][i]
    #except:
    #    print(">> SEARCH: SCORE_PAGES: compute_scores: possible consistency issue")
    #    return vec_scores, completeness_scores, posix_scores
    return vec_scores, completeness_scores, posix_scores


def get_user_pods(username, lang):
    '''Return user's own pods'''
    npzs = []
    pods = []
    owner_hash = hash_username(username)
    private_folders = Pods.query.filter(Pods.url.startswith(f"{owner_hash}/")).filter(Pods.url.endswith(f"/{lang}/user")).all()
    for pf in private_folders:
        npzs.append(join(pod_dir, pf.url+'.npz'))
        pods.append(pf)
    return npzs, pods


def get_group_pods(username, lang):
    '''Return pods for groups the user belongs to'''
    npzs = []
    pods = []
    user_groups = Groups.query.all()
    group_folders = []
    #print("USER GROUPS",[group.identifier for group in user_groups])
    for g in user_groups:
        members = [m.strip() for m in g.name.split(',')]
        if username in members:
            group = Pods.query.filter(Pods.url.startswith(f"{g.identifier}/")).filter(Pods.url.endswith(f"/{lang}/group")).all()
            group_folders.extend(group)
    print("GROUP FOLDERS", [group.url for group in group_folders])
    for gf in group_folders:
        npzs.append(join(pod_dir, gf.url+'.npz'))
        pods.append(gf)
    return npzs, pods


def get_site_pods(lang):
    '''LEGACY Return pods for sites.
    NB: sites cannot have the name of a device on the OMD network
    '''
    npzs = []
    pods = []
    sites = Sites.query.all()
    site_names = [s.name for s in sites]
    pods_in_db = Pods.query.all()
    for pod in pods_in_db:
        location = pod.url.split('/')[1]
        if location in site_names:
            pods.append(pod)
            npzs.append(join(pod_dir, pod.url+'.npz'))
    return npzs, pods


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

    # Compute similarity of query to all pods
    podnames = []
    pods = []
    podsum = []
    npzs = []
    if username is not None:
        #Get user pods
        user_npzs, user_pods = get_user_pods(username, lang)
        npzs.extend(user_npzs)
        pods.extend(user_pods)
        #Get group pods
        group_npzs, group_pods = get_group_pods(username, lang)
        npzs.extend(group_npzs)
        pods.extend(group_pods)
    #Get public files
    npzs.extend(glob(join(pod_dir, f"*/*/{lang}/others.npz")))
    npzs.extend(glob(join(pod_dir, f"*/*/{lang}/sites.npz")))
    pods.extend(db.session.query(Pods).filter_by(language=lang).filter(Pods.url.endswith('/others')).all())
    pods.extend(db.session.query(Pods).filter_by(language=lang).filter(Pods.url.endswith('/sites')).all())
    for npz in npzs:
        podname = npz.replace(pod_dir + "/", "").replace(".npz", "")
        s = np.sum(load_npz(npz).toarray(), axis=0)
        if np.sum(s) > 0:
            podsum.append(s)
            podnames.append(podname)
    podsum = csr_matrix(podsum)
    if np.sum(podsum) == 0:
        return best_pods

    m_cosines = 1 - distance.cdist(query_vector, podsum.todense(), 'cosine')

    # For each pod, retrieve cosine to query
    for p in pods:
        if p.url in podnames:
            cosine_score = m_cosines[0][podnames.index(p.url)]
            print(">> Exact matches:", p.url, cosine_score)
            if math.isnan(cosine_score):
                cosine_score = 0
            pod_scores[p.url] = cosine_score
    print("POD SCORES:",pod_scores)
    for k in sorted(pod_scores, key=pod_scores.get, reverse=True):
        if len(best_pods) < max_pods + 1:
            if pod_scores[k] > 0:
                print("Appending pod",k)
                best_pods.append(k)
        else:
            break
    return best_pods


def score_docs(query, query_vector, tokenized, pod_name):
    '''Score documents for a query'''
    with app.app_context():
        print("\nSEARCH: SCORE_PAGES: score_docs: scoring on", pod_name)
        document_scores = {}  # Document scores
        vec_scores, completeness_scores, posix_scores = \
                compute_scores(query, query_vector, tokenized, pod_name)
        if len(vec_scores) == 0:
            print(">> SEARCH: SCORE_PAGES: score_docs: vec_scores is empty.")
            return document_scores
        for url in list(vec_scores.keys()):
            #print(">>>",url)
            #print(url, vec_scores[url], completeness_scores[url])
            try:
                idx = -1
                u = Urls.query.filter_by(url=url).first()
                if u:
                    idx = u.id
                else:
                    print("ERROR: SEARCH: SCORE_PAGES: score_docs: could not find url in database")
                    print(url)
                document_scores[url] = 0.0
                if idx in posix_scores:
                    document_scores[url]+=posix_scores[idx]
                document_scores[url]+=completeness_scores[url]
                if math.isnan(document_scores[url]) or document_scores[url] < 1:
                    document_scores[url] = 0
                snippet_score = generic_overlap(query, u.snippet)
                document_scores[url]+=snippet_score
                if idx in posix_scores:
                    print(url, vec_scores[url], posix_scores[idx], document_scores[url], completeness_scores[url], snippet_score)
                else:
                    print(url, vec_scores[url], 0.0, document_scores[url], completeness_scores[url], snippet_score)
            except:
                continue
        return document_scores



def return_best_urls(doc_scores, url_filter):
    print(doc_scores)
    best_urls = []
    scores = []
    c = 0
    for url in sorted(doc_scores, key=doc_scores.get, reverse=True):
        if c < 20:
            if doc_scores[url] > 0:
                for f in url_filter:
                    if f in url:
                        best_urls.append(url)
                        scores.append(doc_scores[url])
                        c += 1
            else:
                break
        else:
            break
    return best_urls, scores


def output(best_urls):
    #print(best_urls)
    results = {}
    for i in range(len(best_urls)):
        u = best_urls[i]
        try:
            url = db.session.query(Urls).filter_by(url=u).first().as_dict()
        except:
            url = None
            print("ERROR: SEARCH: SCORE_PAGES: output: could not find url in database")
        results[u] = url
    return results


def run_search(query, url_filter=None):
    if tracker is not None:
        task_name = "run search"
        tracker.start_task(task_name)
    if 'username' in session:
        username = session['username']
    else:
        username = None
    document_scores = {}
    query, lang = get_language(query)
    print("Query/language:",query,lang)
    q_vector, tokenized = compute_query_vectors(query, lang)
    best_pods = score_pods(query, q_vector, lang, username)
    print("\tQ:",query,"BEST PODS:",best_pods)

    #max_thread = int(multiprocessing.cpu_count() * 0.5)
    max_thread = 1
    with Parallel(n_jobs=max_thread, prefer="threads") as parallel:
        delayed_funcs = [delayed(score_docs)(query, q_vector, tokenized, pod) for pod in best_pods]
        scores = parallel(delayed_funcs)
    for dic in scores:
        document_scores.update(dic)
    best_urls, scores = return_best_urls(document_scores, url_filter)
    #print("UNIT TEST: LEN BEST URLS", len(best_urls), "LEN SCORES", len(scores))
    results = output(best_urls)
    #print("UNIT TEST: LEN BEST URLS", len(best_urls), "LEN SCORES", len(scores), "LEN RESULTS", len(results))
    if tracker is not None:
        search_emissions = tracker.stop_task()
        carbon_print(search_emissions, task_name)
    return results, scores
