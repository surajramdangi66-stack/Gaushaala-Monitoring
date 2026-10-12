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
    reload_flag = os.environ.get("RELOAD", "true").lower() in ("true", "1", "yes")
    uvicorn.run("backend.app.main:app", host=host, port=port, reload=reload_flag, log_level="info")
