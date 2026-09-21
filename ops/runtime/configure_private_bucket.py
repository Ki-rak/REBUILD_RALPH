"""Create only the absent RE:Build Agent private bucket; never alter an existing bucket."""
from pathlib import Path
from datetime import datetime,timezone
import sys,json
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root))
import httpx
from ops.runtime.supabase_probe import _load_env
from ops.runtime.supabase_live_verify import _service_headers
config=_load_env(root/".env")
url=config.get("SUPABASE_URL","").rstrip("/")
report={"at":datetime.now(timezone.utc).isoformat(),"scope":"PRIVATE_BUCKET_CONFIGURATION_ONLY",
 "created":False,"existing_bucket_modified":False,"private_bucket_verified":False,
 "db_rls_verified":False,"user_storage_rls_verified":False,"status":"FAILED"}
try:
 assert url=="https://wsziosnttnxefgfbgpeq.supabase.co"
 with httpx.Client(timeout=20) as http:
  headers=_service_headers(config["SUPABASE_SECRET_KEY"])
  lookup=http.get(url+"/storage/v1/bucket/rebuild-agent",headers=headers)
  report["initial_http_status"]=lookup.status_code
  if lookup.status_code==200:
   data=lookup.json()
  else:
   error=lookup.json()
   missing=lookup.status_code in (400,404) and any(
    str(error.get(key,"")).casefold()=="bucket not found" for key in ("error","message"))
   if not missing:
    report["status"]="EXISTENCE_NOT_CONFIRMED_NO_MUTATION"
    raise RuntimeError("STOP")
   created=http.post(url+"/storage/v1/bucket",headers=headers,
    json={"id":"rebuild-agent","name":"rebuild-agent","public":False})
   report["create_http_status"]=created.status_code
   if created.status_code not in (200,201):
    raise RuntimeError("BUCKET_CREATE_FAILED")
   report["created"]=True
   lookup=http.get(url+"/storage/v1/bucket/rebuild-agent",headers=headers)
   assert lookup.status_code==200
   data=lookup.json()
  report["private_bucket_verified"]=data.get("id")=="rebuild-agent" and data.get("public") is False
  report["status"]="CONFIGURED_PRIVATE_BUCKET" if report["private_bucket_verified"] else "BUCKET_POLICY_REVIEW_REQUIRED"
except Exception:
 pass
stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
(root/f"ops/runtime/supabase-bucket-configuration-{stamp}.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report))
raise SystemExit(0 if report["private_bucket_verified"] else 1)