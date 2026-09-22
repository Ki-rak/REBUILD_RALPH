import pytest
from ops.demo import DemoError
from ops.demo_provider_verify import verify_execution

def test_provider_proof_rejects_wrong_auth_and_fabricated_usage():
    value={'execution':{'source':'MODEL_CALL','state':'SUCCEEDED','auth_mode':'OPENAI_API_KEY'},'usage':{'input_tokens':19,'output_tokens':7}}
    assert verify_execution(value,'deployed')[1]['input_tokens']==19
    with pytest.raises(DemoError,match='EXPECTED_REAL_MODEL_EXECUTION_REQUIRED'):verify_execution(value,'local')
    value['usage']['input_tokens']=True
    with pytest.raises(DemoError,match='ACTUAL_TOKEN_USAGE_REQUIRED'):verify_execution(value,'deployed')
    value['usage']={'input_tokens':0,'output_tokens':0}
    assert verify_execution(value,'deployed')[1]['output_tokens']==0
