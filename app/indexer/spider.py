# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import join, dirname, realpath
from flask import session, url_for
import xmltodict
import requests
from app.indexer.htmlparser import extract_txt
from app import OMD_PATH, LOCAL_RUN, AUTH_TOKEN

app_dir_path = dirname(dirname(realpath(__file__)))
user_app_dir_path = join(app_dir_path,'static', 'userdata')

def omd_parse(current_url, username):
    """ This function parses a url and writes the text content
    to the user's corpus file.
    Arguments: the url path and a username.
    """
    print("\n\nRunning OMD parse on", current_url)
    links = []
    fout = open(join(user_app_dir_path, username+'.corpus'),'a', encoding='utf-8')
    try:
        xml = requests.get(current_url, timeout=10, \
                headers={'Authorization': AUTH_TOKEN}, stream =True).raw
    except RuntimeError as error:
        print(">> ERROR: SPIDER: OMD PARSE: Request failed. Moving on.")
        print(error)
        return links
    print(xml.read())
    xml = requests.get(current_url, timeout=10, \
            headers={'Authorization': AUTH_TOKEN}, stream =True).raw
    try:
        parse = xmltodict.parse(xml.read())
    except RuntimeError as error:
        print(">> ERROR: SPIDER: OMD PARSE: File may have some bad XML. Could not parse.")
        print(error)
        return links
    docs = parse['omd_index']['doc']
    if not isinstance(docs, list):
        docs = [docs]
    for doc in docs:
        urldir = '/'.join(current_url.split('/')[:-1])

        # URL
        if doc['@url'][0] == '/':
            url = doc['@url'][1:]
        else:
            url = doc['@url']
        print(">> INDEXER: SPIDER: omd_parse: doc url:", url)
        if url.startswith('shared/'):
            url = join(OMD_PATH, url)
        else:
            url = join(urldir, url)
        print(">> INDEXER: SPIDER: omd_parse: doc url:", url)
        if LOCAL_RUN:
            if url[-1] == '/': #For local test only
                url = join(url,'index.html')

        # CONTENT TYPE
        try:
            print("# DOC CONTENTTYPE: ", doc['@contentType'])
            content_type = doc['@contentType']
            if content_type in ['folder','desktop']:
                if join(OMD_PATH,'shared') not in url:
                    links.append(url)
        except RuntimeError as error:
            print(">> SPIDER: OMD_PARSE: DOC CONTENTTYPE: No contentType")
            print(error)

        # TITLE
        try:
            print("# DOC TITLE:", doc['title'])
            title = doc['title']
        except RuntimeError as error:
            print(">> SPIDER: OMD_PARSE: DOC TITLE: No title")
            print(error)
        if title is None:
            title = ''

        # DESCRIPTION
        description = None
        try:
            #print("# DOC DESCRIPTION:", doc['description'][:100])
            description = title + ' ' + doc['description']
            #print("\t"+description+"\n")
        except:
            print("# DOC DESCRIPTION: No description")

        # CONTENT, ONLY DOCS (NOT FOLDERS)
        if content_type == 'text/plain':
            title, body_str, _, language = extract_txt(url)
            print("# DOC BODY:", body_str[:100])
            fout.write("<doc title='"+title+"' url='"+url+"' lang='"+language+"'>\n")
            if description:
                fout.write("{{DESCRIPTION}} "+description+"\n")
            fout.write("{{BODY}} "+body_str+"\n")
        else:
            print(">> ERROR: SPIDER: OMD PARSE: DOC BODY: Skipping request: \
                    content is neither text/plain nor text/html.")

        fout.write("</doc>\n")
    fout.close()

    print("\n NEW LINKS:",links)
    return links

def write_docs(base_url, username):
    """Write document corpus while crawling.
    Argument: base url, to start the crawl from.
    """
    if base_url is None:
        print("No url passed.")
        return url_for('indexer')

    pages_to_visit = [base_url]
    pages_visited = []
    corpus_path = join(user_app_dir_path, username+'.corpus')

    #Initialise user's corpus path
    fout = open(corpus_path,'w', encoding="utf-8")
    fout.close()

    print("Starting crawl from",base_url)
    while pages_to_visit != []:
        # Start from base url
        print("Pages to visit",pages_to_visit)
        url = pages_to_visit[0]
        pages_visited.append(url)
        pages_to_visit = pages_to_visit[1:]
        try:
            print("\n\n#### Scraping:", url)
            links = omd_parse(url, username)
            for link in links:
                #print(link,pages_visited)
                #print(link,pages_to_visit)
                #print(link,urldir)
                if link not in pages_visited and link not in pages_to_visit and '#' not in link:
                    #print("Found href:",link)
                    pages_to_visit.append(link)
        except RuntimeError as error:
            print(f">> ERROR: SPIDER: OMD PARSE: Failed visiting url: {url}")
            print(error)
