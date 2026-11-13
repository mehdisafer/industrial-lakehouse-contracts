"""Gate unit tests: injected verifier, NOT an executed Spark qualification."""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from ilc.canonical import canonical, digest, read_json
from ilc.errors import IntegrityError
from ilc.native import normalize_native_row, verify_delta_at_final_path
from ilc.storage import batch_path, validate_native_publication, check_native_receipt


@pytest.mark.parametrize('literal', ['1.1234', '0.0001', '9', '9.10', '-1.000000', '0.00'])
def test_decimal_scale_is_not_truncated(literal):
    row = SimpleNamespace(asDict=lambda **kw: {'amount': Decimal(literal)})
    assert normalize_native_row(row)['amount'] == literal


def test_timestamp_normalization_is_explicitly_utc():
    row = SimpleNamespace(asDict=lambda **kw: {'at': datetime(2026,1,1,2,tzinfo=timezone(timedelta(hours=2)))})
    assert normalize_native_row(row)['at'] == '2026-01-01T00:00:00.000000Z'


def test_verifier_refuses_staging_path(tmp_path):
    with pytest.raises(IntegrityError,match='final target'):
        verify_delta_at_final_path(tmp_path/'.stage-test', {'entities':{}})


def test_reference_receipt_never_claims_native(pipeline,accepted,contract):
    assert accepted['native_final_readback']['status']=='NOT_RUN'
    check_native_receipt(pipeline.root,accepted['batch_id'],accepted)


def test_native_proof_is_verified_before_watermark(pipeline,source,monkeypatch):
    def failed(*args):
        assert pipeline.journal.state()['generation']==0
        raise IntegrityError('Injected final read failure; no real Spark')
    monkeypatch.setattr('ilc.pipeline.validate_native_publication',failed)
    folder,m,url=source
    with pytest.raises(IntegrityError):pipeline.execute('readback-failure',m['as_of'],folder,url)
    assert pipeline.journal.state()['generation']==0
    assert pipeline.journal.state()['watermarks']=={}


def test_receipt_proof_rejects_missing_corrupt_or_wrong_binding(tmp_path):
    batch='a'*64
    root=batch_path(tmp_path,batch);root.mkdir(parents=True)
    target_hash='b'*64
    proof={'batch_id':batch,'target_manifest_sha256':target_hash,
           'status':'EXECUTED_AND_RECONCILED_FINAL_PATH','tables':{}}
    receipt={'target':'delta_spark','target_manifest_sha256':target_hash,
             'native_final_readback':{'proof_sha256':digest(proof)}}
    with pytest.raises(IntegrityError):check_native_receipt(tmp_path,batch,receipt)
    (root/'native_final_readback.json').write_bytes(canonical(proof))
    check_native_receipt(tmp_path,batch,receipt)
    proof['batch_id']='c'*64
    (root/'native_final_readback.json').write_bytes(canonical(proof))
    with pytest.raises(IntegrityError):check_native_receipt(tmp_path,batch,receipt)


def test_final_path_probe_binds_manifest(pipeline,accepted,contract,monkeypatch):
    # Injected native adapter tests only the publication control flow and receipt.
    batch=accepted['batch_id']
    target=read_json(batch_path(pipeline.root,batch)/'target/manifest.json')
    target={**target,'target':'delta_spark'}
    monkeypatch.setattr('ilc.storage.read_target',lambda *a:target)
    def fake(path,contract):
        assert path==batch_path(pipeline.root,batch)/'target'
        return {'status':'EXECUTED_AND_RECONCILED_FINAL_PATH','tables':{'gold/fact':{'rows':380}}}
    monkeypatch.setattr('ilc.native.verify_delta_at_final_path',fake)
    r=validate_native_publication(pipeline.root,batch,target,contract)
    assert r['tables_verified']==1
    check_native_receipt(pipeline.root,batch,{'target':'delta_spark',
        'target_manifest_sha256':digest(target),'native_final_readback':r})
