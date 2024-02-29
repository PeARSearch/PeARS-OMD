# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import join
from urllib.parse import quote_plus
from inspect import getfullargspec
from functools import wraps
import requests
from flask import Blueprint, request, render_template, make_response, session
from flask_cors import cross_origin
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from app import LOCAL_RUN, AUTH_TOKEN, OMD_PATH

# Define the blueprint:
auth = Blueprint('auth', __name__, url_prefix='/auth')

class LoginForm(FlaskForm):
    username = StringField('Username')
    password = PasswordField('Password')
    submit = SubmitField('Submit')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    # Declare the login form using FlaskForm library
    form = LoginForm(request.form)
    print(form)
    # Flask message injected into the page, in case of any errors
    msg = None
    # check if both http method is POST and form is valid on submit
    if form.validate_on_submit():
        # assign form data to variables
        username = request.form.get('username', '', type=str)
        password = request.form.get('password', '', type=str)
        # send authorization message to on my disk
        if LOCAL_RUN:
            url = 'http://localhost:9191/api' #Local test
        else:
            url = join(OMD_PATH, 'signin/')
        data = {'action': 'signin', 'username': username, 'password': password}
        user_info = requests.post(url, json=data) 
        if user_info == None:
            msg = "Incorrect credentials"
            return render_template( 'auth/login.html', form=form, msg=msg), 401
        else:
            if not user_info.json()['valid']:
                msg="Incorrect credentials or session expired, redirecting to login page."
                return render_template( 'auth/login.html', form=form, msg=msg), 401
            print(user_info.json())
            print(user_info.cookies)
            username = user_info.json()['username']
            session_token = user_info.json()['session_id']
            # Fill in session info
            session['logged_in'] = True
            session['username'] = username
            session['token'] = session_token
            # Create a new response object
            resp_frontend = make_response(render_template( 'search/user.html', welcome="Welcome "+username))
            # Transfer the cookies from backend response to frontend response
            for name, value in user_info.cookies.items():
                print("SETTING COOKIE:",name, value)
                resp_frontend.set_cookie(name, value, samesite='Lax')
            # Cookies returned from OMD may not work in some modern browsers, so make our own OMD_SESSION_ID cookie
            print("SESSION TOKEN JUST BEFORE SETTING COOKIE", session_token, type(session_token))
            resp_frontend.set_cookie('OMD_SESSION_ID', session_token, samesite='Lax')
            return resp_frontend
    else:
        msg = "Unknown user"
        return render_template( 'auth/login.html', form=form, msg=msg), 401


@auth.route('/logout', methods=['GET','POST'])
def logout():
    access_token = request.cookies.get('OMD_SESSION_ID')
    if LOCAL_RUN:
        url = 'http://localhost:9191/api' #Local test
    else:
        url = join(OMD_PATH, 'signout/')
    data = {'action': 'signout', 'session_id': access_token}
    logout_confirmation = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
    if logout_confirmation.status_code < 400:
        print("Logging out")
    else:
        print("Logged out")
    # Create a new response object
    session['logged_in'] = False
    session.pop('username', None)
    resp_frontend = make_response(render_template( 'search/anonymous.html'))
    resp_frontend.set_cookie('OMD_SESSION_ID', '', expires=0, samesite='Lax')
    return resp_frontend


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if LOCAL_RUN:
            url = 'http://localhost:9191/api' #Local test
        else:
            url = join(OMD_PATH, 'signin/')
        
        access_token = request.headers.get('Token') #Get token from request header
        print(">> login_required: access_token: OMD_SESSION_ID", access_token)
        if access_token:
            #backend_to_backend
            if access_token == AUTH_TOKEN: #if it equals to system-wide security token, then it is call from OMD backend
                print("Backend to backend")
                if 'access_token' in getfullargspec(f).args:
                    kwargs['access_token'] = access_token
                return f(*args, **kwargs)

        #Otherwise, it is frontend calling
        if not access_token:
            access_token = request.cookies.get('OMD_SESSION_ID')
            print(">> login_required: access_token: OMD_SESSION_ID", access_token)
        if not access_token: # still no token - relogin is needed
            session['logged_in'] = False
            session['token'] = ''
            return render_template('search/anonymous.html'), 401

        #Token is present and it is user's session token. Check if this token is already stored in session
	#to avoid excess OMD api calls on every key press
        if bool(session.get('logged_in')) and  session.get('token') == access_token:
            if 'access_token' in getfullargspec(f).args:
                kwargs['access_token'] = access_token
            return f(*args, **kwargs)
        #Token is present but we need to check if OMD session is valid
        data = {'action': 'getUserInfo', 'session_id': access_token}
        resp = requests.post(url, json=data, timeout=30, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
        if resp.status_code < 400 and resp.json()['valid']:
            session['logged_in'] = True
            session['username'] = resp.json()['username']
            session['token'] = access_token #save token	in session
            if 'access_token' in getfullargspec(f).args:
                kwargs['access_token'] = access_token
            return f(*args, **kwargs)
        session['logged_in'] = False 	
        return render_template('search/anonymous.html'), 401
    return decorated_function
