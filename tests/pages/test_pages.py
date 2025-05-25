from tests import client


def test_acknowledgements_page(client):
    page = client.get("/acknowledgements/")
    html = page.data.decode()
    assert "<h3>Acknowledgements</h3>" in html
    assert page.status_code == 200

def test_contact_page(client):
    page = client.get("/contact/")
    html = page.data.decode()
    assert "<h3>Contact</h3>" in html
    assert page.status_code == 200

