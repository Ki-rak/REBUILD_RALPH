import pytest
from test_api import flow
from ops.demo import ProductAPI,DemoError
from ops.demo_negative_verify import run_negative_flow

def test_negative_verifier_exercises_changed_input_and_failures(flow):
    client,records,files=flow
    report={'boundary':'TEST_STORAGE_INJECTED','checks':[]}
    run_negative_flow(ProductAPI(client,token='alice'),ProductAPI(client,token='bob'),report)
    assert len(report['checks'])==4 and all(row['passed'] for row in report['checks'])


def test_negative_verifier_rejects_cross_user_leak(flow):
    client,records,files=flow
    with pytest.raises(DemoError,match='CROSS_USER_PROJECT_LEAK'):
        run_negative_flow(ProductAPI(client,token='alice'),ProductAPI(client,token='alice'),{'checks':[]})
