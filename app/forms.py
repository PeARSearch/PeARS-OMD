from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, url

class LoginForm(FlaskForm):
    username = StringField('Username', [DataRequired()])
    password = PasswordField('Password', [DataRequired()])

class IndexerForm(FlaskForm):
    url = StringField('The url to index from', [DataRequired(), url()], description="https://onmydisk.net/username/devicename/")
