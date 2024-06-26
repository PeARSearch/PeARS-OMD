# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os.path import join
import re
from datetime import datetime
from math import sqrt
import requests
import numpy as np
from scipy.spatial import distance
from app import LANGS, CARBON_DIR



def carbon_print(tracker_results, task_name):
    date = datetime.today().strftime('%Y-%m-%d')
    filename = 'carbon.'+date+'.txt'
    with open(join(CARBON_DIR,filename),'a', encoding="utf-8") as f:
        f.write(task_name+': '+str(tracker_results)+'\n')


def read_urls(url_file):
    with open(url_file, 'r', encoding="utf-8") as fd:
        urls = fd.read().splitlines()
    return urls


def read_docs(doc_file):
    """ Function to read the pre-processed documents, as obtained
    from crawling the OMD xml files.
    Argument: the path to the document file.
    Returns: paths, titles, snippets, descriptions and full bodies
    of documents in the input file.
    """

    # Initializations
    url = ""
    title = ""
    snippet = ""
    description = ""
    language = LANGS[0]

    urls = []
    titles = []
    snippets = []
    docs = []
    descriptions = []
    languages = []

    with open(doc_file, 'r', encoding="utf-8") as df:
        description = ""
        doc = ""
        for l in df:
            l=l.rstrip('\n')
            if l[:4] == "<doc":
                m = re.search('url=\'([^\']*)\'',l)
                url = m.group(1)
                m = re.search('title=\'([^\']*)\'',l)
                title = m.group(1)
                m = re.search('lang=\'([^\']*)\'',l)
                language = m.group(1)
            elif "</doc" not in l:
                if "{{DESCRIPTION}}" in l:
                    description = l.replace("{{DESCRIPTION}} ","")
                    logging.debug("DOC WITH DESCRIPTION: {description}")
                elif "{{BODY}}" in l:
                    l = l.replace("{{BODY}} ","")
                    doc+=l+' '
                else:
                    doc+=l+' '
            else:
                if url != "":
                    snippet = doc[:200]
                    urls.append(url)
                    titles.append(title)
                    snippets.append(snippet)
                    descriptions.append(description)
                    languages.append(language)
                    docs.append(description+' '+doc)
                    description = ""
                    url = ""
                    title = ""
                    snippet = ""
                    doc = ""
                    language = LANGS[0]
    return urls, titles, snippets, descriptions, languages, docs


def normalise(v):
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


def convert_to_string(vector):
    s = ' '.join(str(i) for i in vector)
    return(s)


def convert_to_array(vector):
    # for i in vector.rstrip(' ').split(' '):
    #    print('#',i,float(i))
    return np.array([float(i) for i in vector.split()])


def convert_dict_to_string(dic):
    s = ""
    for k, v in dic.items():
        s += k + ':' + str(v) + ' '
    return s


def convert_string_to_dict(s):
    d = {}
    els = s.rstrip(' ').split()
    for e in els:
        if ':' in e:
            pair = e.split(':')
            if pair[0] != "" and pair[1] != "":
                d[pair[0]] = pair[1]
    return d


def cosine_similarity(v1, v2):
    if len(v1) != len(v2):
        return 0.0
    num = np.dot(v1, v2)
    den_a = np.dot(v1, v1)
    den_b = np.dot(v2, v2)
    return num / (sqrt(den_a) * sqrt(den_b))


def hamming_similarity(v1, v2):
    return 1 - distance.hamming(v1,v2)


def cosine_to_matrix(q, M):
    qsqrt = sqrt(np.dot(q, q))
    if qsqrt == 0:
        return np.zeros(M.shape[0])
    qMdot = np.dot(q, M.T)
    Mdot = np.dot(M, M.T)
    Msqrts = [sqrt(Mdot[i][i]) for i in range(len(Mdot[0]))]
    cosines = []
    for i in range(len(Mdot[0])):
        if Msqrts[i] != 0:
            cosines.append(qMdot[i] / (qsqrt * Msqrts[i]))
        else:
            cosines.append(0)
    return cosines


def sim_to_matrix(dm_dict, vec, n):
    cosines = {}
    c = 0
    for k, v in dm_dict.items():
        try:
            cos = cosine_similarity(vec, v)
            cosines[k] = cos
            c += 1
        except Exception:
            pass
    c = 0
    neighbours = []
    for t in sorted(cosines, key=cosines.get, reverse=True):
        if c < n:
            if t.isalpha():
                print(t, cosines[t])
                neighbours.append(t)
                c += 1
        else:
            break
    return neighbours


def sim_to_matrix_url(url_dict, vec, n):
    cosines = {}
    for k, v in url_dict.items():
        try:
            cos = cosine_similarity(vec, v.vector)
            cosines[k] = cos
        except Exception:
            pass
    c = 0
    neighbours = []
    for t in sorted(cosines, key=cosines.get, reverse=True):
        if c < n:
            # print(t,cosines[t])
            neighbour = [t, url_dict[t].title, url_dict[t].snippet]
            neighbours.append(neighbour)
            c += 1
        else:
            break
    return neighbours


def get_pod_info(url):
    print("Fetching pod", join(url, "api/self/"))
    pod = None
    try:
        r = requests.get(join(url, "api/self/"))
        if r.status_code == 200:
            pod = r.json()
    except Exception:
        print("Problem fetching pod...")
    return pod


def get_language(query):
    lang = None
    m = re.search('(.*) -(..\s*)$',query)
    if m:
        print(m.group(1), m.group(2))
        query = m.group(1)
        lang = m.group(2)
        if lang not in LANGS:
            lang = None
    return query, lang

def beautify_title(title, doctype):
    title = title[:70]
    if doctype == 'stat':
        title = '📈 '+title
    if doctype == 'doc':
        title = '📝 '+title
    if doctype == 'url':
        title = '🌏 '+title
    if doctype == 'ind':
        title = '☺️  '+title
    if doctype == 'map':
        title = '📍 '+title
    return title

def beautify_snippet(snippet, query):
    if snippet == '':
        return snippet
    tmp_snippet = snippet
    for w in query.split():
        tmp_snippet = tmp_snippet.replace(w,'<b>'+w+'</b>')
        tmp_snippet = tmp_snippet.replace(w.title(),'<b>'+w.title()+'</b>')
    return tmp_snippet
