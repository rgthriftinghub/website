from app.models.enums import UserRole
from app.models.store_content import StoreContent
from tests.conftest import create_user, sign_in

def test_store_content_public_and_admin_permissions(client, db):
    page = StoreContent(key="shipping", title="Shipping", body="Manual delivery details")
    db.add(page); db.commit()
    assert client.get("/api/v1/content/shipping").json()["body"] == "Manual delivery details"
    customer, password = create_user(db, UserRole.CUSTOMER)
    sign_in(client, customer.email, password)
    assert client.put("/api/v1/admin/content/shipping", json={"title":"X","body":"Y","enabled":True}).status_code == 403

def test_admin_can_edit_content_and_announcement(admin_client):
    resp = admin_client.put("/api/v1/admin/content/announcement", json={"title":"Announcement","body":"Free delivery today","enabled":True})
    assert resp.status_code == 200, resp.text
    assert admin_client.get("/api/v1/content").json()["announcement"]["body"] == "Free delivery today"

def test_disabled_public_page_is_hidden(client, db):
    db.add(StoreContent(key="privacy", title="Privacy", body="secret", enabled=False)); db.commit()
    assert client.get("/api/v1/content/privacy").status_code == 404
