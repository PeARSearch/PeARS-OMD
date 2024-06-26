# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from os.path import join, dirname, realpath
from flask import session, url_for
import xmltodict
import requests
from langdetect import detect
from app.indexer.htmlparser import extract_txt
from app import (LANGS, OMD_PATH, LOCAL_RUN, 
        AUTH_TOKEN, FILE_SIZE_LIMIT, IGNORED_EXTENSIONS)

app_dir_path = dirname(dirname(realpath(__file__)))
user_app_dir_path = join(app_dir_path,'userdata')

def omd_parse(current_url, username):
    """ This function parses a url and writes the text content
    to the user's corpus file.
    Arguments: the url path and a username.
    """
    logging.info("\n>> INDEXER: SPIDER: omd_parse: Running OMD parse on "+current_url)
    links = []
    fout = open(join(user_app_dir_path, username+'.corpus'),'a', encoding='utf-8')
    try:
        xml = requests.get(current_url, timeout=120, \
            headers={'Authorization': AUTH_TOKEN}, stream =True).raw
    except RuntimeError as error:
        logging.error(">> ERROR: SPIDER: OMD PARSE: Request failed. Moving on.")
        logging.error(error)
        return links
    #print(xml.read())
    #xml = requests.get(current_url, timeout=60, \
    #    headers={'Authorization': AUTH_TOKEN}, stream =True).raw
    try:
        parse = xmltodict.parse(xml.read())
    except:
        logging.error(">> ERROR: SPIDER: OMD PARSE: File may have some bad XML. Could not parse.")
        return links
    try:
        docs = parse['omd_index']['doc']
    except:
        logging.error(">> ERROR: SPIDER: OMD PARSE: No documents found in the XML.")
        return links

    if not isinstance(docs, list):
        docs = [docs]
    for doc in docs:
        urldir = '/'.join(current_url.split('/')[:-1])

        # URL
        if doc['@url'][0] == '/':
            url = doc['@url'][1:]
        else:
            url = doc['@url']
        if url.startswith('shared/'):
            url = join(OMD_PATH, url)
        else:
            url = join(urldir, url)
        logging.info(">> INDEXER: SPIDER: omd_parse: doc url: "+url)
        if LOCAL_RUN:
            if url[-1] == '/': #For local test only
                url = join(url,'index.html')
        
        # IS THIS ITEM A FOLDER DESCRIPTION
        is_folder_description = url.endswith("?description")
        if is_folder_description:
            url = url.replace("?description", "")

        # EXTENSION
        extension = '.'+url.split('/')[-1].split('.')[-1]
        if extension in IGNORED_EXTENSIONS:
            continue

        # CONVERTIBILITY
        convertible = False
        try:
            logging.info(">> SPIDER: OMD_PARSE: DOC CONVERTIBILITY: ", doc.get('@convertible'))
            convertible_str = doc.get("@convertible")
            assert convertible_str in ["True", "False", None]
            convertible = True if convertible_str == "True" else False 

        except RuntimeError as error:
            logging.info(">> SPIDER: OMD_PARSE: DOC CONVERTIBILITY: No convertible")
            logging.info(error)

        # CONTENT TYPE
        try:
            logging.info(">> SPIDER: OMD_PARSE: DOC CONTENTTYPE: "+extension+" "+doc['@contentType'])
            content_type = doc['@contentType']
            if content_type in ['folder','desktop']:
                if join(OMD_PATH,'shared') not in url:
                    links.append(url)
                # for folders - add the URL to the list & skip!
                # we'll come back to it, and index it based on the ?description info
                continue
        except RuntimeError as error:
            logging.info(">> SPIDER: OMD_PARSE: DOC CONTENTTYPE: No contentType")
            logging.info(error)
            pass

        
        # TITLE
        try:
            logging.info(">> SPIDER: OMD_PARSE: DOC TITLE: "+doc['title'])
            title = doc['title']
        except RuntimeError as error:
            logging.info(">> SPIDER: OMD_PARSE: DOC TITLE: No title")
            logging.info(error)
            pass
        if title is None:
            if is_folder_description:
                title = doc["description"]
            else:   
                title = ''
        

        # DESCRIPTION
        description = None
        try:
            logging.info(">> SPIDER: DOC DESCRIPTION: "+doc['description'][:100])
            if title != doc['description']:
                description = title + ' ' + doc['description']
            else:
                description = doc['description']
            logging.info("\t"+description+"\n")
        except:
            logging.info(">> SPIDER: DOC DESCRIPTION: No description")
            pass
       
        
        # FIRST GO AT LANGUAGE DETECTION
        if description is not None:
            language = detect(description)
        else:
            language = LANGS[0]

        # CONTENT, ONLY DOCS (NOT FOLDERS)
        body_str = None
        if convertible:
            title, body_str, _, language = extract_txt(url + "?totext")
        elif is_folder_description:
            _, description, _, language = extract_txt(url + "?description")
        elif content_type in ['text/plain', 'text/x-tex']:
            title, body_str, _, language = extract_txt(url)

        # Hack. Revert to main language if language is not installed
        if language not in LANGS:
            logging.info(">> SPIDER: LANGUAGE: language is not in LANGS, reverting to default.")
            language = LANGS[0]

        # Write to temporary corpus file
        logging.info(">> SPIDER: WRITING CORPUS")
        fout.write("<doc title='"+title+"' url='"+url+"' lang='"+language+"'>\n")
        if description:
            fout.write("{{DESCRIPTION}} "+description+"\n")
        if body_str:
            # Limit how much of the content will be indexed, to cope with storage limitations
            fout.write("{{BODY}} "+body_str[:FILE_SIZE_LIMIT]+"\n")
        fout.write("</doc>\n")
    fout.close()

    #print("\n NEW LINKS:",links)
    return links

def write_docs(base_url, username):
    """Write document corpus while crawling.
    Argument: base url, to start the crawl from.
    """
    if base_url is None:
        print("No url passed.")
        return url_for('indexer')

    if not LOCAL_RUN and base_url[-1] != '/':
        base_url+='/'

    pages_to_visit = [base_url]
    pages_visited = []
    corpus_path = join(user_app_dir_path, username+'.corpus')

    #Initialise user's corpus path
    fout = open(corpus_path,'w', encoding="utf-8")
    fout.close()

    print(">> INDEXER: SPIDER: write_docs: Starting crawl from",base_url)
    while len(pages_to_visit) > 0:
        # Start from base url
        #print("Pages to visit",pages_to_visit)
        url = pages_to_visit[0]
        pages_visited.append(url)
        try:    
            links = omd_parse(url, username)
            for link in links:
                #print(link,pages_visited)
                #print(link,pages_to_visit)
                #print(link,urldir)
                if link not in pages_visited and link not in pages_to_visit and '#' not in link:
                    #print("Found href:",link)
                    pages_to_visit.append(link)
        except: 
            print(f">> ERROR: SPIDER: OMD PARSE: exceptions in parsing: {url}")
        pages_to_visit = pages_to_visit[1:]
