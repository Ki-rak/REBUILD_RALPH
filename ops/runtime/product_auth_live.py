"""Actual localhost product Auth endpoints with a disposable real Supabase user."""
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
import sys,json,secrets
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
import httpx
from ops.runtime.supabase_probe import _load_env
from ops.runtime.supabase_live_verify import _create_test_user,_cleanup
config=_load_env(root/".env")
url=config.get("SUPABASE_URL","").rstrip("/")
secret=config.get("SUPABASE_SECRET_KEY","")
report={"at":datetime.now(timezone.utc).isoformat(),"scope":"REAL_PRODUCT_HTTP_AUTH_WITH_REAL_SUPABASE",
 "login":False,"me":False,"refresh":False,"logout":False,"refresh_revoked":False,
 "response_no_store":False,"invalid_credentials_rejected":False,"cleanup_complete":True,
 "db_storage_verified":False,"oauth_verified":False}
users=[];stage="configuration"
with httpx.Client(timeout=20) as http:
 try:
  assert url=="https://wsziosnttnxefgfbgpeq.supabase.co" and secret
  api="http://127.0.0.1:8780"
  assert http.get(api+"/api/health").json()["product"]=="RE:Build Agent"
  run=uuid4().hex
  email=f"rebuild-product-auth+{run}@example.com"
  password=secrets.token_urlsafe(24)
  stage="create_probe_user"
  owner=_create_test_user(http,url,secret,email,password,run,20)
  users.append(owner)
  stage="login"
  response=http.post(api+"/api/auth/login",json={"email":email,"password":password})
  assert response.status_code==200
  session=response.json()
  assert session["user"]["id"]==owner
  report["login"]=True
  report["response_no_store"]=response.headers.get("cache-control")=="no-store"
  stage="me"
  response=http.get(api+"/api/auth/me",headers={"Authorization":"Bearer "+session["access_token"]})
  assert response.status_code==200 and response.json()["id"]==owner
  report["me"]=True
  stage="refresh"
  response=http.post(api+"/api/auth/refresh",json={"refresh_token":session["refresh_token"]})
  assert response.status_code==200
  session=response.json()
  assert session["user"]["id"]==owner
  report["refresh"]=True
  stage="logout"
  response=http.post(api+"/api/auth/logout",headers={"Authorization":"Bearer "+session["access_token"]})
  assert response.status_code==200 and response.json()["logged_out"]
  report["logout"]=True
  response=http.post(api+"/api/auth/refresh",json={"refresh_token":session["refresh_token"]})
  assert response.status_code==401
  report["refresh_revoked"]=True
  stage="invalid_credentials"
  response=http.post(api+"/api/auth/login",json={"email":email,"password":secrets.token_urlsafe(24)})
  assert response.status_code==401
  report["invalid_credentials_rejected"]=True
  report["status"]="PASS"
 except Exception:
  report.update(status="FAILED",stage=stage,error_code="SAFE_DIAGNOSTIC_WITHHELD")
 finally:
  report["cleanup_complete"]=_cleanup(http=http,url=url,secret_key=secret,users=users,
   entity_ids={},object_paths=[],timeout=20)
  if not report["cleanup_complete"]:report["status"]="CLEANUP_FAILED"
stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
(root/f"ops/runtime/product-auth-live-{stamp}.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report))
raise SystemExit(0 if report["status"]=="PASS" and report["cleanup_complete"] else 1)