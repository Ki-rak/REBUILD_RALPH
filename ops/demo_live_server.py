"""Private, loopback verification server using the unmodified real Supabase app."""
import os
from fastapi import HTTPException
from backend.server import create_app

app = create_app()

@app.get('/__rebuild_live_verify_identity')
def identity():
    run_id = os.environ.get('REBUILD_LIVE_VERIFY_RUN_ID')
    if not run_id:
        raise HTTPException(404)
    return {'run_id': run_id, 'boundary': 'REAL_SUPABASE_USER_JWT', 'product': 'RE:Build Agent'}
