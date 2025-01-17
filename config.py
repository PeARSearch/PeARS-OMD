# SPDX-FileCopyrightText: 2023 PeARS Project <community@pearsproject.org>
#
# SPDX-License-Identifier: AGPL-3.0-only

from os.path import abspath, dirname, join
from pathlib import Path

# Statement for enabling the development environment
DEBUG = True

# Define the application directory
BASE_DIR = abspath(dirname(__file__))
Path(join(BASE_DIR,'app/db')).mkdir(parents=True, exist_ok=True)

# Define the database - we are working with
# SQLite for this example
SQLALCHEMY_DATABASE_URI = 'sqlite:///' + join(BASE_DIR, 'app/db/app.db')
DATABASE_CONNECT_OPTIONS = {}

THREADS_PER_PAGE = 2
SQLALCHEMY_TRACK_MODIFICATIONS = False

# To ensure utf-8 is handled properly by jsonify
JSON_AS_ASCII = False
# To ensure json preserves order of dictionaries
JSON_SORT_KEYS = False
