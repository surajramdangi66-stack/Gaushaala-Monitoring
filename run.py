import uvicorn
import os
import sys

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    print(f"================================================================")
    print(f"  SMART GAUSHALA CCTV AI LIVESTOCK SURVEILLANCE PLATFORM")
    print(f"  Access UI at: http://localhost:{port}")
    print(f"  Default Credentials: admin / gaushala2026")
    print(f"================================================================")
    uvicorn.run("backend.app.main:app", host=host, port=port, reload=False, log_level="info")
