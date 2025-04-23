from os.path import join, dirname, realpath
import pytest
from dotenv import load_dotenv
from app import app

dir_path = dirname(dirname(realpath(__file__)))


class TestingUtils:
    # Helper function for checking that an unauthorized page request is handled correctly
    @staticmethod
    def test_authentication_failed(page):
        html = page.data.decode()
        assert page.status_code == 401
        assert "Hey there! You don't seem to be logged in." in html


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