# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
from flask import Blueprint, request, render_template, send_from_directory, make_response
from flask import current_app, session
from flask_cors import cross_origin
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from functools import wraps
from inspect import getfullargspec

# Import the database object from the main app module
from app import app

# Import utilities
import re
import os
import requests
from os.path import dirname, join, realpath, isfile
from flask import jsonify, Response
from app import LOCAL_RUN, AUTH_TOKEN

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
            url = ' https://demo.onmydisk.net/signin/'
        data = {'action': 'signin', 'username': username, 'password': password}
        user_info = requests.post(url, json=data) 
        if user_info == None:
            msg = "Incorrect credentials"
            return render_template( 'auth/login.html', form=form, msg=msg)
        else:
            access_token = user_info.cookies.get('OMD_SESSION_ID')
            print(user_info.json())
            print(user_info.cookies)
            username = user_info.json()['username']
            # Create a new response object
            session['logged_in'] = True
            resp_frontend = make_response(render_template( 'search/user.html', welcome="Welcome "+username))
            # Transfer the cookies from backend response to frontend response
            for name, value in user_info.cookies.items():
                print("SETTING COOKIE:",name,value)
                resp_frontend.set_cookie(name, value, samesite='Lax')
            return resp_frontend
            #return render_template('search/user.html', welcome="Welcome "+username)
    else:
       msg = "Unknown user"
       return render_template( 'auth/login.html', form=form, msg=msg)


@auth.route('/logout', methods=['GET','POST'])
def logout():
    access_token = request.cookies.get('OMD_SESSION_ID')
    if LOCAL_RUN:
        url = 'http://localhost:9191/api' #Local test
    else:
        url = ' https://demo.onmydisk.net/signout/'
    data = {'action': 'signout', 'session_id': access_token}
    logout_confirmation = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
    if logout_confirmation.status_code == requests.codes.ok:
        print("Logging out")
    else:
        print("Logged out")
    # Create a new response object
    session['logged_in'] = False
    resp_frontend = make_response(render_template( 'search/anonymous.html'))
    resp_frontend.set_cookie('OMD_SESSION_ID', '', expires=0, samesite='Lax')
    return resp_frontend


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        access_token = request.headers.get('Token')
        if access_token:
            #backend_to_backend
            print("Backend to backend")
            if access_token == AUTH_TOKEN:
                session['logged_in'] = True
                if 'access_token' in getfullargspec(f).args:
                    kwargs['access_token'] = access_token
                return f(*args, **kwargs)
            else:
                return render_template('search/anonymous.html')
        else:
            #user_to_backend
            print("User to backend")
            access_token = request.cookies.get('OMD_SESSION_ID')  
            if not access_token:
                session['logged_in'] = False
                return render_template('search/anonymous.html')
            if 'access_token' in getfullargspec(f).args:
                kwargs['access_token'] = access_token
            return f(*args, **kwargs)
    return decorated_function

