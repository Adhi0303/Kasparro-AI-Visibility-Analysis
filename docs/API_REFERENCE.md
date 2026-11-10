# REST API Reference & Integration Guide

The service exposes a versioned REST API built on FastAPI. Interactive OpenAPI/Swagger documentation is served at `/docs` when the server is running.

## 1. Authentication & Role-Based Access Control (RBAC)

Authentication is enforced via Bearer Tokens passed in the `Authorization` header:

```http
Authorization: Bearer <TOKEN>
```

| Role | Static Token Setting | Permitted Operations |
| :--- | :--- | :--- |
| **Analyst** | `ANALYST_TOKEN` | Import datasets, trigger analyses, poll status, create/edit draft reports, submit reports. |
| **Reviewer** | `REVIEWER_TOKEN` | Review submitted reports, approve or reject report versions. |
| **Analyst or Reviewer** | Either Token | Health checks, inspect analysis status, export approved immutable reports. |

> [!CAUTION]
> Caller roles are **strictly derived on the server** from token validation. Client request payloads cannot inject, override, or spoof actor permissions. An Analyst attempting to submit a review decision receives `HTTP 403 Forbidden`.

---

## 2. API Endpoints

### 1. System Health Check
* **Endpoint:** `GET /health`
* **Auth:** None (Public)
* **Response:**
  ```json
  {
    "status": "ok",
    "version": "1.0.0"
  }
  ```

---

### 2. Import Dataset
* **Endpoint:** `POST /datasets`
* **Auth:** `require_analyst`
* **Request Body:**
  ```json
  {
    "dataset_name": "kasparro-july-2026-snapshot",
    "source_directory": "data"
  }
  ```
* **Response (HTTP 200):**
  ```json
  {
    "dataset_id": "cfc212e3-7412-4df9-857f-47403b6b2112",
    "dataset_name": "kasparro-july-2026-snapshot",
    "imported_prompts": 50,
    "imported_responses": 150,
    "imported_citations": 2439,
    "invalid_records": [],
    "validation_status": "valid"
  }
  ```

---

### 3. Trigger Visibility Analysis
* **Endpoint:** `POST /analyses`
* **Auth:** `require_analyst`
* **Request Body:**
  ```json
  {
    "dataset_id": "cfc212e3-7412-4df9-857f-47403b6b2112",
    "execution_mode": "replay",
    "classifier_version": "v1",
    "scoring_version": "v1"
  }
  ```
* **Response (HTTP 200):**
  ```json
  {
    "analysis_id": "884808aa-f87b-440f-8cc7-267af6f8b32e",
    "dataset_id": "cfc212e3-7412-4df9-857f-47403b6b2112",
    "status": "completed",
    "total_eligible": 150,
    "successful_count": 150,
    "failed_count": 0,
    "skipped_count": 0
  }
  ```

---

### 4. Poll Analysis Status & Results
* **Endpoint:** `GET /analyses/{id}`
* **Auth:** `require_analyst_or_reviewer`
* **Response (HTTP 200):**
  ```json
  {
    "analysis_id": "884808aa-f87b-440f-8cc7-267af6f8b32e",
    "status": "completed",
    "total_eligible": 150,
    "successful_count": 150,
    "failed_count": 0,
    "skipped_count": 0,
    "overall": {
      "mean_score": 33.04,
      "distribution": {
        "inclusion_rate": 0.48,
        "recommendation_rate": 0.06,
        "negative_rate": 0.0333
      }
    },
    "engine_aggregates": {
      "gemini": { "mean_score": 34.93, "distribution": { "inclusion_rate": 0.44, "recommendation_rate": 0.12, "negative_rate": 0.0 } },
      "chatgpt": { "mean_score": 31.43, "distribution": { "inclusion_rate": 0.50, "recommendation_rate": 0.02, "negative_rate": 0.06 } },
      "aimode": { "mean_score": 32.75, "distribution": { "inclusion_rate": 0.50, "recommendation_rate": 0.04, "negative_rate": 0.04 } }
    }
  }
  ```

---

### 5. Create Draft Report
* **Endpoint:** `POST /reports?dataset_id={dataset_id}&analysis_id={analysis_id}`
* **Auth:** `require_analyst`
* **Response (HTTP 200):**
  ```json
  {
    "report_id": "92ec0a1a-466a-4d29-ae1e-450f3b92f70b",
    "dataset_id": "cfc212e3-7412-4df9-857f-47403b6b2112",
    "current_draft_version_id": "85bd59bc-5b48-438d-8d54-c6fdb8969a47",
    "status": "DRAFT",
    "version_number": 1
  }
  ```

---

### 6. Edit Draft Report
* **Endpoint:** `PATCH /reports/{id}`
* **Auth:** `require_analyst`
* **Request Body:**
  ```json
  {
    "diagnostics": [...],
    "remedies": [...]
  }
  ```
* **Response (HTTP 200):** Returns updated draft report with updated SHA-256 content hash.

---

### 7. Submit Report for Review
* **Endpoint:** `POST /reports/{id}/submit`
* **Auth:** `require_analyst`
* **Response (HTTP 200):**
  ```json
  {
    "report_id": "92ec0a1a-466a-4d29-ae1e-450f3b92f70b",
    "version_id": "85bd59bc-5b48-438d-8d54-c6fdb8969a47",
    "status": "SUBMITTED",
    "version_number": 1,
    "submitted_at": "2026-10-28T18:00:00Z"
  }
  ```

---

### 8. Reviewer Decision (Approve / Reject)
* **Endpoint:** `POST /reports/{id}/decision`
* **Auth:** `require_reviewer` (Analysts receive HTTP 403)
* **Request Body:**
  ```json
  {
    "version_id": "85bd59bc-5b48-438d-8d54-c6fdb8969a47",
    "decision": "approve",
    "comment": "Verified 150 responses against evidence quotes. Approved for distribution."
  }
  ```
* **Response (HTTP 200):**
  ```json
  {
    "decision_id": "c1f72834-8849-4eb5-b2be-a3779e39404d",
    "report_id": "92ec0a1a-466a-4d29-ae1e-450f3b92f70b",
    "version_id": "85bd59bc-5b48-438d-8d54-c6fdb8969a47",
    "status": "APPROVED",
    "reviewer_id": "dev-reviewer",
    "comment": "Verified 150 responses against evidence quotes. Approved for distribution."
  }
  ```

---

### 9. Export Approved Report
* **Endpoint:** `GET /reports/{id}/export`
* **Auth:** `require_analyst_or_reviewer`
* **Gate Enforcement:**
  * If report is `DRAFT` $\rightarrow$ **HTTP 400 Bad Request**
  * If report is `SUBMITTED` $\rightarrow$ **HTTP 400 Bad Request**
  * If report was edited after approval $\rightarrow$ **HTTP 400 Bad Request**
  * If report is `APPROVED` $\rightarrow$ **HTTP 200 OK**
* **Response (HTTP 200):** Returns complete immutable report payload with cryptographic content hash, audit history, diagnostics, remedies, and aggregate scores.

---

## 3. End-to-End Command Line Flow (cURL)

```bash
# 1. Import
curl -X POST http://127.0.0.1:8000/datasets \
  -H "Authorization: Bearer dev-analyst-token" \
  -H "Content-Type: application/json" \
  -d '{"dataset_name": "live-test", "source_directory": "data"}'

# 2. Analyze
curl -X POST http://127.0.0.1:8000/analyses \
  -H "Authorization: Bearer dev-analyst-token" \
  -H "Content-Type: application/json" \
  -d '{"dataset_id": "<DATASET_ID>", "execution_mode": "replay"}'

# 3. Create Report & Submit
curl -X POST "http://127.0.0.1:8000/reports?dataset_id=<DATASET_ID>&analysis_id=<ANALYSIS_ID>" \
  -H "Authorization: Bearer dev-analyst-token"
curl -X POST http://127.0.0.1:8000/reports/<REPORT_ID>/submit \
  -H "Authorization: Bearer dev-analyst-token"

# 4. Reviewer Approval
curl -X POST http://127.0.0.1:8000/reports/<REPORT_ID>/decision \
  -H "Authorization: Bearer dev-reviewer-token" \
  -H "Content-Type: application/json" \
  -d '{"version_id": "<VERSION_ID>", "decision": "approve", "comment": "Approved"}'

# 5. Export
curl -X GET http://127.0.0.1:8000/reports/<REPORT_ID>/export \
  -H "Authorization: Bearer dev-analyst-token"
```

