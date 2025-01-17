# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from collections import Counter
from shutil import copy2, copytree
from os.path import dirname, realpath, join
import re
import json
from datetime import datetime
from pathlib import Path
import joblib
import requests
from flask import Blueprint
import click
import pandas as pd
from scipy.sparse import load_npz, save_npz
from selenium import webdriver
from selenium.webdriver.common.by import By
from app import app, db, Urls, Pods
from app.auth import VIEW_FUNCTIONS_PERMISSIONS
from app.auth.controllers import get_func_identifier
from app.indexer.posix import load_posix
from app.utils_db import rm_from_npz, rm_doc_from_pos

pears = Blueprint('pears', __name__)

dir_path = dirname(dirname(dirname(realpath(__file__))))
pod_dir = join(dir_path,'app','pods')


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


#####################
# UNIT TESTS
#####################

@pears.cli.command('unittest')
@click.argument('username')
def checkconsistency(username):
    print("\n>> CLI: UNITTEST: CONSISTENCY CHECKS")
    pods = Pods.query.all()
    usernames = [p.name.split('/')[0] for p in pods]
    if username not in usernames:
        print("\t> ERROR: no username",username)
        return 0
    check_idx_to_url(username)
    check_missing_docs_in_npz(username)
    check_duplicates_idx_to_url(username)
    check_db_vs_idx_to_url(username)
    print("\n")
    pods = [p for p in pods if p.name.split('/')[0] == username]
    for pod in pods:
        print(">> CLI: UNITTEST: CONSISTENCY: CHECKING POD:", pod.name)
        check_npz_to_idx(pod.name)
        check_npz_to_idx_vs_idx_to_url(pod.name, username)
        check_npz_vs_npz_to_idx(pod.name)
        check_pos_vs_npz_to_idx(pod.name)


def check_idx_to_url(username):
    print("\t>> CHECKING IDX_TO_URL")
    pod_path = join(pod_dir, username, 'user.idx')
    idx_to_url = joblib.load(pod_path)
    if len(idx_to_url[0]) != len(idx_to_url[1]):
        print("\t\t> ERROR: the two lists in idx_to_url do not match in length", len(idx_to_url[0]), len(idx_to_url[1]))
    return idx_to_url


def check_db_vs_idx_to_url(username):
    print("\t>> CHECKING DB VS IDX_TO_URL")
    urls = []
    pods = Pods.query.all()
    pods = [p for p in pods if p.name.split('/')[0] == username]
    for pod in pods:
        urls.extend(Urls.query.filter_by(pod=pod.name).all())
    urls = [url.url for url in urls]
    pod_path = join(pod_dir, username, 'user.idx')
    idx_to_url = joblib.load(pod_path)
    if len(set(urls)) != len(set(idx_to_url[1])):
        print("\t\t> ERROR: Length of URL set in DB != len(set(idx)) in idx_to_url", len(urls), len(idx_to_url[0]))
        return list(set(urls)-set(idx_to_url[1]))
    return []


def check_duplicates_idx_to_url(username):
    print("\t>> CHECKING DUPLICATES IN IDX_TO_URL")
    pod_path = join(pod_dir, username, 'user.idx')
    idx_to_url = joblib.load(pod_path)
    if len(idx_to_url[0]) > len(list(set(idx_to_url[0]))):
        print("\t\t> ERROR: Duplicates in idx_to_url (idx)")
    if len(idx_to_url[1]) > len(list(set(idx_to_url[1]))):
        print("\t\t> ERROR: Duplicates in idx_to_url (urls)")


def check_missing_docs_in_npz(username):
    print("\t>> CHECKING DOCS IN IDX_TO_URL WITHOUT A VECTOR")
    pod_path = join(pod_dir, username, 'user.idx')
    idx_to_url = joblib.load(pod_path)
    all_npz_idx = []
    pods = Pods.query.all()
    pods = [p for p in pods if p.name.split('/')[0] == username]
    for pod in pods:
        pod_path = join(pod_dir, pod.name+'.npz.idx')
        npz_to_idx = joblib.load(pod_path)
        all_npz_idx.extend(npz_to_idx[1][1:])
    #A URL can be in two pods (home+shared)
    if set(all_npz_idx) != set(idx_to_url[0]):
        diff = list(set(idx_to_url[0])-set(all_npz_idx))
        print("\t\t> ERROR: Some documents in idx_to_url do not have a vector associated with them.")
        print("\t\t>      :", diff)
        return diff
    return []


def check_npz_to_idx(pod):
    print("\t>> CHECKING NPZ_TO_IDX")
    pod_path = join(pod_dir, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    if len(npz_to_idx[0]) != len(npz_to_idx[1]):
        print("\t\t> ERROR: the two lists in npz_to_idx do not match in length", len(npz_to_idx[0]), len(npz_to_idx[1]))
    if len(npz_to_idx[0]) > len(list(set(npz_to_idx[0]))):
        print("\t\t> ERROR: Duplicates in npz_to_idx (npz)")
    if len(npz_to_idx[1]) > len(list(set(npz_to_idx[1]))):
        print("\t\t> ERROR: Duplicates in npz_to_idx (idx)")


def check_npz_to_idx_vs_idx_to_url(pod, username):
    print("\t>> CHECKING NPZ_TO_IDX VS IDX_TO_URL")
    pod_path = join(pod_dir, username, 'user.idx')
    idx_to_url = joblib.load(pod_path)
    pod_path = join(pod_dir, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    idx1 = idx_to_url[0]
    idx2 = npz_to_idx[1][1:] #Ignore first value, which is -1
    if not set(idx2) <= set(idx1):
        print("\t\t> ERROR: idx in npz_to_idx is not a subset of idx in idx_to_url")


def check_npz_vs_npz_to_idx(pod):
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
        print("\t\t> idx  :", set(idx1))
        print("\t\t> posix:", set(idx2))
    return set(idx1), set(idx2)


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
    repair_duplicates_idx_to_url(username)
    repair_missing_docs_in_npz(username)
    repair_db_vs_idx_to_url(username)
    pods = Pods.query.all()
    pods = [p for p in pods if p.name.split('/')[0] == username]
    for pod in pods:
        print("\n>> CLI: REPAIR: ", pod.name)
        repair_duplicates_npz_to_idx(pod.name)
        repair_npz_to_idx_vs_idx_to_url(pod.name, username)
        repair_npz_vs_npz_to_idx(pod.name)
        repair_pos_vs_npz_to_idx(pod.name)


def repair_duplicates_idx_to_url(username):
    print("\t>> DELETE DUPLICATES IN IDX_TO_URL")
    pod_path = join(pod_dir, username, 'user.idx')
    idx_to_url = joblib.load(pod_path)
    idx = idx_to_url[0]
    urls = idx_to_url[1]
    duplicate_urls = [k for k,v in Counter(urls).items() if v>1]
    for dup in duplicate_urls:
        while dup in urls:
            i = urls.index(dup)
            idx.pop(i)
            urls.pop(i)
    duplicate_idx = [k for k,v in Counter(idx).items() if v>1]
    for dup in duplicate_idx:
        while dup in idx: #several entries could have the same idx
            i = idx.index(dup)
            idx.pop(i)
            urls.pop(i)
    joblib.dump([idx,urls], pod_path)


def repair_missing_docs_in_npz(username):
    print("\t>> DELETE DOCS WITHOUT VECTORS FROM IDX_TO_URL")
    pod_path = join(pod_dir, username, 'user.idx')
    idx_to_url = joblib.load(pod_path)
    idx = idx_to_url[0]
    urls = idx_to_url[1]
    diff = check_missing_docs_in_npz(username)
    for doc in diff:
        i = idx.index(doc)
        idx.pop(i)
        urls.pop(i)
    joblib.dump([idx,urls], pod_path)


def repair_db_vs_idx_to_url(username):
    print("\t>> DELETE DOCS IN DB WITHOUT AN IDX")
    diff = check_db_vs_idx_to_url(username)
    print(diff)
    for url in diff:
        u = db.session.query(Urls).filter_by(url=url).first()
        db.session.delete(u)
        db.session.commit()


def repair_duplicates_npz_to_idx(pod):
    print("\t>> DELETE DUPLICATES IN NPZ_TO_IDX")
    pod_path = join(pod_dir, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    npz = npz_to_idx[0]
    idx = npz_to_idx[1]
    duplicate_npz = [k for k,v in Counter(npz).items() if v>1]
    for dup in duplicate_npz:
        while dup in npz:
            i = npz.index(dup)
            npz.pop(i)
            idx.pop(i)
    duplicate_idx = [k for k,v in Counter(idx).items() if v>1]
    for dup in duplicate_idx:
        while dup in idx: #several entries could have the same idx
            i = idx.index(dup)
            npz.pop(i)
            idx.pop(i)
    joblib.dump([npz,idx], pod_path)


def repair_npz_to_idx_vs_idx_to_url(pod, username):
    print("\t>> DELETE NPZ_TO_IDX ENTRIES NOT IN IDX_TO_URL")
    pod_path = join(pod_dir, username, 'user.idx')
    idx_to_url = joblib.load(pod_path)
    pod_path = join(pod_dir, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    idx1 = idx_to_url[0]
    idx2 = npz_to_idx[1][1:] #Ignore first value, which is -1
    idx = npz_to_idx[1]
    diff = list(set(idx2)-set(idx1))
    popped = []
    for d in diff:
        while d in idx:  #several entries could have the same idx
            i = idx.index(d)
            idx.pop(i)
            popped.append(i)
    if len(popped) > 0:
        print("\t   "+str(len(popped))+" entries popped. ("+' '.join([str(i) for i in popped])+')')
    npz = list(range(len(idx)))
    joblib.dump([npz, idx], pod_path)
    del_npz_rows(pod, popped)


def repair_npz_vs_npz_to_idx(pod):
    print("\t>> DELETE NPZ ENTRIES NOT IN NPZ_TO_IDX")
    pod_path = join(pod_dir, pod+'.npz.idx')
    npz_to_idx = joblib.load(pod_path)
    pod_path = join(pod_dir, pod+'.npz')
    pod_m = load_npz(pod_path)
    npz = npz_to_idx[0]
    pod_m = pod_m[:len(npz)]
    save_npz(pod_path, pod_m)

def repair_pos_vs_npz_to_idx(pod):
    idx1, idx2 = check_pos_vs_npz_to_idx(pod)
    if len(idx1) > len(idx2):
        orphans = list(idx1-idx2)
        del_pod_docs(pod, orphans)


def del_npz_rows(pod, todelete):
    print("\t>> DELETE NPZ ROWS", todelete)
    for i in todelete:
        rm_from_npz(i,pod)


def del_pod_docs(pod, todelete):
    print("\t>> DELETE POS DOCS", todelete)
    for i in todelete:
        rm_doc_from_pos(i,pod)


#####################
# SHOW INDEX FILES
#####################

@pears.cli.command('show')
@click.argument('username')
@click.argument('indexfile')
def showindexfile(username, indexfile):
    if indexfile == 'idx_to_url':
        print(">> CLI: SHOW: IDX TO URL: ")
        pod_path = join(pod_dir, username, 'user.idx')
        idx_to_url = joblib.load(pod_path)
        for i in range(len(idx_to_url[0])):
            print(idx_to_url[0][i], idx_to_url[1][i])

    if indexfile == 'npz_to_idx':
        pods = Pods.query.all()
        pods = [p for p in pods if p.name.split('/')[0] == username]
        for pod in pods:
            print("\n>> CLI: SHOW: NPZ TO IDX: ", pod.name)
            pod_path = join(pod_dir, pod.name+'.npz.idx')
            npz_to_idx = joblib.load(pod_path)
            for i in range(len(npz_to_idx[0])):
                print(npz_to_idx[0][i], npz_to_idx[1][i])

    if indexfile == 'posdocs':
        pods = Pods.query.all()
        pods = [p for p in pods if p.name.split('/')[0] == username]
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


#####################
# PERMISSION CHECKER
#####################

@pears.cli.command('list_endpoint_permissions')
def list_endpoints():
    """
    This command makes a CSV list of all of the endpoints in the entire flask application,
    and reads from the @login_required decorators which ones require being logged in.
    The output can be manually annotated to account for endpoints that are missing 
    @login_required or mistakenly have it. The final list can then be read by the 
    test_endpoint_permissions command, which checks for any authentication errors. 
    """
    endpoint_permissions = {}
    for ep, func in app.view_functions.items():
        func_id = get_func_identifier(func)
        permissions = VIEW_FUNCTIONS_PERMISSIONS.get(func_id)
        if permissions is None:
            # admin + DB management endpoints
            # TODO: find a less hacky way to get the permissions for these
            if ep.split(".")[0] in ["admin", "sites", "pods", "urls", "locations", "groups"]: # NB: locations and groups are not used at the moment, but might be (re-)added (e.g. for testing purposes) in the future
                permissions = {"login": True}
            else:
                # TODO: is this always true??
                permissions = {"login": False}
        endpoint_permissions[ep] = permissions

    rows = []
    for ep, permissions in endpoint_permissions.items():
        row_dict = {"endpoint": ep}
        row_dict.update(permissions)
        rows.append(row_dict)
    pd.DataFrame(rows).to_csv("endpoint_permissions.csv")


@pears.cli.command('update_manual_permission_sheet')
@click.argument("old_annotated_sheet")
def update_manual_permission_sheet(old_annotated_sheet):
    """
    Litle helper command that adds extra rows to a manually annotated version of the 
    endpoint permissions sheet created by list_endpoint_permissions if any new endpoints 
    have been added after completing the annotation. 
    """
    # set the index to endpoint so we can easily look up rows
    old_annotated_df = pd.read_csv(old_annotated_sheet, index_col=0).set_index("endpoint")
    new_unannotated_df = pd.read_csv("endpoint_permissions.csv", index_col=0).set_index("endpoint")
    columns = old_annotated_df.columns
    assert all(c in columns for c in new_unannotated_df.columns), "Found unknown columns in endpoint_permissions.csv, please update the new sheet manually"
    old_endpoints = set(old_annotated_df.index)
    new_endpoints = set(new_unannotated_df.index).difference(old_endpoints)
    if not new_endpoints:
        print("No new endpoints found!")
        return
    
    new_rows = []
    for ep in new_endpoints:
        new_entry = {"endpoint": ep}
        new_entry.update({c: "[[NEW!]]" for c in columns})
        new_entry.update(new_unannotated_df.loc[ep])
        new_rows.append(new_entry)
    new_rows_df = pd.DataFrame(new_rows)
    new_annotated_df = pd.concat([
        old_annotated_df.reset_index(names=["endpoint"]), # make "endpoint" a normal column so we can concatenate correctly 
        new_rows_df
    ])
    (
        new_annotated_df
        .reset_index(drop=True) # redo the index so we have continuous numbering
        .to_csv("endpoint_permission__annotated_new.csv")
    )


@pears.cli.command('test_endpoint_permissions')
@click.argument("manual")
def test_endpoint_permissions(manual=False):
    if manual:
        permissions = pd.read_csv("endpoint_permissions__manual.csv", index_col=0)
    else:
        permissions = pd.read_csv("endpoint_permissions.csv", index_col=0)

    permissions = (
        permissions
        .dropna(subset=["login"])  # drop entries with missing permissions (= endpoints that are marked for deletion)
        .fillna({"skip": False, "reset_login": False}) # fill in False for unspecified skip/reset column entries
    )

    # selenium 
    # (setup for firefox: getting the right gecko driver on ubuntu, see https://stackoverflow.com/a/78110627)
    # uncomment the right version depending on your system
    # geckodriver_path = "/snap/bin/geckodriver" # for recent ubuntus
    geckodriver_path = "/usr/local/bin/geckodriver"  # for other systems
    driver_service = webdriver.FirefoxService(executable_path=geckodriver_path)
    def _start_browser():
        return webdriver.Firefox(service=driver_service)

    # which endpoints have which arugments?
    # (for now, we'll skip the ones that take arguments)
    endpoints_to_arguments = {}
    endpoints_to_methods = {}
    for rule in app.url_map.iter_rules():
        endpoints_to_arguments[rule.endpoint] = rule.arguments
        endpoints_to_methods[rule.endpoint] = rule.methods

    # read test user login info
    with open("testusers.json") as f:
        test_users = json.load(f)
    
    TEST_CASES = [
        {"logged_in": False},
        {"logged_in": True}
    ]

    results = []
    for tc in TEST_CASES:

        print(f"Running test case: {tc}")
        browser = _start_browser()

        user = None
        csrf_token = None
        if tc["logged_in"]:
            user = test_users["testuser"]
            csrf_token = _selenium_test_login(browser, user)
        else:
            csrf_token = _selenium_get_csrf_without_login(browser)
        _cookies = browser.get_cookies()
        
        if _cookies:
            cookies = {c["name"]: c["value"] for c in _cookies}
        else:
            cookies = {}
        print(cookies)

        urls = app.url_map.bind("localhost:9090", "/")
        for _, ep_data in permissions.iterrows():
            ep = ep_data["endpoint"]

            endpoint_results = {
                "user": user["username"] if user else None,
                "endpoint": ep,
                "methods": endpoints_to_methods[ep],
                "permissions_login": ep_data["login"],
                "arguments": None,
                "url": None,
                "received_status": None,
                "test_result": 0,  ## 0 = not applicable, -1 = failure, +1 = success 
                "test_result_note": None,
                "test_skipped_reason": None
            }
            results.append(endpoint_results)
            if ep_data["skip"]:
                print(f"\t skipping endpoint {ep} according to instructions")
                endpoint_results["test_skipped_reason"] = "marked for skipping in permission sheet"
                continue
            print(ep)

            url_args = {}
            get_args = {}
            form_args = {} 
            argtype = ep_data["argtype"]
            if argtype == "url":
                url_args = _parse_endpoint_example_args(ep_data["argex"])
            elif argtype == "get":
                get_args = _parse_endpoint_example_args(ep_data["argex"])
            elif argtype == "form":
                form_args = _parse_endpoint_example_args(ep_data["argex"])
                form_args["csrf_token"] = csrf_token
            url = urls.build(ep, url_args, force_external=True)
            endpoint_results["url"] = url
            print("\t", ep, "->", url)

            # use requests to see if we get the right status code
            # (selenium can't do this out of the box, cf https://github.com/seleniumhq/selenium-google-code-issue-archive/issues/141)
            chosen_method = None
            num_attempts = 5
            for attempt in range(num_attempts):
                try:
                    methods = endpoints_to_methods[ep]
                    if "GET" in methods:
                        chosen_method = "GET"
                        r = requests.get(url, params=get_args, cookies=cookies)
                    elif "POST" in methods:
                        chosen_method = "POST"
                        if get_args:
                            raise ValueError("Trying to use GET arguments in POST request!")
                        r = requests.post(url, data=form_args, cookies=cookies)
                    else:
                        raise ValueError("Got endpoint that supports neither GET nor POST, don't know what to do!")
                    break
                except ConnectionError:
                    print(f"\tAttempt {attempt+1}, can't connect to {url}")
            else: 
                print(f"\tNo success after {num_attempts} attemps, giving up on {url}")
                endpoint_results["test_skipped_reason"] = "connection_failure"
                continue

            should_have_access = _should_have_access(tc, ep_data)
            received_status_code = r.status_code
            endpoint_results["received_status"] = received_status_code

            if received_status_code == 200 and not should_have_access:
                # check if we've been redirected to the login/confirmation page
                if r.history and r.history[-1].status_code == 302 and (r.url.startswith("http://localhost:9090/auth/login?next=") or r.url.startswith("http://localhost:9090/auth/inactive")):
                    endpoint_results["test_result"] = 1
                    endpoint_results["test_result_note"] = "redirected to home page as expected"
                elif ep_data["admin"] and r.url == "http://localhost:9090/":
                    # we have been sent back to the home page, let's check if we get the admin-only message
                    if _selenium_check_admin_warning_displayed(browser, url):
                        endpoint_results["test_result"] = 1
                        endpoint_results["test_result_note"] = "should not have access, is appropriately redirected to home page with admin-only warning"
                    else:
                        endpoint_results["test_result"] = -1
                        endpoint_results["test_result_note"] = "should not have access, is redirected to home page but without message"
                elif r.history and r.history[-1].status_code == 302 and r.url.startswith("http://localhost:9090/admin/"):
                    # sent back to one of the admin pages?
                    # check for error code
                    if _senelium_check_admin_permission_denied_msg(browser, url):
                        endpoint_results["test_result"] = 1
                        endpoint_results["test_result_note"] = "sent back to admin page with 'permission denied' message, this is appropriate here"
                    else:
                        endpoint_results["test_result"] = 0
                        endpoint_results["test_result_note"] = "sent to admin page without 'permission denied' message, don't know what's going on"

                else:
                    endpoint_results["test_result"] = -1
                    endpoint_results["test_result_note"] = "appears to have access but should not"
    
            elif received_status_code == 200 and should_have_access:
                if r.history and r.history[-1].status_code == 302 and (r.url.startswith("http://localhost:9090/auth/login?next=")  or r.url.startswith("http://localhost:9090/auth/inactive")):

                    # exception: some endpoints *should* redirect to /auth/inactive, with a message
                    if ep == "auth.resend_confirmation" and r.url.startswith("http://localhost:9090/auth/inactive") and _selenium_check_confirmation_mail_sent_displayed(browser, url):
                        endpoint_results["test_result"] = 1
                        endpoint_results["test_result_note"] = "should have access, verified flash contents using selenium"
                    else:
                        endpoint_results["test_result"] = -1
                        endpoint_results["test_result_note"] = "should have access but is unexpectedly redirected to login/inactive page"                    
                
                # have we been redirected to the home page
                elif r.history and r.history[-1].status_code == 302 and r.url == "http://localhost:9090/":
                    if chosen_method == "GET" and _selenium_check_admin_warning_displayed(browser, url):
                        endpoint_results["test_result"] = -1
                        endpoint_results["test_result_note"] = "should have access but unexpectedly rerouted to home page with admin warning"
                    else:
                        endpoint_results["test_result"] = 1
                        endpoint_results["test_result_note"] = "rerouted to home page, no warnings found; I'm assuming this means the endpoint was successfully accessed"

                # sent back to one of the admin pages?
                elif r.history and r.history[-1].status_code == 302 and r.url.startswith("http://localhost:9090/admin/"):
                    # check for error code
                    if _senelium_check_admin_permission_denied_msg(browser, url):
                        endpoint_results["test_result"] = -1
                        endpoint_results["test_result_note"] = "sent back to admin page with 'permission denied' message, while we should have access"
                    else:
                        endpoint_results["test_result"] = 0
                        endpoint_results["test_result_note"] = "sent to admin page without 'permission denied' message, don't know what's going on"

                else:
                    endpoint_results["test_result"] = 1
                    endpoint_results["test_result_note"] = "should have access and does"

            elif str(received_status_code).startswith("4") and not should_have_access:
                endpoint_results["test_result"] = 1
                endpoint_results["test_result_note"] = "should not have access and gets 4xx response"
            
            elif str(received_status_code).startswith("4") and should_have_access:
                endpoint_results["test_result"] = -1
                endpoint_results["test_result_note"] = "should have access but gets 4xx response"

            else:
                endpoint_results["test_result"] = 0
                endpoint_results["test_skipped_reason"] = "can't interpret test outcome"

            # if the test logged us out (for now: auth.logout): log us back in
            if ep_data["reset_login"] and endpoint_results["test_result"] == 1:
                if user is not None:
                    csrf_token = _selenium_test_login(browser, user)
                else:
                    csrf_token = _selenium_get_csrf_without_login(browser)

        browser.quit()
        df_results = (
            pd.DataFrame(results)
        )
        df_results_styled = (
            df_results
            .style
            .applymap(
            lambda res: (
                "background-color: green" if res > 0 else 
                "background-color: yellow" if res == 0 else
                "background-color: red"
                ), 
            subset=["test_result"]
            )
        )
        df_results_styled.to_html("permission_tests.html")
        df_results.to_csv("permission_tests.csv")

def _selenium_test_login(browser, user):
    # go to login page 
    browser.get("http://localhost:9090/auth/login")

    # get the CSRF token (needed to test POST requests)
    csrf_token = browser.find_element(By.ID, value="csrf_token").get_attribute("value")

    # fill out and submit the login form
    browser.find_element(By.ID, value="username").send_keys(user["username"])
    browser.find_element(By.ID, value="password").send_keys(user["password"])
    browser.find_element(By.ID, value="submit_button").click()

    return csrf_token

def _selenium_get_csrf_without_login(browser):
    browser.get("http://localhost:9090/auth/login")
    csrf_token = browser.find_element(By.ID, value="csrf_token").get_attribute("value")
    return csrf_token

def _selenium_check_admin_warning_displayed(browser, target_url):
        browser.get(target_url) # redo the request with selenium
        divs = browser.find_elements(By.CLASS_NAME, value="notification.is-danger")
        if divs and "The page you requested is admin only." in divs[0].text:
            return True
        return False

def _senelium_check_admin_permission_denied_msg(browser, target_url):
        browser.get(target_url) # redo the request with selenium
        divs = browser.find_elements(By.CLASS_NAME, value="alert.alert-danger.alert-dismissable")
        if divs and "Permission denied." in divs[0].text:
            return True
        return False


def _selenium_check_confirmation_mail_sent_displayed(browser, target_url):
    browser.get(target_url) # redo the request with selenium
    divs = browser.find_elements(By.CLASS_NAME, value="notification.is-danger")
    
    if divs and "A new confirmation email has been sent." in divs[0].text:
        return True
    return False

def _should_have_access(test_case, endpoint_info):
    if endpoint_info["login"] and not test_case["logged_in"]:
        return False
    return True

def _parse_endpoint_example_args(arg_string):
    args = {}
    for item in arg_string.split(","):
        item = item.strip()
        m = re.match(r"(?P<key>\S+?):(?P<val>\S+)", item)
        if not m:
            raise ValueError("Argument examples don't follow the correct format!")
        args[m.group("key")] = m.group("val")
    return args
