# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import isdir, exists, join, dirname, realpath
from glob import glob
from datetime import datetime
import sentencepiece as spm
from app import db, GATEWAY_TIMEZONE

sp = spm.SentencePieceProcessor()

dir_path = dirname(dirname(realpath(__file__)))

def get_installed_languages():
    installed_languages = []
    language_paths = glob(join(dir_path, 'api/models/*/'))
    for p in language_paths:
        lang = p[:-1].split('/')[-1]
        installed_languages.append(lang)
    print("Installed languages:",installed_languages)
    return installed_languages

installed_languages = get_installed_languages()


# Define a base model for other database tables to inherit
class Base(db.Model):

    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow())
    date_modified = db.Column(
        db.DateTime,
        default=datetime.utcnow(),
        onupdate=datetime.utcnow())


class Urls(Base):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(1000))
    title = db.Column(db.String(1000))
    vector = db.Column(db.Integer)
    snippet = db.Column(db.String(1000))
    pod = db.Column(db.String(1000))
    description = db.Column(db.String(1000))

    def __init__(self,
                 url=None,
                 title=None,
                 vector=None,
                 snippet=None,
                 pod=None,
                 description=None):
        self.url = url
        self.title = title
        self.vector = vector
        self.snippet = snippet
        self.pod = pod
        self.description = description

    def __repr__(self):
        return self.url

    @property
    def serialize(self):
        return {
            'id': self.id,
            'url': self.url,
            'title': self.title,
            'vector': self.vector,
            'snippet': self.snippet,
            'pod': self.pod,
            'notes': self.description
        }

    def as_dict(self):
       return {c.name: str(getattr(self, c.name)) for c in self.__table__.columns}


class Pods(Base):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1000))
    url = db.Column(db.String(1000))
    description = db.Column(db.String(7000))
    language = db.Column(db.String(1000))
    owner = db.Column(db.String(2000))

    def __init__(self,
                 name=None,
                 url=None,
                 description=None,
                 language=None,
                 owner=None):
        self.name = name
        self.url = url
        self.description = description
        self.language = language
        self.owner = owner

    @property
    def serialize(self):
        return {
            'name': self.name,
            'url': self.url,
            'description': self.description,
            'language': self.language,
            'owner': self.owner
        }

    def as_dict(self):
       return {c.name: str(getattr(self, c.name)) for c in self.__table__.columns}


class Locations(Base):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1000))
    device = db.Column(db.Boolean)
    subscribed = db.Column(db.Boolean)

    def __init__(self, name=None, device=False, subscribed=False):
        self.name = name
        self.device = device
        self.subscribed = subscribed

    @property
    def serialize(self):
            return {
                'name': self.name,
                'device': self.device,
                'subscribed': self.subscribed
                }

    def as_dict(self):
       return {c.name: str(getattr(self, c.name)) for c in self.__table__.columns}


class Groups(Base):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(1000))
    identifier = db.Column(db.String(64))
    subscribed = db.Column(db.Boolean)

    def __init__(self, name=None, identifier=None, subscribed=False):
        self.name = name
        self.identifier = identifier
        self.subscribed = subscribed

    @property
    def serialize(self):
            return {
                'name': self.name,
                'identifier': self.identifier,
                'subscribed': self.subscribed
                }

    def as_dict(self):
       return {c.name: str(getattr(self, c.name)) for c in self.__table__.columns}


class Sites(Base):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(1000))
    name = db.Column(db.String(200))
    title = db.Column(db.String(1000))
    description = db.Column(db.String(1000))
    owner = db.Column(db.String(100))
    subscribed = db.Column(db.Boolean)

    def __init__(self, url=None, name=None, title=None, description=None, owner=False, subscribed=False):
        self.url = url
        self.name = name
        self.title = title
        self.description = description
        self.owner = owner
        self.subscribed = subscribed

    @property
    def serialize(self):
            return {
                'url': self.url,
                'name': self.name,
                'title': self.title,
                'description': self.description,
                'owner': self.owner,
                'subscribed': self.subscribed
                }

    def as_dict(self):
       return {c.name: str(getattr(self, c.name)) for c in self.__table__.columns}

