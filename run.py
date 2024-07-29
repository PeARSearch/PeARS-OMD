# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Run a test server.
import os

from app import app

if os.getenv("FLASK_ENV") == "development":
    debug_mode = True
else:
    debug_mode = False

app.run(host='0.0.0.0', port=9090, debug=debug_mode, threaded=True)
