import os
import sys
import unittest
import tempfile
import asyncio
import uuid

# Ensure project root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.database import get_db, init_db, SessionLocal, engine, Base
from backend.app.db.models import CattleModel, CensusRecordModel, FeedingScheduleModel, FeedingObservationModel, AlertModel, UserModel
from backend.app.auth import verify_password, create_access_token


class TestGaushalaSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize test database tables
        init_db()
        cls.client = TestClient(app)
        
        # Authenticate via official endpoint
        res = cls.client.post("/api/auth/login", json={"username": "admin", "password": "gaushala2026"})
        token_data = res.json()
        token = token_data.get("access_token") or token_data.get("token")
        cls.headers = {"Authorization": f"Bearer {token}"}

    def test_01_health_and_root(self):
        """Test API health check endpoint"""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertEqual(data.get("service"), "gaushala-ai-cctv")

    def test_02_cattle_registry_crud(self):
        """Test Cattle Registry CRUD endpoints with database persistence"""
        unique_tag = f"TEST-GIR-{uuid.uuid4().hex[:6]}"
        # 1. Create a cattle head
        new_cow = {
            "tag_id": unique_tag,
            "name": "Nandini",
            "enclosure_id": "cam-01",
            "breed": "Gir",
            "notes": "Healthy purebred Gir cow"
        }
        res_post = self.client.post("/api/cattle", json=new_cow, headers=self.headers)
        self.assertEqual(res_post.status_code, 201)
        created = res_post.json()
        cow_id = created["id"]
        self.assertEqual(created["tag_id"], unique_tag)
        self.assertEqual(created["status"], "active")

        # 2. Get list of cattle
        res_list = self.client.get("/api/cattle", headers=self.headers)
        self.assertEqual(res_list.status_code, 200)
        items = res_list.json()
        self.assertTrue(any(c["id"] == cow_id for c in items))

        # 3. Get Herd Summary
        res_summary = self.client.get("/api/cattle/summary", headers=self.headers)
        self.assertEqual(res_summary.status_code, 200)
        summary = res_summary.json()
        self.assertGreaterEqual(summary["total_registered"], 1)
        self.assertGreaterEqual(summary["active_herd"], 1)

        # 4. Toggle Status to Inactive
        res_patch = self.client.patch(f"/api/cattle/{cow_id}/status", headers=self.headers)
        self.assertEqual(res_patch.status_code, 200)
        updated = res_patch.json()
        self.assertEqual(updated["status"], "inactive")

        # 5. Delete cattle
        res_del = self.client.delete(f"/api/cattle/{cow_id}", headers=self.headers)
        self.assertEqual(res_del.status_code, 204)

    def test_03_census_routes(self):
        """Test Herd Census Summary, Diagnostic Execution, and History"""
        unique_tag = f"TEST-CENSUS-{uuid.uuid4().hex[:6]}"
        # Register one cattle head to test baseline
        cow_payload = {
            "tag_id": unique_tag,
            "name": "Surabhi",
            "enclosure_id": "cam-01",
            "breed": "Sahiwal"
        }
        res_c = self.client.post("/api/cattle", json=cow_payload, headers=self.headers)
        self.assertEqual(res_c.status_code, 201)
        cow_id = res_c.json()["id"]

        # 1. Check Census Summary / Latest
        res_sum = self.client.get("/api/census/latest", headers=self.headers)
        self.assertEqual(res_sum.status_code, 200)
        summary = res_sum.json()
        self.assertIn("active_registered_herd", summary)
        self.assertIn("next_scheduled_run", summary)
        self.assertGreaterEqual(summary["active_registered_herd"], 1)

        # 2. Run On-Demand Diagnostic Census
        res_diag = self.client.post(
            "/api/census/run-diagnostic",
            json={"camera_id": "cam-01", "capture_window_seconds": 1.0},
            headers=self.headers
        )
        self.assertEqual(res_diag.status_code, 200)
        diag = res_diag.json()
        self.assertIn("detected_count", diag)
        self.assertIn("expected_count", diag)

        # 3. Check Census History
        res_hist = self.client.get("/api/census/history", headers=self.headers)
        self.assertEqual(res_hist.status_code, 200)
        history = res_hist.json()
        self.assertIn("records", history)
        self.assertGreater(len(history["records"]), 0)

        # Cleanup test cattle
        self.client.delete(f"/api/cattle/{cow_id}", headers=self.headers)

    def test_04_feeding_compliance_routes(self):
        """Test Feeding Schedules and Compliance Inspection"""
        # 1. Get feeding schedules
        res_sched = self.client.get("/api/feeding/schedules", headers=self.headers)
        self.assertEqual(res_sched.status_code, 200)
        scheds = res_sched.json()
        self.assertIsInstance(scheds, list)
        self.assertGreater(len(scheds), 0)

        # 2. Check Feeding Compliance
        res_chk = self.client.post(
            "/api/feeding/check-now",
            json={"camera_id": "cam-01", "trough_name": "Feeder Trough A"},
            headers=self.headers
        )
        self.assertEqual(res_chk.status_code, 200)
        chk = res_chk.json()
        self.assertIn("status", chk)

        # 3. Get Feeding Observations
        res_obs = self.client.get("/api/feeding/observations", headers=self.headers)
        self.assertEqual(res_obs.status_code, 200)
        obs = res_obs.json()
        self.assertIsInstance(obs, list)

    def test_05_auth_flow(self):
        """Test User login authentication with database persistence"""
        # Sign in with default supervisor account
        login_payload = {
            "username": "admin",
            "password": "gaushala2026"
        }
        res_login = self.client.post("/api/auth/login", json=login_payload)
        self.assertEqual(res_login.status_code, 200)
        data = res_login.json()
        self.assertTrue("access_token" in data or "token" in data)
        self.assertEqual(data["user"]["username"], "admin")


if __name__ == "__main__":
    unittest.main()
