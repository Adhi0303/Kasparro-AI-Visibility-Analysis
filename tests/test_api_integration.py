import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.config import get_settings


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1.0.0"}


def test_api_full_workflow(client):
    settings = get_settings()
    analyst_headers = {"Authorization": f"Bearer {settings.ANALYST_TOKEN}"}
    reviewer_headers = {"Authorization": f"Bearer {settings.REVIEWER_TOKEN}"}
    bad_headers = {"Authorization": "Bearer bad-token"}

    # 1. Dataset import without auth -> 401
    resp = client.post("/datasets", json={"dataset_name": "api-test", "source_directory": "data"})
    assert resp.status_code == 401

    # Dataset import with reviewer -> 403 (analyst required)
    resp = client.post("/datasets", headers=reviewer_headers, json={"dataset_name": "api-test", "source_directory": "data"})
    assert resp.status_code == 403

    # Dataset import with analyst -> 200
    resp = client.post("/datasets", headers=analyst_headers, json={"dataset_name": "api-test", "source_directory": "data"})
    assert resp.status_code == 200
    dataset_id = resp.json()["dataset_id"]
    assert resp.json()["imported_responses"] == 150

    # 2. Start analysis
    resp = client.post("/analyses", headers=analyst_headers, json={"dataset_id": dataset_id, "execution_mode": "replay"})
    assert resp.status_code == 200
    analysis_id = resp.json()["analysis_id"]

    # 3. Get analysis status
    resp = client.get(f"/analyses/{analysis_id}", headers=analyst_headers)
    assert resp.status_code == 200
    status_data = resp.json()
    assert status_data["total_eligible"] == 150
    assert "chatgpt" in status_data["engine_aggregates"]

    # 4. Create report
    resp = client.post(f"/reports?dataset_id={dataset_id}&analysis_id={analysis_id}", headers=analyst_headers)
    assert resp.status_code == 200
    report_id = resp.json()["report_id"]

    # 5. Analyst attempts review decision -> 403 (Wrong role)
    v1_id = resp.json()["current_draft_version_id"]
    resp = client.post(
        f"/reports/{report_id}/decision",
        headers=analyst_headers,
        json={"version_id": v1_id, "decision": "approve", "comment": "Analyst approving own report"}
    )
    assert resp.status_code == 403

    # 6. Analyst submits draft report
    resp = client.post(f"/reports/{report_id}/submit", headers=analyst_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "SUBMITTED"

    # 7. Attempt export while SUBMITTED -> 400
    resp = client.get(f"/reports/{report_id}/export", headers=analyst_headers)
    assert resp.status_code == 400

    # 8. Reviewer approves report
    resp = client.post(
        f"/reports/{report_id}/decision",
        headers=reviewer_headers,
        json={"version_id": v1_id, "decision": "approve", "comment": "Approved by reviewer"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"

    # 9. Export approved report -> 200
    resp = client.get(f"/reports/{report_id}/export", headers=analyst_headers)
    assert resp.status_code == 200
    export_payload = resp.json()
    assert export_payload["export_status"] == "exported"
    assert len(export_payload["content"]["diagnostics"]) == 3
    assert len(export_payload["content"]["remedies"]) == 3

