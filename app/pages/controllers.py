# SPDX-FileCopyrightText: 2022 PeARS Project, <community@pearsproject.org>, 
#
# SPDX-License-Identifier: AGPL-3.0-only

# Import flask dependencies
from flask import Blueprint, render_template

from app.api.models import Pods

# Define the blueprint:
pages = Blueprint('pages', __name__, url_prefix='')


@pages.route('/acknowledgements/')
def return_acknowledgements():
    return render_template("pages/acknowledgements.html")

@pages.route('/contact/')
def return_contact():
    return render_template("pages/contact.html")
