from flask_wtf import FlaskForm
from wtforms import SubmitField, StringField, PasswordField, SelectMultipleField, widgets
from wtforms.validators import DataRequired, url

class ChoiceObj(object):
    def __init__(self, name, choices):
        # this is needed so that BaseForm.process will accept the object for the named form,
        # and eventually it will end up in SelectMultipleField.process_data and get assigned
        # to .data
        setattr(self, name, choices)

class MultiCheckboxField(SelectMultipleField):
    widget = widgets.TableWidget()
    option_widget = widgets.CheckboxInput()

class SearchForm(FlaskForm):
      query = StringField("", [DataRequired()])
  
class LoginForm(FlaskForm):
    username = StringField('Username', [DataRequired()])
    password = PasswordField('Password', [DataRequired()])

class IndexerForm(FlaskForm):
    url = StringField('The url to index from', [DataRequired(), url()], description="https://onmydisk.net/username/devicename/")

class DeviceForm(FlaskForm):
    devices = MultiCheckboxField(None)

class GroupForm(FlaskForm):
    groups = MultiCheckboxField(None)
