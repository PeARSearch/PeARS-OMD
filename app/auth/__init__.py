# SPDX-FileCopyrightText: 2024 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# dictionary mapping view function names to information about access requirements
# the dictionary is compiled at runtime from the login_required decorator
# solution inspired by https://stackoverflow.com/a/34664604
# example: {"indexer.index"}

VIEW_FUNCTIONS_PERMISSIONS = {}