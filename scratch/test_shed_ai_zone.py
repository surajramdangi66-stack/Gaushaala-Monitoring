import os
import sys
import numpy as np
import cv2

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.vision.spatial import SpatialZone, SpatialAnalytics, analyze_trough_visual_density
from backend.app.vision.shed_ai_zone import ShedAIZoneManager
from backend.app.db.database import init_db, SessionLocal
from backend.app.db.models import CVODispatchModel, FodderSubsidyDailyModel, ShedZoneConfigModel

def run_tests():
    print("=" * 60)
    print("TESTING BAADA & SHED AI ZONE: CORE VISION & GOVERNANCE MODULES")
    print("=" * 60)

    # 1. Database Init
    init_db()
    print(">>> [PASS] Database schema initialized with ShedZone & CVO models.")

    # 2. Spatial Geofencing (4 Zones)
    zones_config = {
        "feeder": {
            "name": "Feeder Trough (चारा चरणी)",
            "name_hi": "चारा चरणी क्षेत्र",
            "polygon": [[100, 330], [540, 330], [540, 440], [100, 440]],
            "max_capacity": 4,
            "color": "#10b981"
        },
        "resting": {
            "name": "Resting Bay (विश्राम शेड)",
            "name_hi": "विश्राम एवं जुगाली शेड",
            "polygon": [[50, 90], [360, 90], [360, 300], [50, 300]],
            "max_capacity": 10,
            "color": "#3b82f6"
        },
        "quarantine": {
            "name": "Quarantine Ward (क्वारंटीन वार्ड)",
            "name_hi": "पृथक / चिकित्सा वार्ड",
            "polygon": [[400, 70], [590, 70], [590, 230], [400, 230]],
            "max_capacity": 2,
            "color": "#f59e0b"
        },
        "boundary": {
            "name": "Pen Perimeter (बाड़ा सुरक्षा सीमा)",
            "name_hi": "बाड़ा सुरक्षा सीमा",
            "polygon": [[30, 40], [610, 40], [610, 460], [30, 460]],
            "color": "#ef4444"
        }
    }

    spatial = SpatialAnalytics(zones_config)
    assert spatial.is_in_feeder(200, 350) == True, "Point should be inside feeder"
    assert spatial.is_in_feeder(50, 50) == False, "Point should not be in feeder"
    assert spatial.is_in_quarantine(450, 100) == True, "Point should be inside quarantine"
    assert spatial.is_in_resting_bay(100, 150) == True, "Point should be inside resting bay"
    assert spatial.check_geofence_breach(10, 10) == True, "Point outside boundary should be flagged breach"
    assert spatial.check_geofence_breach(200, 200) == False, "Point inside boundary should not be breach"
    print(">>> [PASS] Spatial 4-Zone Point-in-Polygon tests passed.")

    # 3. Virtual Tripwire Test on Quarantine
    crossing = spatial.check_quarantine_tripwire(prev_x=350, prev_y=100, curr_x=450, curr_y=100)
    assert crossing == "UNAUTHORIZED_ENTRY", f"Expected UNAUTHORIZED_ENTRY, got {crossing}"
    print(">>> [PASS] Quarantine Virtual Tripwire crossing test passed.")

    # 4. Trough Visual Density / Pixel Analysis Test
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Draw green grass & hay in trough area
    cv2.rectangle(test_frame, (120, 340), (500, 430), (35, 180, 60), -1)  # Green fodder
    cv2.rectangle(test_frame, (200, 360), (350, 420), (20, 150, 210), -1)  # Golden hay

    density = spatial.analyze_trough(test_frame)
    print(f"    Trough Fill Percent: {density['fill_percent']}% | Status: {density['status']}")
    assert density["fill_percent"] > 50.0, "Fodder should be detected with high fill percentage"
    assert density["is_empty"] == False, "Trough should not be declared empty"
    print(">>> [PASS] Feeder Trough visual pixel density analysis test passed.")

    # 5. ShedAIZoneManager
    shed_mgr = ShedAIZoneManager.get_instance("cam-01", "बाड़ा 1: मुख्य शेड", spatial)
    
    # Mock Track
    class MockTrack:
        def __init__(self, tid, cx, cy, label="COW-101", state="active"):
            self.track_id = tid
            self.cx = cx
            self.cy = cy
            self.label = label
            self.activity_state = state
            self.inactivity_duration = 0.0
            self.centroid_history = [(cx-5, cy-5), (cx, cy)]
            self.bbox = [cx-20, cy-30, cx+20, cy+30]
            self.is_worker = False
            self.is_calf = False

    t1 = MockTrack(101, 200, 350, label="COW-101", state="active")  # in feeder
    t2 = MockTrack(102, 120, 150, label="COW-102", state="resting") # in resting
    t3 = MockTrack(103, 450, 100, label="COW-103", state="active")  # in quarantine (unauthorized!)

    # Feeding attendance
    feed_res = shed_mgr.process_feeder_attendance([t1, t2, t3], test_frame, now=100.0)
    assert feed_res["active_feeding_count"] == 1, "Should have 1 active feeder"
    print(">>> [PASS] Feeder Attendance accumulation test passed.")

    # Quarantine breach detection
    breaches = shed_mgr.check_quarantine_tripwire_breaches([t1, t2, t3], test_frame, alert_engine=None)
    assert len(breaches) >= 1, "Should detect unauthorized intrusion into quarantine"
    assert breaches[0]["alert_type"] == "QUARANTINE_INTRUSION"
    print(f">>> [PASS] Quarantine Breach Alert detected: {breaches[0]['message']}")

    # Resting & Rumination motion score
    rum_res = shed_mgr.process_resting_and_rumination([t1, t2, t3], now=100.0)
    assert rum_res["resting_count"] == 1
    print(f">>> [PASS] Rumination Score: {rum_res['average_rumination_score']}% ({rum_res['rumination_status']})")

    # NDLM 12-Digit Tag Mapping
    ndlm_maps = shed_mgr.update_tag_zone_mappings([t1, t2, t3], test_frame)
    assert len(ndlm_maps) == 3
    for m in ndlm_maps:
        parts = m["ndlm_uid"].split(" ")
        assert len(parts) == 3, f"NDLM UID should be 12 digits (4-4-4 format), got {m['ndlm_uid']}"
        assert len(parts[0]) == 4 and len(parts[1]) == 4 and len(parts[2]) == 4
    print(f">>> [PASS] NDLM 12-digit Tag UIDs generated & verified: {[m['ndlm_uid'] for m in ndlm_maps]}")

    # Government Fodder Subsidy Calculation
    shed_mgr.record_attendance_sample(total_cattle=18, cows=12, bulls=2, calves=4, sick=2)
    sub = shed_mgr.compute_subsidy_metrics()
    daily_claim = sub["subsidy_claim_inr"]["daily_total_inr"]
    assert daily_claim > 500.0, f"Expected > 500 claim, got {daily_claim}"
    print(f">>> [PASS] Fodder Subsidy Claim calculated: Rs. {daily_claim}/day (Monthly: Rs. {sub['subsidy_claim_inr']['monthly_projected_inr']})")

    # CVO Outbreak Dispatch
    cvo_rec = shed_mgr.dispatch_cvo_outbreak_alert(
        event_type="DISEASE_OUTBREAK_SUSPECTED",
        message="2 cows in quarantine showing high fever & salivation",
        affected_tags=["COW-104", "COW-109"],
        severity="CRITICAL"
    )
    assert cvo_rec["id"].startswith("CVO-")
    assert cvo_rec["cvo_status"] == "DISPATCHED"
    print(f">>> [PASS] CVO Emergency Alert successfully dispatched: ID {cvo_rec['id']}")

    # 6. Test FastAPI Client
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)

    # Test analytics endpoint
    res = client.get("/api/shed-ai/cam-01/analytics")
    assert res.status_code == 200, f"Failed analytics: {res.text}"
    data = res.json()
    assert "trough_monitoring" in data
    assert "quarantine_ward" in data
    assert "resting_rumination_analytics" in data
    assert "ndlm_tag_mappings" in data
    assert "government_fodder_subsidy" in data
    print(">>> [PASS] GET /api/shed-ai/cam-01/analytics returned 200 OK with all required modules.")

    # Test preset endpoint
    res_preset = client.post("/api/shed-ai/cam-01/presets/standard")
    assert res_preset.status_code == 200
    print(">>> [PASS] POST /api/shed-ai/cam-01/presets/standard returned 200 OK.")

    # Test subsidy export HTML
    res_html = client.get("/api/shed-ai/cam-01/subsidy/export?format=html")
    assert res_html.status_code == 200
    assert "सरकारी चारा अनुदान" in res_html.text
    print(">>> [PASS] GET /api/shed-ai/cam-01/subsidy/export?format=html generated official audit report.")

    print("=" * 60)
    print("ALL 9 TEST SUITES COMPLETED WITH 100% SUCCESS!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
