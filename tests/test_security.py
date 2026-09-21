from copy import deepcopy
import pytest
from backend.security import IntegrityError, APPROVAL_FIELDS, sign_document, verify_document, sign_approval, verify_approval

KEY="isolated-test-integrity-key-never-production"

def test_evidence_seal_binds_owner_content_locator_and_document_identity():
    doc={"id":"doc1","project_id":"p","sha256":"a"*64,"blocks":[{"id":"b1","text":"actual","locator":"line 1"}]}
    doc["extraction_signature"]=sign_document(doc,"owner1",KEY)
    verify_document(doc,"owner1",KEY)
    for field,value in [("id","doc2"),("sha256","b"*64),("blocks",[{"id":"b1","text":"forged"}])]:
        altered=deepcopy(doc);altered[field]=value
        with pytest.raises(IntegrityError):verify_document(altered,"owner1",KEY)
    with pytest.raises(IntegrityError):verify_document(doc,"owner2",KEY)
    with pytest.raises(IntegrityError):verify_document(doc,"owner1","")
    with pytest.raises(IntegrityError):verify_document(doc,"owner1",KEY+"rotated")

def test_approval_seal_requires_exact_snapshot_kind_version_and_owner():
    draft={"id":"d1","project_id":"p","output_kind":"itb","type":"itb","revision":1,"rows":[],
           "input_fingerprint":"hash","template_id":"itb","template_sha256":"template","approval_id":"a1",
           "approved_at":"time","reviewer":"owner1","version":2,"approved_entity_version":2}
    draft["approval_signature"]=sign_approval(draft,"owner1",KEY)
    snapshot={"id":"a1","draft_id":"d1","approval_signature":draft["approval_signature"],
              "signed_draft":{field:draft.get(field) for field in APPROVAL_FIELDS}}
    verify_approval(draft,snapshot,"owner1",KEY)
    with pytest.raises(IntegrityError):verify_approval(draft,None,"owner1",KEY)
    for field,value in [("id","d2"),("revision",2),("output_kind","risk"),("approval_id","a2"),("rows",[{"title":"forged"}])]:
        altered=deepcopy(draft);altered[field]=value
        with pytest.raises(IntegrityError):verify_approval(altered,snapshot,"owner1",KEY)
    snapshot["signed_draft"]["rows"]=[{"text":"forged snapshot"}]
    with pytest.raises(IntegrityError):verify_approval(draft,snapshot,"owner1",KEY)
