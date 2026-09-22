"""Private, loopback verification server using the unmodified real Supabase app."""
import os
from fastapi import FastAPI, HTTPException
from backend.server import create_app

# Register ownership before the product app's catch-all frontend mount.
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

@app.get('/__rebuild_live_verify_identity')
def identity():
    run_id = os.environ.get('REBUILD_LIVE_VERIFY_RUN_ID')
    if not run_id:
        raise HTTPException(404)
    return {'run_id': run_id, 'boundary': 'REAL_SUPABASE_USER_JWT', 'product': 'RE:Build Agent'}

SAFE_ERROR_TYPES = {"ReadTimeout", "ConnectTimeout", "WriteTimeout", "PoolTimeout", "RemoteProtocolError", "ConnectError", "ReadError", "HTTPStatusError", "StorageUnavailableError", "ConflictError", "NotFoundError", "ValueError", "TypeError", "KeyError"}


def safe_error_diagnostic(error):
    """Classify a private probe failure without serializing messages or requests."""
    names, seen = [], set()
    while error is not None and id(error) not in seen and len(names) < 5:
        seen.add(id(error))
        name = type(error).__name__
        names.append(name if name in SAFE_ERROR_TYPES else "OtherError")
        error = error.__cause__ or error.__context__
    return "/".join(names)


product = create_app()
original_handler = product.exception_handlers[Exception]


async def diagnostic_handler(request, error):
    response = await original_handler(request, error)
    response.headers["X-Rebuild-Test-Error"] = safe_error_diagnostic(error)
    return response


product.add_exception_handler(Exception, diagnostic_handler)
app.mount('/', product)
