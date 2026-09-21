"""RE:Build Agent: approved past-data import and fresh multipart upload helpers.

This tool uses the actual product HTTP API and INPUT originals. It does not write
product rows directly, seed answers, read evaluator data, or change originals.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from collections import Counter
from datetime import datetime, timezone
import getpass
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import httpx
from backend.config import INPUT_ROOT
from backend.extraction import _SUPPORTED as SUPPORTED


class DemoError(RuntimeError):
    pass


def catalog(root: Path = INPUT_ROOT) -> list[dict]:
    if root.resolve() != INPUT_ROOT.resolve():
        raise DemoError('INPUT_ROOT_REQUIRED')
    projects = []
    for branch, kind in [('01_PAST_PROJECTS', 'historical'), ('02_NEW_PROJECTS', 'current')]:
        for folder in sorted((root / branch).iterdir()):
            if not folder.is_dir() or folder.is_symlink():
                continue
            files = []
            for path in sorted(folder.rglob('*')):
                if (not path.is_file() or path.is_symlink() or path.suffix.lower() not in SUPPORTED
                        or not path.resolve().is_relative_to((root / branch).resolve())):
                    continue
                data = path.read_bytes()
                files.append({'name': path.name, 'path': path.relative_to(root).as_posix(),
                              'bytes': len(data), 'sha256': sha256(data).hexdigest()})
            projects.append({'code': folder.name.split('_', 1)[0], 'name': folder.name,
                             'kind': kind, 'files': files})
    return projects


def select_projects(entries: list[dict], codes: list[str], kind: str) -> list[dict]:
    available = {x['code']: x for x in entries if x['kind'] == kind}
    selected = list(available) if codes == ['all'] else list(dict.fromkeys(codes))
    if not selected or any(code not in available for code in selected):
        raise DemoError('PROJECT_SELECTION_INVALID')
    return [deepcopy(available[code]) for code in selected]


def read_original(item: dict) -> bytes:
    path = (INPUT_ROOT / item['path']).resolve()
    if (not path.is_relative_to(INPUT_ROOT.resolve())
            or Path(item['path']).parts[0] not in {'01_PAST_PROJECTS', '02_NEW_PROJECTS'}):
        raise DemoError('INPUT_PATH_REJECTED')
    data = path.read_bytes()
    if sha256(data).hexdigest() != item['sha256']:
        raise DemoError('ORIGINAL_CHANGED_SINCE_SELECTION')
    return data


def validate_url(url: str) -> str:
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
            or parsed.username or parsed.password or parsed.path not in {'', '/'}
            or parsed.query or parsed.fragment):
        raise DemoError('LOOPBACK_PRODUCT_URL_REQUIRED')
    return url.rstrip('/')


class ProductAPI:
    def __init__(self, client, token: str | None = None):
        self.client, self.token = client, token

    def request(self, method: str, path: str, *, expected=(200, 201), **kwargs):
        headers = dict(kwargs.pop('headers', {}))
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        response = self.client.request(method, path, headers=headers, **kwargs)
        if response.status_code not in expected:
            code = 'PRODUCT_REQUEST_FAILED'
            try:
                candidate = response.json().get('detail', {}).get('code', '')
                if re.fullmatch(r'[A-Z0-9_]{3,80}', candidate):
                    code = candidate
            except (ValueError, TypeError, AttributeError):
                pass
            raise DemoError(f'{code}_HTTP_{response.status_code}')
        return response

    def json(self, method: str, path: str, **kwargs):
        return self.request(method, path, **kwargs).json()

    def login(self, email: str, password: str) -> dict:
        result = self.json('POST', '/api/auth/login', json={'email': email, 'password': password})
        self.token = result['access_token']
        return result['user']

    def logout(self):
        if self.token:
            self.json('POST', '/api/auth/logout')
            self.token = None


def all_documents(api: ProductAPI) -> list[dict]:
    documents = []
    for project in api.json('GET', '/api/projects'):
        documents.extend(api.json('GET', f"/api/projects/{project['id']}/documents"))
    return documents


def ensure_project(api: ProductAPI, name: str, kind: str) -> dict:
    matches = [x for x in api.json('GET', '/api/projects') if x['name'] == name]
    if len(matches) > 1 or any(x['kind'] != kind for x in matches):
        raise DemoError('AMBIGUOUS_EXISTING_PROJECT')
    return matches[0] if matches else api.json('POST', '/api/projects', json={'name': name, 'kind': kind})


def seed_past(api: ProductAPI, projects: list[dict], *, approved: bool) -> list[dict]:
    if approved is not True or any(x['kind'] != 'historical' for x in projects):
        raise DemoError('PAST_SELECTION_APPROVAL_REQUIRED')
    # Check the complete local selection before any mutation.
    for project in projects:
        for item in project['files']:
            read_original(item)
    allowed = {x['path'] for x in api.json('GET', '/api/import/candidates')['candidates']}
    if any(item['path'] not in allowed for project in projects for item in project['files']):
        raise DemoError('SERVER_INPUT_SELECTION_MISMATCH')
    reports = []
    for selected in projects:
        project = ensure_project(api, selected['name'], 'historical')
        documents = []
        # Small approved batches make interrupted runs safely resumable by SHA dedup.
        for offset in range(0, len(selected['files']), 4):
            batch = selected['files'][offset:offset+4]
            result = api.json('POST', '/api/import/approve', json={
                'project_id': project['id'], 'paths': [x['path'] for x in batch], 'confirmed': True})
            documents.extend(result['documents'])
        validate_extracted_selection(selected, documents)
        reports.append({'code': selected['code'], 'project_id': project['id'],
                        'documents': document_summary(documents)})
    return reports


def validate_extracted_selection(selected: dict, documents: list[dict]):
    if (not selected['files'] or Counter(x['sha256'] for x in selected['files'])
            != Counter(x.get('sha256') for x in documents)):
        raise DemoError('SELECTED_DOCUMENT_COVERAGE_MISMATCH')
    if any(x.get('extraction_status') != 'EXTRACTED' for x in documents):
        raise DemoError('SOURCE_EXTRACTION_NOT_COMPLETE')


def document_summary(documents: list[dict]) -> list[dict]:
    return [{key: doc.get(key) for key in ['id', 'filename', 'sha256', 'extraction_status', 'duplicate']}
            for doc in documents]


def upload_new(api: ProductAPI, selected: dict) -> dict:
    if selected['kind'] != 'current':
        raise DemoError('NEW_PROJECT_REQUIRED')
    originals = [(item, read_original(item)) for item in selected['files']]
    existing = {x['sha256'] for x in all_documents(api)}
    fresh = [item for item, _ in originals if item['sha256'] not in existing]
    # A copied historical attachment can be a known hash. The new base contract
    # itself must be absent, so a replay cannot be reported as a fresh upload.
    primary = [item for item, _ in originals if item['name'] == '02_ITB_and_Contract_Rev00.pdf']
    if not fresh or not primary or any(item['sha256'] in existing for item in primary):
        raise DemoError('NEW_INPUT_ALREADY_PRESENT')
    project = ensure_project(api, selected['name'], 'current')
    if api.json('GET', f"/api/projects/{project['id']}/documents"):
        raise DemoError('NEW_PROJECT_NOT_EMPTY')
    documents = []
    for offset in range(0, len(originals), 4):
        result = api.json('POST', f"/api/projects/{project['id']}/upload", files=[
            ('files', (item['name'], data, 'application/octet-stream')) for item, data in originals[offset:offset+4]])
        documents.extend(result['documents'])
    validate_extracted_selection(selected, documents)
    return {'code': selected['code'], 'project_id': project['id'],
            'fresh_hash_count': len(fresh), 'hash_absence_scope': 'CURRENT_AUTHENTICATED_OWNER',
            'known_attachment_hashes': [item['sha256'] for item, _ in originals if item['sha256'] in existing],
            'documents': documents}


def write_report(report: dict, label: str) -> Path:
    directory = ROOT / 'ops/runtime/demo'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (label + '-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inventory', 'seed', 'upload'])
    parser.add_argument('--past', nargs='+', default=['P01', 'P06'])
    parser.add_argument('--new', choices=['N01', 'N02'], default='N01')
    parser.add_argument('--url', default='http://127.0.0.1:8780')
    parser.add_argument('--email')
    parser.add_argument('--approve-past', action='store_true')
    args = parser.parse_args()
    report = {'product': 'RE:Build Agent', 'at': datetime.now(timezone.utc).isoformat(),
              'scope': 'USER_SELECTED_INPUT_PREPARATION', 'command': args.command, 'status': 'PENDING'}
    api = None
    try:
        entries = catalog()
        if args.command == 'inventory':
            report.update(status='INVENTORY_ONLY', projects=entries,
                          note='No upload, parsing, database or authentication mutation.')
        else:
            url = validate_url(args.url)
            selection = select_projects(entries, args.past if args.command == 'seed' else [args.new],
                                        'historical' if args.command == 'seed' else 'current')
            print(json.dumps({'selection': [{'code': x['code'], 'files': len(x['files'])} for x in selection],
                              'new_projects_preloaded': False}, ensure_ascii=False))
            if args.command == 'seed' and not args.approve_past:
                raise DemoError('Review inventory and use --approve-past for the chosen past projects')
            email = args.email or input('제품 로그인 이메일: ').strip()
            password = getpass.getpass('제품 로그인 비밀번호 (저장/출력하지 않음): ')
            with httpx.Client(base_url=url, timeout=180, follow_redirects=False, trust_env=False) as client:
                api = ProductAPI(client)
                api.login(email, password)
                password = ''
                try:
                    if args.command == 'seed':
                        result = seed_past(api, selection, approved=args.approve_past)
                    else:
                        result = [upload_new(api, selection[0])]
                    issues = [d for p in result for d in p['documents'] if d['extraction_status'] != 'EXTRACTED']
                    report.update(status='REVIEW_REQUIRED' if issues else 'PASSED', projects=result,
                                  extraction_review_count=len(issues), product_complete=False)
                finally:
                    api.logout()
        path = write_report(report, args.command)
        print(json.dumps({'status': report['status'], 'report': str(path.relative_to(ROOT))}, ensure_ascii=False))
        return 0 if report['status'] in {'PASSED', 'INVENTORY_ONLY'} else 3
    except (Exception, KeyboardInterrupt) as error:
        report.update(status='FAILED', error_code=str(error) if isinstance(error, DemoError) else 'SAFE_DIAGNOSTIC_WITHHELD')
        path = write_report(report, args.command)
        print(json.dumps({'status': 'FAILED', 'error_code': report['error_code'], 'report': str(path.relative_to(ROOT))}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
