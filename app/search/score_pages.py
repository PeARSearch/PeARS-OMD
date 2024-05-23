# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import dirname, join, realpath
import multiprocessing
import math
from glob import glob
from flask import session
import joblib
from joblib import Parallel, delayed
import numpy as np
from scipy.sparse import csr_matrix, load_npz
from scipy.spatial import distance
from app.api.models import Urls, Pods
from app import app, db, tracker
from app.search.overlap_calculation import generic_overlap, completeness, posix
from app.utils import cosine_similarity, hamming_similarity, convert_to_array, get_language, carbon_print
from app.indexer.mk_page_vector import compute_query_vectors

dir_path = dirname(dirname(realpath(__file__)))
pod_dir = join(dir_path,'pods')

def compute_scores(query, query_vector, tokenized, pod_name):
    """ Compute different scores for a query.
    """
    vec_scores = {}
    completeness_scores = {}
    posix_scores = {}
    try:
        pod_m = load_npz(join(pod_dir,pod_name+'.npz'))
    except:
        print(">> SEARCH: SCORE_PAGES: compute_scores: pod does not exist.")
        return {}, {}, {}
    m_cosines = 1 - distance.cdist(query_vector, pod_m.todense(), 'cosine')
    m_completeness = completeness(query_vector, pod_m.todense())
    try:
        posix_scores = posix(tokenized, pod_name)
    except:
        print(">> SEARCH: SCORE_PAGES: compute_scores: issue in posix computation.")

    #If no document were found through posix, just exit
    if len(posix_scores) == 0:
        return vec_scores, completeness_scores, posix_scores

    username = pod_name.split('.u.')[1]
    idx_to_url = joblib.load(join(pod_dir, username+'.idx'))
    npz_to_idx = joblib.load(join(pod_dir, pod_name+'.npz.idx'))
    for i in range(pod_m.shape[0]):
        cos =  m_cosines[0][i]
        if  cos == 0 or math.isnan(cos):
            continue
        #Get doc idx for row i of the matrix
        idx = npz_to_idx[1][i]
        #Get list position of doc idx in idx_to_url
        lspos = idx_to_url[0].index(idx)
        #Retrieve corresponding URL
        url = idx_to_url[1][lspos]
        vec_scores[url] = cos
        completeness_scores[url] = m_completeness[0][i]
    return vec_scores, completeness_scores, posix_scores


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
        userhome = 'home.'+lang+'.u.'+username
        npzs.append(join(pod_dir, userhome+'.npz'))
        pods.append(db.session.query(Pods).filter_by(name=userhome).first())
    npzs.extend(glob(join(pod_dir,'*.'+lang+'.shared.u.*npz')))
    for npz in npzs:
        podname = npz.split('/')[-1].replace('.npz','')
        s = np.sum(load_npz(npz).toarray(), axis=0)
        if np.sum(s) > 0:
            podsum.append(s)
            podnames.append(podname)
    podsum = csr_matrix(podsum)
    if np.sum(podsum) == 0:
        return best_pods

    m_cosines = 1 - distance.cdist(query_vector, podsum.todense(), 'cosine')

    # For each pod, retrieve cosine to query
    pods.extend(db.session.query(Pods).filter_by(language=lang).filter_by(registered=True).\
            filter(Pods.name.contains('.shared.u.')).all())
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
            return document_scores
        username = pod_name.split('.u.')[1]
        idx_to_url = joblib.load(join(pod_dir, username+'.idx'))
        #print("IDX TO URL",idx_to_url)
        for url in list(vec_scores.keys()):
            #print(">>>",url)
            #print(url, vec_scores[url], completeness_scores[url])
            i = idx_to_url[1].index(url)
            idx = idx_to_url[0][i]
            document_scores[url] = 0.0
            if idx in posix_scores:
                document_scores[url]+=posix_scores[idx]
            document_scores[url]+=completeness_scores[url]
            if math.isnan(document_scores[url]) or document_scores[url] < 1:
                document_scores[url] = 0
            else:
                u = db.session.query(Urls).filter_by(url=url).first()
                if u:
                    snippet_score = generic_overlap(query, u.snippet)
                    document_scores[url]+=snippet_score
                else:
                    print("ERROR: SEARCH: SCORE_PAGES: score_docs: could not find url in database")
                    print(url)
                #if idx in posix_scores:
                #    print(url, vec_scores[url], posix_scores[idx], document_scores[url], completeness_scores[url], snippet_score)
                #else:
                #    print(url, vec_scores[url], 0.0, document_scores[url], completeness_scores[url], snippet_score)
        return document_scores



def return_best_urls(doc_scores, url_filter):
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

    max_thread = int(multiprocessing.cpu_count() * 0.5)
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
