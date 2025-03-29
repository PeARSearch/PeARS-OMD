from os.path import join, dirname, realpath
import pytest
from dotenv import load_dotenv
from app import app

dir_path = dirname(dirname(realpath(__file__)))

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

