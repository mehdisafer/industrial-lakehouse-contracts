"""Offline evidence-gate tests; synthetic documents are not integration results."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/verify_reference_ci.py'
SPEC = importlib.util.spec_from_file_location('reference_gate', SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)
SHA = 'a' * 40
TREE = 'b' * 40


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding='utf-8')


def alter(path, mutation):
    data = json.loads(path.read_text()); mutation(data); write(path, data)


@pytest.fixture
def evidence(tmp_path, monkeypatch):
    root = tmp_path
    app = root / 'src/ilc/module.py'; app.parent.mkdir(parents=True); app.write_text('# synthetic module\n')
    (root / 'pyproject.toml').write_text('# synthetic project\n')
    test = root / 'tests/test_unit.py'; test.parent.mkdir(); test.write_text('# synthetic test\n')
    manifest = {n: gate.sha256((root/n).read_bytes()) for n in ['src/ilc/module.py', 'pyproject.toml']}
    identity = {'commit': SHA, 'worktree_dirty': False}
    tests = [{'nodeid': 'tests/test_unit.py::test_good', 'classname': 'tests.test_unit', 'name': 'test_good', 'native': False},
             {'nodeid': 'tests/test_native_gate.py::test_real_native_qualification', 'classname': gate.NATIVE_TEST[0],
              'name': gate.NATIVE_TEST[1], 'native': True}]
    (root / 'tests/test_native_gate.py').write_text('# synthetic native test\n')
    write(root/'artifacts/reference/test-inventory.json', {'schema_version':'ilc-reference-collection/1',
        'source_sha':SHA,'source_tree':TREE,'tests':tests,'test_file_sha256':{
            n:gate.sha256((root/n).read_bytes()) for n in ['tests/test_unit.py','tests/test_native_gate.py']}})
    junit = root / 'test-results/junit.xml'; junit.parent.mkdir()
    junit.write_text('<testsuites><testsuite tests="2" errors="0" failures="0" skipped="1">'
        '<testcase classname="tests.test_unit" name="test_good"/>'
        '<testcase classname="tests.test_native_gate" name="test_real_native_qualification">'
        '<skipped message="Native qualification not enabled"/></testcase></testsuite></testsuites>')
    write(root/'artifacts/repository/check.json', {'status':'PASS','errors':[],'tracked_files':10})
    write(root/'artifacts/publication/summary.json', {'source_sha':SHA,'status':'RULE_BASED_HISTORY_SCAN_NO_FINDINGS',
        'finding_count':0,'findings':[],'scanner':{'positive_control_detected':True}})
    ref = root/'.runtime/circleci-reference/evidence'
    rec = root/'.runtime/circleci-recovery/evidence'
    checks={f'V-P01-{n:02}':{'status':'PASS_REFERENCE'} for n in range(1,7)}
    checks['V-P01-01'].update(same_batch=True, generation_after_replay=1)
    checks['V-P01-02'].update(child_exit=73,accepted_generation=2,target_exists_before_accept=True,
        watermark_unchanged_before_resume=True,resume_with_source_offline=True,candidate_reused=True)
    checks['V-P01-03'].update(publication_blocked=True)
    checks['V-P01-05']['outcomes']={'unauthenticated':401,'wrong_token':401,'cross_site':403,'global_evidence':403,
        'global_catalog':403,'other_site_order':404}
    checks['V-P01-06'].update(last_accepted_preserved=True,degraded_exposed=True)
    summary={'git':identity,'source_code':manifest,'qualified_profile':'reference_sqlite/reference_json',
        'actual_captured_rows_per_clean_base_batch':10000,'application_checks':checks,
        'metadata_extension':{'status':'PASS_REFERENCE','new_rows':3,'report_generation':3,
                              'engine_code_unchanged':True,'consumer_catalog_observed':True}}
    for k in ['native_postgresql_spark_delta_dagster','openmetadata','fabric','power_bi','big_data_scale']:summary[k]='NOT_RUN'
    write(ref/'qualification.json',summary)
    reports=[]
    for generation,amount,receiptfile,reportfile in [(1,'8857766.18','baseline-receipt.json','report-initial.json'),
                                                   (2,'8857786.18','recovery-receipt.json','report-recovered.json')]:
        receipt={'git':identity,'status':'ACCEPTED','engine':'reference_sqlite','target':'reference_json',
            'observed_captured_rows':10000,'gold_fact_rows':3980,'generation':generation,'batch_id':str(generation)*64,
            'target_manifest_sha256':str(generation)*64,'source_to_target':{'line_counts_equal':True,
            'keys_equal':True,'amounts_equal':True,'source_amount':amount,'gold_amount':amount},
            'invocation':'RESUMED' if generation==2 else 'FIRST_ATTEMPT','target_reused':generation==2}
        report={'generation':generation,'dataset_batch_id':receipt['batch_id'],
                'lineage':{'target_manifest_sha256':receipt['target_manifest_sha256']},
                'totals':{'ordered_amount':amount,'line_count':3980},
                'sites':[{'site_id':'SITE_A','ordered_amount':amount,'line_count':3980}]}
        write(ref/receiptfile,receipt);write(ref/reportfile,report);reports.append(report)
    for fault in ['duplicate_key','invalid_amount','schema_drift']:
        write(ref/f'rejected-{fault}.json',{'status':'REJECTED','dataset_promoted':False,'watermark_advanced':False})
        write(ref/f'report-after-{fault}.json',{**reports[0],'status':'DEGRADED'})
    restore={'git':identity,'source_code':manifest,'status':'REFERENCE_RECOVERY_AND_PROTOCOL_CHECKS_EXECUTED',
        'source_rows':10000,'gold_rows':3980,'reference_restore':{k:True for k in [
            'sqlite_backup_api_used','original_runtime_retained','same_path_identity','totals_equal',
            'report_reread_over_real_http','unauthenticated_refused','accepted_replay_http_source_offline',
            'publication_state_equal','governance_outbox_restored']},'openmetadata':{
            'scope':'PROTOCOL_EMULATOR_NOT_OPENMETADATA_PRODUCT','server_product_qualified':False,
            'server_rbac_qualified':False,'database_create_requests_after_lost_response':1}}
    restore['reference_restore']['catalog_replay_additional_writes']=0
    for k in ['native_profile','fabric','power_bi']:restore[k]='NOT_RUN'
    write(rec/'qualification.json',restore)
    archive = rec.parent/'work/reference-snapshot.zip'; archive.parent.mkdir(parents=True)
    archive.write_bytes(b'synthetic archive bytes; not an executed restore')
    archive_hash = gate.sha256(archive.read_bytes())
    alter(rec/'qualification.json',lambda d:d['reference_restore'].update(archive_sha256=archive_hash))
    first=gate.read_json(ref/'baseline-receipt.json')
    write(rec/'acceptance.json', first)
    write(rec/'replay-after-restore.json', {**first,'invocation':'REPLAY_OF_ACCEPTED_BATCH'})
    write(rec/'report-before-restore.json', reports[0]);write(rec/'report-after-restore.json', reports[0])
    write(rec/'backup-receipt.json',{'status':'REFERENCE_BACKUP_WRITTEN','archive_sha256':archive_hash,
                                    'native_backup_qualified':False,'generation':1})
    write(rec/'restore-receipt.json',{'status':'REFERENCE_RESTORE_VERIFIED','archive_sha256':archive_hash,
                  'native_backup_qualified':False,'generation':1,'accepted_batch':first['batch_id']})
    monkeypatch.setattr(gate,'checkout',lambda root,expected:TREE)
    return root


def test_accepts_consistent_synthetic_fixture(evidence):
    result=gate.verify(evidence,SHA)
    assert result['status']=='REFERENCE_EVIDENCE_CONSISTENT'
    assert result['test_results']['passed']==1 and result['test_results']['skipped']==1
    assert result['test_results']['original_xml_sha256']['junit.xml']==gate.sha256((evidence/'test-results/junit.xml').read_bytes())
    assert result['reference']['catalogue_peer']=='PROTOCOL_EMULATOR_NOT_OPENMETADATA_PRODUCT'
    assert result['billing_credits_observed'] is None


@pytest.mark.parametrize('change',[
    lambda xml:xml.find('testsuite').set('tests','100'),
    lambda xml:xml.find('testsuite').set('failures','1'),
    lambda xml:xml.find('testsuite').set('skipped','0'),
    lambda xml:xml.find('testsuite/testcase').set('name','different_test'),
    lambda xml:xml.find('testsuite').append(deepcopy(xml.find('testsuite/testcase'))),
    lambda xml:xml.find('testsuite').remove(xml.find('testsuite/testcase')),
    lambda xml:ET.SubElement(xml,'script',{'src':'chrome-extension://example.invalid/script.js'}),
    lambda xml:xml.find('testsuite/testcase/skipped').attrib.pop('message'),
])
def test_rejects_inconsistent_original_junit(evidence,change):
    path=evidence/'test-results/junit.xml';xml=ET.fromstring(path.read_bytes());change(xml)
    path.write_bytes(ET.tostring(xml))
    with pytest.raises(gate.EvidenceError):gate.verify(evidence,SHA)


@pytest.mark.parametrize('tag,attribute',[('failure','failures'),('error','errors'),('skipped','skipped')])
def test_rejects_failing_or_extra_skipped_reference_case(evidence,tag,attribute):
    path=evidence/'test-results/junit.xml';xml=ET.fromstring(path.read_bytes());suite=xml.find('testsuite')
    ET.SubElement(suite.find('testcase'),tag,{'message':'synthetic'})
    suite.set(attribute,str(int(suite.get(attribute))+1));path.write_bytes(ET.tostring(xml))
    with pytest.raises(gate.EvidenceError):gate.verify(evidence,SHA)


def test_junit_dtd_is_refused(evidence):
    p=evidence/'test-results/junit.xml';p.write_text('<!DOCTYPE testsuites [<!ENTITY fixture "not executed">]>'+p.read_text())
    with pytest.raises(gate.EvidenceError):gate.verify(evidence,SHA)


def test_junit_symlink_is_refused(evidence,tmp_path):
    p=evidence/'test-results/junit.xml';original=p.read_bytes();p.unlink()
    target=tmp_path/'original.xml';target.write_bytes(original);p.symlink_to(target)
    with pytest.raises(gate.EvidenceError):gate.verify(evidence,SHA)


@pytest.mark.parametrize('path,mutation',[
    ('artifacts/reference/test-inventory.json',lambda d:d.update(source_sha='c'*40)),
    ('artifacts/reference/test-inventory.json',lambda d:d.update(source_tree='c'*40)),
    ('artifacts/reference/test-inventory.json',lambda d:d.update(tests=[])),
    ('artifacts/reference/test-inventory.json',lambda d:d['tests'].append(d['tests'][0])),
    ('artifacts/repository/check.json',lambda d:d.update(status='FAIL')),
    ('artifacts/repository/check.json',lambda d:d.update(errors=['synthetic problem'])),
    ('artifacts/publication/summary.json',lambda d:d.update(finding_count=1)),
    ('artifacts/publication/summary.json',lambda d:d['scanner'].update(positive_control_detected=False)),
    ('.runtime/circleci-reference/evidence/qualification.json',lambda d:d['git'].update(worktree_dirty=True)),
    ('.runtime/circleci-reference/evidence/qualification.json',lambda d:d['source_code'].pop('pyproject.toml')),
    ('.runtime/circleci-reference/evidence/qualification.json',lambda d:d.update(qualified_profile='native_spark')),
    ('.runtime/circleci-reference/evidence/qualification.json',lambda d:d.update(fabric='PASS')),
    ('.runtime/circleci-reference/evidence/qualification.json',lambda d:d['application_checks'].pop('V-P01-01')),
    ('.runtime/circleci-reference/evidence/qualification.json',lambda d:d['application_checks']['V-P01-02'].update(candidate_reused=False)),
    ('.runtime/circleci-reference/evidence/qualification.json',lambda d:d['application_checks']['V-P01-05']['outcomes'].update(cross_site=200)),
    ('.runtime/circleci-reference/evidence/qualification.json',lambda d:d['metadata_extension'].update(engine_code_unchanged=False)),
    ('.runtime/circleci-reference/evidence/recovery-receipt.json',lambda d:d['git'].update(commit='c'*40)),
    ('.runtime/circleci-reference/evidence/recovery-receipt.json',lambda d:d.update(gold_fact_rows=9999)),
    ('.runtime/circleci-reference/evidence/recovery-receipt.json',lambda d:d.update(target_reused=False)),
    ('.runtime/circleci-reference/evidence/recovery-receipt.json',lambda d:d['source_to_target'].update(keys_equal=False)),
    ('.runtime/circleci-reference/evidence/rejected-invalid_amount.json',lambda d:d.update(dataset_promoted=True)),
    ('.runtime/circleci-reference/evidence/report-recovered.json',lambda d:d.update(generation=1)),
    ('.runtime/circleci-reference/evidence/report-recovered.json',lambda d:d['sites'][0].update(ordered_amount='0.00')),
    ('.runtime/circleci-reference/evidence/report-after-schema_drift.json',lambda d:d['totals'].update(line_count=1)),
    ('.runtime/circleci-recovery/evidence/backup-receipt.json',lambda d:d.update(archive_sha256='f'*64)),
    ('.runtime/circleci-recovery/evidence/restore-receipt.json',lambda d:d.update(generation=2)),
    ('.runtime/circleci-recovery/evidence/report-after-restore.json',lambda d:d['totals'].update(line_count=4000)),
    ('.runtime/circleci-recovery/evidence/replay-after-restore.json',lambda d:d.update(invocation='FIRST_ATTEMPT')),
    ('.runtime/circleci-recovery/evidence/qualification.json',lambda d:d['reference_restore'].update(totals_equal=False)),
    ('.runtime/circleci-recovery/evidence/qualification.json',lambda d:d['reference_restore'].update(catalog_replay_additional_writes=1)),
    ('.runtime/circleci-recovery/evidence/qualification.json',lambda d:d['openmetadata'].update(server_product_qualified=True)),
])
def test_rejects_incomplete_or_conflicting_receipts(evidence,path,mutation):
    alter(evidence/path,mutation)
    with pytest.raises(gate.EvidenceError):gate.verify(evidence,SHA)


def test_test_source_change_after_collection_fails(evidence):
    (evidence/'tests/test_unit.py').write_text('# different')
    with pytest.raises(gate.EvidenceError):gate.verify(evidence,SHA)


def test_application_change_after_receipt_fails(evidence):
    (evidence/'src/ilc/module.py').write_text('# different')
    with pytest.raises(gate.EvidenceError):gate.verify(evidence,SHA)


def test_output_is_not_overwritten(evidence):
    path=evidence/'result.json';path.write_text('preserved')
    assert gate.main(['verify','--root',str(evidence),'--expected-sha',SHA,'--output',str(path)])==1
    assert path.read_text()=='preserved'


def test_duplicate_json_keys_and_nonfinite_values_refused(tmp_path):
    p=tmp_path/'evidence.json'
    for text in ['{"a":1,"a":2}','{"a":NaN}','[]']:
        p.write_text(text)
        with pytest.raises(gate.EvidenceError):gate.read_json(p)


def test_untrusted_error_text_is_not_echoed(evidence,capsys):
    p=evidence/'test-results/junit.xml';p.write_text('<testsuite tests="SYNTHETIC_SECRET"/>')
    assert gate.main(['verify','--root',str(evidence),'--expected-sha',SHA,'--output',str(evidence/'out.json')])==1
    assert 'SYNTHETIC_SECRET' not in capsys.readouterr().out


def test_real_collection_records_nodeids_without_executing_tests(tmp_path):
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=tmp_path,text=True).strip()
    git('init','-q');git('config','user.name','P01 test');git('config','user.email','test@example.invalid')
    (tmp_path/'tests').mkdir();(tmp_path/'.gitignore').write_text('artifacts/\n__pycache__/\n.pytest_cache/\n')
    (tmp_path/'pyproject.toml').write_text('[tool.pytest.ini_options]\nmarkers=["native: optional integration"]\n')
    (tmp_path/'tests/test_unit.py').write_text('def test_collected_only():\n    raise AssertionError("must not execute")\n')
    (tmp_path/'tests/test_native_gate.py').write_text('import pytest\n@pytest.mark.native\ndef test_real_native_qualification():\n    raise AssertionError("must not execute")\n')
    git('add','.');git('commit','-qm','synthetic collection fixture');sha=git('rev-parse','HEAD')
    output=tmp_path/'artifacts/inventory.json'
    result=subprocess.run([sys.executable,str(SCRIPT),'collect','--root',str(tmp_path),'--expected-sha',sha,'--output',str(output)],
                          capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    data=json.loads(output.read_text())
    assert data['source_sha']==sha and len(data['tests'])==2
    assert len(data['test_file_sha256'])==2
    assert data['tests'][0]['native'] is True
    (tmp_path/'tests/test_unit.py').write_text('# modified')
    retry=subprocess.run([sys.executable,str(SCRIPT),'collect','--root',str(tmp_path),'--expected-sha',sha,
                          '--output',str(tmp_path/'artifacts/new.json')],capture_output=True,text=True,timeout=30)
    assert retry.returncode==1 and not (tmp_path/'artifacts/new.json').exists()


def test_retained_archive_tampering_is_rejected(evidence):
    (evidence/'.runtime/circleci-recovery/work/reference-snapshot.zip').write_bytes(b'changed')
    with pytest.raises(gate.EvidenceError):gate.verify(evidence,SHA)
