# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import isdir, exists
from glob import glob
import sentencepiece as spm
from app import db

sp = spm.SentencePieceProcessor()

def get_installed_languages():
    installed_languages = []
    language_paths = glob('./app/api/models/*/')
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
    date_created = db.Column(db.DateTime, default=db.func.current_timestamp())
    date_modified = db.Column(
        db.DateTime,
        default=db.func.current_timestamp(),
        onupdate=db.func.current_timestamp())


class Urls(Base):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(1000))
    title = db.Column(db.String(1000))
    vector = db.Column(db.String(7000))
    snippet = db.Column(db.String(1000))
    cc = db.Column(db.Boolean)
    pod = db.Column(db.String(1000))
    description = db.Column(db.String(1000))

    def __init__(self,
                 url=None,
                 title=None,
                 vector=None,
                 snippet=None,
                 cc=False,
                 pod=None,
                 description=None):
        self.url = url
        self.title = title
        self.vector = vector
        self.snippet = snippet
        self.cc = cc
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
            'cc': self.cc,
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
    DS_vector = db.Column(db.String(7000))
    word_vector = db.Column(db.String(7000))
    registered = db.Column(db.Boolean)

    def __init__(self,
                 name=None,
                 url=None,
                 description=None,
                 language=None,
                 DS_vector=None,
                 word_vector=None,
                 registered=False):
        self.name = name
        self.url = url
        self.description = description
        self.language = language

    @property
    def serialize(self):
        return {
            'name': self.name,
            'url': self.url,
            'description': self.description,
            'language': self.language,
            'DSvector': self.DS_vector,
            'wordvector': self.word_vector,
            'registered': self.registered
        }

