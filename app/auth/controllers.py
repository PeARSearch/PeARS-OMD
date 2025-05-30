# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import join
from inspect import getfullargspec
from functools import wraps
import requests
from flask import Blueprint, request, render_template, make_response, session, flash
from flask_cors import cross_origin
from app.forms import LoginForm, SearchForm
from app import AUTH_TOKEN, OMD_PATH

# Define the blueprint:
auth = Blueprint('auth', __name__, url_prefix='/auth')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    # Declare the login form using FlaskForm library
    form = LoginForm(request.form)
    # check if both http method is POST and form is valid on submit
    if form.validate_on_submit():
        # assign form data to variables
        username = request.form.get('username', '', type=str)
        password = request.form.get('password', '', type=str)
        # send authorization message to on my disk
        url = join(OMD_PATH, 'signin/')
        data = {'action': 'signin', 'username': username, 'password': password, 'remember': True}
        user_info = requests.post(url, timeout=30, json=data)
        if user_info is None:
            flash("Incorrect credentials")
            return render_template( 'auth/login.html', form=form), 401
        if not user_info.json()['valid']:
            flash("Incorrect credentials or session expired, redirecting to login page.")
            return render_template( 'auth/login.html', form=form), 401
        #print(user_info.json())
        #print(user_info.cookies)
        username = user_info.json()['profile']['user']
        is_admin = user_info.json()['profile']['isAdmin']
        session_token = user_info.json()['session_id']
        # Fill in session info
        session.permanent = False
        session['logged_in'] = True
        session['username'] = username
        session['token'] = session_token
        session['admin'] = is_admin
        # Create a new response object
        searchform = SearchForm()
        resp_frontend = make_response(render_template( 'search/user.html', welcome="Welcome "+username, searchform=searchform))
        # Transfer the cookies from backend response to frontend response
        for name, value in user_info.cookies.items():
            #print("SETTING COOKIE:",name, value)
            resp_frontend.set_cookie(name, value, samesite='Lax')
        # Cookies returned from OMD may not work in some modern browsers, so make our own OMD_SESSION_ID cookie
        #print("SESSION TOKEN JUST BEFORE SETTING COOKIE", session_token, type(session_token))
        resp_frontend.set_cookie('OMD_SESSION_ID', session_token, samesite='Lax')
        return resp_frontend
    flash("Hello, unknown user.")
    return render_template( 'auth/login.html', form=form), 401


@auth.route('/logout', methods=['GET','POST'])
def logout():
    access_token = request.cookies.get('OMD_SESSION_ID')
    url = join(OMD_PATH, 'signout/')
    data = {'action': 'signout', 'session_id': access_token}
    logout_confirmation = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
    if logout_confirmation.status_code < 400:
        print("Logging out")
    else:
        print("Logged out")
    # Create a new response object
    #session['logged_in'] = False
    #session.pop('username', None)
    session.clear()
    #print(">> AUTH: user logged out. Clearing session and OMD_SESSION_ID cookie.")
    #print(f">> SESSION: {session}")
    searchform = SearchForm()
    resp_frontend = make_response(render_template( 'search/anonymous.html', searchform=searchform))
    resp_frontend.set_cookie('OMD_SESSION_ID', '', expires=0, samesite='Lax')
    return resp_frontend


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        url = join(OMD_PATH, 'signin/')
        
        access_token = request.headers.get('Token') #Get token from request header
        #print(">> login_required: access_token from header: OMD_SESSION_ID", access_token)

        if not access_token:
           access_token = session.get('token')
           #print(">> login_required: access_token from session: OMD_SESSION_ID", access_token)

        if access_token:
            #backend_to_backend
            if access_token == AUTH_TOKEN: #if it equals to system-wide security token, then it is call from OMD backend
                #print("Backend to backend")
                if 'access_token' in getfullargspec(f).args:
                    kwargs['access_token'] = access_token
                return f(*args, **kwargs)

        #Otherwise, it is frontend calling
        if not access_token:
            access_token = request.cookies.get('OMD_SESSION_ID')
            #print(">> login_required: access_token from cookie: OMD_SESSION_ID", access_token)
        if not access_token: # still no token - relogin is needed
            #session['logged_in'] = False
            #session['token'] = ''
            session.clear()
            print(">> AUTH: no token found. Clearing session and OMD_SESSION_ID cookie.")
            print(f">> SESSION: {session}")
            searchform = SearchForm()
            resp_frontend = make_response(render_template( 'search/anonymous.html', searchform=searchform), 401)
            resp_frontend.set_cookie('OMD_SESSION_ID', '', expires=0, samesite='Lax')
            return resp_frontend

        #Token is present and it is user's session token. Check if this token is already stored in session
	#to avoid excess OMD api calls on every key press
        #print(f">>AUTH DECORATOR: checking session token vs access token: {session.get('token')} : {access_token}")
        if bool(session.get('logged_in')) and  session.get('token') == access_token:
            if 'access_token' in getfullargspec(f).args:
                kwargs['access_token'] = access_token
            return f(*args, **kwargs)
        #Token is present but we need to check if OMD session is valid
        data = {'action': 'getUserInfo', 'session_id': access_token}
        #print(f">>AUTH DECORATOR: sending request for user info with access token: {access_token}")
        resp = requests.post(url, json=data, timeout=30, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
        if resp.status_code < 400 and resp.json()['valid']:
            session['logged_in'] = True
            session['username'] = resp.json()['user']
            session['token'] = access_token #save token	in session
            if 'access_token' in getfullargspec(f).args:
                kwargs['access_token'] = access_token
            return f(*args, **kwargs)
        session.clear()
        print(">> AUTH DECORATOR: OMD session is not valid. Clearing session and OMD_SESSION_ID cookie.")
        print(f">> SESSION: {session}")
        searchform = SearchForm()
        resp_frontend = make_response(render_template( 'search/anonymous.html', searchform=searchform), 401)
        resp_frontend.set_cookie('OMD_SESSION_ID', '', expires=0, samesite='Lax')
        return resp_frontend
    return decorated_function
