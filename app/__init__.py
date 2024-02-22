# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

import os
import sys
import logging
from pathlib import Path
from os.path import dirname, join, realpath
from codecarbon import EmissionsTracker
from decouple import Config, RepositoryEnv
from dotenv import load_dotenv

# Import flask and template operators
from flask import Flask, render_template, request
from flask_admin import Admin, AdminIndexView

# Import SQLAlchemy
from flask_sqlalchemy import SQLAlchemy

# Initialise emission tracking
CARBON_TRACKING = False
CARBON_DIR = None
tracker = None
if CARBON_TRACKING:
    dir_path = dirname(dirname(realpath(__file__)))
    CARBON_DIR = join(dir_path,'emission_tracking')
    Path(CARBON_DIR).mkdir(exist_ok=True, parents=True)
    tracker = EmissionsTracker(output_dir=CARBON_DIR, project_name="PeARS Lite, OMD emission tracking")

# Get paths to SentencePiece model and vocab
LANG = 'en' # hardcoded for now
SPM_DEFAULT_VOCAB_PATH = f'app/api/models/{LANG}/{LANG}wiki.vocab'
spm_vocab_path = os.environ.get("SPM_VOCAB", SPM_DEFAULT_VOCAB_PATH)
SPM_DEFAULT_MODEL_PATH = f'app/api/models/{LANG}/{LANG}wiki.model'
spm_model_path = os.environ.get("SPM_MODEL", SPM_DEFAULT_MODEL_PATH)

# Make sure user data directories exist
DEFAULT_PATH = f'app'
Path(os.path.join(DEFAULT_PATH,'static/userdata')).mkdir(parents=True, exist_ok=True)

# Define vector size
from app.indexer.vectorizer import read_vocab

print(f"Loading SPM vocab from '{spm_vocab_path}' ...")
vocab, _, _ = read_vocab(spm_vocab_path)
from sklearn.feature_extraction.text import CountVectorizer

print(f"Loading SPM vocab from '{spm_vocab_path}' ...")
vocab, inverted_vocab, logprobs = read_vocab(spm_vocab_path)
vectorizer = CountVectorizer(vocabulary=vocab, lowercase=True, token_pattern='[^ ]+')
VEC_SIZE = len(vocab)

# Assess whether the code is run locally or on the On My Disk server
LOCAL_RUN = os.environ.get("LOCAL_RUN", "false").lower() == "true"

# Read tokens
try:
    DOTENV_FILE = 'app/static/conf/pears.ini'
    env_config = Config(RepositoryEnv(DOTENV_FILE))
    AUTH_TOKEN = env_config.get('AUTH_TOKEN')
except:
    print(">>\tERROR: __init__.py: the pears.ini file is not present in the app/static/conf directory or incorrectly configured")
    sys.exit()

def configure_logging():
    # register root logging
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('werkzeug').setLevel(logging.INFO)


configure_logging()

# Define the WSGI application object
app = Flask(__name__)

# Configurations
app.config.from_object('config')
load_dotenv('app/static/conf/pears.ini')
AUTH_TOKEN = os.getenv('AUTH_TOKEN')
OMD_PATH = os.getenv('OMD_PATH')

# Define the database object which is imported
# by modules and controllers
db = SQLAlchemy(app)


# Import a module / component using its blueprint handler variable (mod_auth)
from app.auth.controllers import auth as auth_module
from app.indexer.controllers import indexer as indexer_module
from app.api.controllers import api as api_module
from app.search.controllers import search as search_module
from app.orchard.controllers import orchard as orchard_module
from app.pages.controllers import pages as pages_module
from app.settings.controllers import settings as settings_module

# Register blueprint(s)
app.register_blueprint(auth_module)
app.register_blueprint(indexer_module)
app.register_blueprint(api_module)
app.register_blueprint(search_module)
app.register_blueprint(orchard_module)
app.register_blueprint(pages_module)
app.register_blueprint(settings_module)
# ..

# Build the database:
# This will create the database file using SQLAlchemy
#db.drop_all()
with app.app_context():
    db.create_all()

from flask_admin.contrib.sqla import ModelView
from app.api.models import Pods, Urls
from app.api.controllers import return_delete

from flask_admin import expose
from flask_admin.contrib.sqla.view import ModelView
from flask_admin.model.template import EndpointLinkRowAction

from app.auth.controllers import login_required
import requests

# Flask and Flask-SQLAlchemy initialization here

class MyAdminIndexView(AdminIndexView):
    def is_accessible(self):
        access_token = request.headers.get('Token')
        if not access_token:     
            access_token = request.cookies.get('OMD_SESSION_ID')  
        if not access_token:
            return False
        if LOCAL_RUN:
            url = 'http://localhost:9191/api' #Local test
        else:
            url = join(OMD_PATH, 'signin/')
        data = {'action': 'getUserInfo', 'session_id': access_token}
        resp = requests.post(url, json=data, headers={'accept':'application/json', 'Authorization': 'token:'+access_token})
        is_admin = False
        if resp.json().get('valid'):
            is_admin = resp.json().get('isAdmin')
        return is_admin # This does the trick rendering the view only if the user is admin


admin = Admin(app, name='PeARS DB', template_mode='bootstrap3', index_view=MyAdminIndexView())

class UrlsModelView(ModelView):
    list_template = 'admin/pears_list.html'
    column_exclude_list = ['vector','cc']
    column_searchable_list = ['url', 'title', 'description', 'pod']
    column_editable_list = ['description']
    can_edit = True
    page_size = 50
    form_widget_args = {
        'vector': {
            'readonly': True
        },
        'date_created': {
            'readonly': True
        },
        'date_modified': {
            'readonly': True
        },
    }
    def delete_model(self, model):
        try:
            self.on_model_delete(model)
            print("DELETING",model.url,model.vector)
            # Add your custom logic here and don't forget to commit any changes e.g.
            print(return_delete(idx=model.vector))
            self.session.commit()
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash(gettext('Failed to delete record. %(error)s', error=str(ex)), 'error')
                log.exception('Failed to delete record.')

            self.session.rollback()

            return False
        else:
            self.after_model_delete(model)

        return True



class PodsModelView(ModelView):
    list_template = 'admin/pears_list.html'
    column_exclude_list = ['DS_vector','word_vector']
    column_searchable_list = ['url', 'name', 'description', 'language']
    can_edit = True
    page_size = 50
    form_widget_args = {
        'DS_vector': {
            'readonly': True
        },
        'word_vector': {
            'readonly': True
        },
        'date_created': {
            'readonly': True
        },
        'date_modified': {
            'readonly': True
        },
    }
    def delete_model(self, model):
        try:
            self.on_model_delete(model)
            print("DELETING",model.name)
            # Add your custom logic here and don't forget to commit any changes e.g.
            print(return_pod_delete(model.name))
            self.session.commit()
        except Exception as ex:
            if not self.handle_view_exception(ex):
                flash(gettext('Failed to delete record. %(error)s', error=str(ex)), 'error')
                log.exception('Failed to delete record.')

            self.session.rollback()

            return False
        else:
            self.after_model_delete(model)

        return True


admin.add_view(PodsModelView(Pods, db.session))
admin.add_view(UrlsModelView(Urls, db.session))


