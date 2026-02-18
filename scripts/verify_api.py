import asyncio
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Add the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from fastapi import FastAPI
from core.api.app import create_app
from core.config import get_config

async def verify_api():
    print("🚀 Starting API Verification...")
    
    try:
        # 1. Load configuration
        print("📦 Loading configuration...")
        config = get_config()
        print(f"✅ Configuration loaded: {config.app.name} v{config.app.version}")
        
        # 2. Initialize App
        print("🔧 Creating FastAPI app...")
        app = create_app(config)
        print("✅ FastAPI app created successfully")
        
        # 3. Check Routes
        print("🔍 Checking registered routes...")
        routes = [route.path for route in app.routes]
        expected_routes = [
            "/health",
            "/api/info",
            "/api/devices",
            "/api/agents/register",
            "/api/agents/heartbeat",
            "/api/audit/run",
            "/api/credentials"
        ]
        
        missing_routes = [r for r in expected_routes if not any(r in route for route in routes)]
        
        if missing_routes:
            print(f"❌ Missing routes: {missing_routes}")
        else:
            print(f"✅ All {len(expected_routes)} base routes registered successfully")
            
        print("\n📝 Registered Routes Detail:")
        for route in app.routes:
            if hasattr(route, 'methods'):
                print(f"  - {list(route.methods)} {route.path}")
            else:
                print(f"  - {route.path}")

        print("\n✅ API Route Verification Complete!")
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify_api())
