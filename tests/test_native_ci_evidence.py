"""Verifier regression cases on synthetic receipts, not an executed native stack."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest

SPEC=importlib.util.spec_from_file_location('native_ci_gate',Path(__file__).parents[1]/'scripts/verify_native_ci.py')
gate=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
SHA='a'*40

@pytest.fixture
def evidence(tmp_path):
    repo=tmp_path/'repo';repo.mkdir();(repo/'pyproject.toml').write_text('# fixture\n')
    folder=tmp_path/'evidence';folder.mkdir()
    identity={'commit':SHA,'worktree_dirty':False}
    checks={f'V-P01-{i:02}':{'status':'PASS_NATIVE'} for i in range(1,7)}
    checks['V-P01-01']['same_batch']=True
    checks['V-P01-02'].update(target_reused=True,http_source_offline=True,watermark_unchanged_before_resume=True,exit_code=73)
    checks['V-P01-03']['publication_blocked']=True
    checks['V-P01-05']['outcomes']={'unauthenticated':401,'cross_site':403,'catalog_forbidden':403,'evidence_forbidden':403,'other_site_order':404}
    checks['V-P01-06'].update(last_accepted_preserved=True,degraded_exposed=True)
    summary={'profile':'native_spark/delta_spark/postgresql','status':'EXECUTED_SYNTHETIC_NATIVE_CHECKS',
       'git':identity,'dagster_run_id':'synthetic-run','application_checks':checks,
       'source_code':{'pyproject.toml':hashlib.sha256((repo/'pyproject.toml').read_bytes()).hexdigest()},
       'source_seeds':[{'server_version':160010} for _ in range(5)],
       'runtime_versions':{'pyspark':'4.0.1','delta-spark':'4.0.1','dagster':'1.11.16','psycopg':'3.2.13'}}
    docs={'qualification-native.json':summary,
          'report-before-faults.json':{'generation':1},
          'report-recovered.json':{'generation':2,'dataset_batch_id':'recovered'}}
    for batch,receiptname,proofname in [('base','accepted-receipt.json','accepted-final-readback.json'),
                                      ('recovered','recovery-receipt.json','native-final-readback.json')]:
        proof={'batch_id':batch,'target_manifest_sha256':'b'*64,'tables':{str(i):{'version':0} for i in range(10)}}
        raw=(json.dumps(proof,sort_keys=True,ensure_ascii=False,separators=(',',':'))+'\n').encode()
        docs[proofname]=proof
        docs[receiptname]={'git':identity,'batch_id':batch,'target_manifest_sha256':'b'*64,
           'status':'ACCEPTED','engine':'native_spark','observed_captured_rows':10000,'gold_fact_rows':3980,
           'source_to_target':{'line_counts_equal':True,'keys_equal':True,'amounts_equal':True},
           'native_final_readback':{'status':'EXECUTED_AND_RECONCILED_FINAL_PATH','tables_verified':10,
                                   'proof_sha256':hashlib.sha256(raw).hexdigest()}}
    for name,data in docs.items():(folder/name).write_text(json.dumps(data))
    junit=tmp_path/'junit.xml'
    junit.write_text('<testsuites><testsuite><testcase name="test_real_native_qualification" /></testsuite></testsuites>')
    return repo,folder,junit


def alter(folder,name,change):
    p=folder/name;d=json.loads(p.read_text());change(d);p.write_text(json.dumps(d))


def test_accepts_consistent_fixture_only(evidence):
    repo,folder,junit=evidence
    assert gate.validate(folder,junit,SHA,repo)['native_scenarios']==[f'V-P01-{i:02}' for i in range(1,7)]

@pytest.mark.parametrize('tag',['skipped','failure','error'])
def test_rejects_unexecuted_or_failed_native_test(evidence,tag):
    repo,folder,junit=evidence
    junit.write_text(f'<testsuite><testcase name="test_real_native_qualification"><{tag}/></testcase></testsuite>')
    with pytest.raises(ValueError):gate.validate(folder,junit,SHA,repo)

@pytest.mark.parametrize('name,mutation',[
 ('qualification-native.json',lambda d:d['git'].update(commit='b'*40)),
 ('qualification-native.json',lambda d:d['git'].update(worktree_dirty=True)),
 ('qualification-native.json',lambda d:d.update(profile='reference_sqlite')),
 ('qualification-native.json',lambda d:d['application_checks'].pop('V-P01-06')),
 ('qualification-native.json',lambda d:d['application_checks']['V-P01-02'].update(target_reused=False)),
 ('qualification-native.json',lambda d:d.update(dagster_run_id=None)),
 ('qualification-native.json',lambda d:d['runtime_versions'].update(pyspark='3.5.0')),
 ('qualification-native.json',lambda d:d.update(source_seeds=[])),
 ('accepted-receipt.json',lambda d:d.update(observed_captured_rows=9999)),
 ('accepted-receipt.json',lambda d:d['source_to_target'].update(amounts_equal=False)),
 ('accepted-final-readback.json',lambda d:d.update(batch_id='other')),
 ('native-final-readback.json',lambda d:d['tables']['0'].update(version=1)),
 ('report-recovered.json',lambda d:d.update(generation=1)),
])
def test_rejects_inconsistent_native_evidence(evidence,name,mutation):
    repo,folder,junit=evidence;alter(folder,name,mutation)
    with pytest.raises(ValueError):gate.validate(folder,junit,SHA,repo)


def test_rejects_source_drift(evidence):
    repo,folder,junit=evidence;(repo/'pyproject.toml').write_text('different')
    with pytest.raises(ValueError):gate.validate(folder,junit,SHA,repo)


def test_rejects_zero_native_tests(evidence):
    repo,folder,junit=evidence;junit.write_text('<testsuite/>')
    with pytest.raises(ValueError):gate.validate(folder,junit,SHA,repo)
