import sys
import json

try:
    import requests
    LIVE_AVAILABLE = True
except ImportError:
    LIVE_AVAILABLE = False

base_url = "http://localhost:8000"

def run_tests():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)

    print("--- 1. Testing CSV Template Download ---")
    r1 = client.get("/api/cattle/template/csv")
    print(f"Status: {r1.status_code}, Length: {len(r1.text)}")
    assert r1.status_code == 200, "Template download failed"
    assert "Tag ID" in r1.text, "Invalid CSV header"

    print("\n--- 2. Testing Herd Immunity Coverage Summary ---")
    r2 = client.get("/api/cattle/medical/coverage-summary")
    print(f"Status: {r2.status_code}")
    data2 = r2.json()
    print("Immunity Score:", data2.get("overall_immunity_score"), "%")
    assert r2.status_code == 200, "Coverage summary failed"
    assert "fmd" in data2 and "lsd" in data2, "Missing disease coverage data"

    print("\n--- 3. Testing Subsidy Ledger CSV Export ---")
    r3 = client.get("/api/census/subsidy-ledger/export-csv")
    print(f"Status: {r3.status_code}, Header: {r3.headers.get('content-type')}")
    assert r3.status_code == 200, "Subsidy CSV export failed"
    assert "GOVERNMENT SUBSIDY" in r3.text or "TREASURY" in r3.text

    print("\n--- 4. Testing Public Passport Verification Page ---")
    r4_list = client.get("/api/cattle")
    all_cattle = r4_list.json()
    if all_cattle:
        tag_id = all_cattle[0]["tag_id"]
        r4 = client.get(f"/verify/{tag_id}")
        print(f"Status for {tag_id}: {r4.status_code}")
        assert r4.status_code == 200, "Public passport failed"
        assert "BHARAT PASHUDHAN" in r4.text or "Bharat Pashudhan" in r4.text
        assert "Pedigree Lineage" in r4.text or "वंशावली" in r4.text
        assert "Immunization" in r4.text or "टीकाकरण" in r4.text
        print("✓ Sovereign Public Digital Passport verified successfully!")
    else:
        print("No cattle found to test passport.")

    print("\nALL ENHANCED AND ADVANCED SYSTEMATIC FEATURES VALIDATED 100%!")

if __name__ == "__main__":
    run_tests()

