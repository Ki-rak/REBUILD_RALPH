"""Run the actual browser/API fixture and bounded checks in one owned process."""
from pathlib import Path
import argparse
import os
import uuid
import runpy
import subprocess
import threading
import time

import uvicorn

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8783)
    parser.add_argument('scripts', nargs='+')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535')
    allowed = {'browser_flow.cjs', 'browser_mixed_upload.cjs', 'browser_slide_limits.cjs',
               'browser_search_scope.cjs', 'browser_provider_profiles.cjs', 'browser_mobile_core.cjs'}
    scripts = []
    for name in args.scripts:
        script = (ROOT / 'tests/ui' / name).resolve()
        if name not in allowed or not script.is_relative_to(ROOT / 'tests/ui') or not script.is_file():
            parser.error('Choose an existing project browser .cjs test')
        scripts.append(script)
    namespace = runpy.run_path(str(ROOT / 'tests/ui/browser_server.py'), run_name='browser_fixture')
    run_id = uuid.uuid4().hex
    namespace['app'].state.browser_run_id = run_id
    child_env = {**os.environ, 'BROWSER_TEST_URL': f'http://127.0.0.1:{args.port}',
                 'BROWSER_TEST_RUN_ID': run_id}
    server = uvicorn.Server(uvicorn.Config(namespace['app'], host='127.0.0.1', port=args.port,
                                         access_log=False, log_level='warning'))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 30
    try:
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise RuntimeError('TEST_STORAGE_INJECTED fixture did not start')
            time.sleep(0.1)
        print(f'TEST_STORAGE_INJECTED fixture ready on 127.0.0.1:{args.port}', flush=True)
        for script in scripts:
            result = subprocess.run(['node', str(script)], cwd=ROOT, timeout=180, env=child_env,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                return result.returncode
        return 0
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        if thread.is_alive():
            raise RuntimeError('Fixture shutdown did not complete')
        print('Owned browser fixture stopped', flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
