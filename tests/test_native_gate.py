"""Reference tests do not silently qualify optional/native components."""
import importlib.util
import os
import pytest
from ilc.errors import NativeUnavailable,SourceError
from ilc.native import require_native
from ilc.sources import validate_pg_dsn


def test_missing_native_dependency_never_falls_back(monkeypatch):
    monkeypatch.setattr(importlib.util,'find_spec',lambda name:None)
    with pytest.raises(NativeUnavailable):require_native()


@pytest.mark.parametrize('dsn',[
    'postgresql://user:pass@127.0.0.1/ilc_demo?host=external.example',
    'postgresql://user:pass@127.0.0.1/ilc_demo?dbname=production',
])
def test_dsn_query_cannot_override_authorized_target(dsn):
    with pytest.raises(SourceError):validate_pg_dsn(dsn)


@pytest.mark.native
@pytest.mark.skipif(os.environ.get('ILC_NATIVE_TESTS')!='1',reason='Native PostgreSQL/Spark/Delta/Dagster qualification not enabled')
def test_real_native_qualification(tmp_path,repo,contract):
    # In explicitly enabled CI this fails, rather than skips, if setup is missing.
    require_native()
    from ilc.canonical import read_json
    from ilc.fixtures import create_fixture
    from ilc.native import seed_postgres
    from ilc.orchestration import accepted_sales_job
    from ilc.pipeline import Pipeline
    from ilc.source_api import serving
    from ilc.storage import read_target
    root=tmp_path/'native';source=tmp_path/'fixture'
    m=create_fixture(source,contract,1000)
    seed_postgres(source,contract,read_json(repo/'profiles/native.json'))
    with serving(source) as url:
        result=accepted_sales_job.execute_in_process(run_config={'ops':{'execute_accepted_batch':{'config':{
            'repo':str(repo),'root':str(root),'contract':str(repo/'contracts/sales.json'),
            'profile':str(repo/'profiles/native.json'),'fixture':str(source),'api_url':url,
            'key':'native-ci','until':m['as_of']}}}})
        assert result.success
        p=Pipeline(repo,root,repo/'contracts/sales.json',repo/'profiles/native.json')
        try:
            row=p.journal.find('native-ci')
            assert row['receipt']['status']=='ACCEPTED' and row['receipt']['engine']=='native_spark'
            manifest=read_target(root,row['batch_id'])
            assert manifest['native_materialization']['status']=='EXECUTED_AND_RECONCILED'
            assert p.execute('native-ci',m['as_of'],source,url)['invocation']=='REPLAY_OF_ACCEPTED_BATCH'
        finally:p.close()
