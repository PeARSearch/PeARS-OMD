import os
from os.path import join, dirname, realpath
import requests
import pytest
from dotenv import load_dotenv
from app import app, OMD_PATH

dir_path = dirname(dirname(realpath(__file__)))


class TestingUtils:

    FAKE_OMD_PATH = "https://fakesite.pearsproject.org/"
    real_omd_path = None

    # Helper function for checking that an unauthorized page request is handled correctly
    @staticmethod
    def test_authentication_failed(page):
        html = page.data.decode()
        assert page.status_code == 401
        assert "Hey there! You don't seem to be logged in." in html

    @staticmethod
    def get_omd_session_id():
        url = join(OMD_PATH, 'signin/')
        username = os.environ["TEST_USERNAME"]
        password = os.environ["TEST_PASSWORD"]
        data = {'action': 'signin', 'username': username, 'password': password}
        user_info = requests.post(url, timeout=30, json=data)
        return user_info.json()["session_id"]


    @classmethod
    def set_fake_gateway_path(cls):
        import app.subscriptions.controllers as subscription_controllers
        cls.real_omd_path = subscription_controllers.OMD_PATH
        subscription_controllers.OMD_PATH = cls.FAKE_OMD_PATH

    @classmethod
    def unset_fake_gateway_path(cls):
        import app.subscriptions.controllers as subscription_controllers
        subscription_controllers.OMD_PATH = cls.real_omd_path


@pytest.fixture
def client():
    """Configures the app for testing
    Sets app config variable ``TESTING`` to ``True``
    :return: App for testing
    """

    app.config['TESTING'] = True
    client = app.test_client()
    
    load_dotenv(join(dir_path, 'conf', 'test.pears.ini'))

    yield client


@pytest.fixture
def utils():
    return TestingUtils