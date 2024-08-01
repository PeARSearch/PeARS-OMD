# SPDX-FileCopyrightText: 2023 PeARS Project, <community@pearsproject.org> 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Run a test server.

from app import app
from app import SERVER_HOST


host, port = SERVER_HOST.split(":")
app.run(host=host, port=int(port), debug=True, threaded=True)
