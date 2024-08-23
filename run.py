# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Run a test server.
import os

from app import app
from app import SERVER_HOST

if os.getenv("FLASK_ENV") == "development":
    debug_mode = True
else:
    debug_mode = False

host, port = SERVER_HOST.split(":")
app.run(host=host, port=int(port), debug=debug_mode, threaded=True)
