from pathlib import Path
import pytest
from ilc.canonical import read_json
from ilc.fixtures import create_fixture
from ilc.pipeline import Pipeline
from ilc.source_api import serving

REPO=Path(__file__).resolve().parents[1]

@pytest.fixture
def repo():return REPO

@pytest.fixture
def contract():return read_json(REPO/'contracts/sales.json')

@pytest.fixture
def profile():return read_json(REPO/'profiles/reference.json')

@pytest.fixture
def source(tmp_path,contract):
    folder=tmp_path/'fixture'
    manifest=create_fixture(folder,contract,rows=1000)
    with serving(folder) as url:
        yield folder,manifest,url

@pytest.fixture
def pipeline(repo,tmp_path):
    p=Pipeline(repo,tmp_path/'runtime',repo/'contracts/sales.json',repo/'profiles/reference.json')
    try:yield p
    finally:p.close()

@pytest.fixture
def accepted(pipeline,source):
    folder,manifest,url=source
    receipt=pipeline.execute('accepted-baseline',manifest['as_of'],folder,url)
    assert receipt['status']=='ACCEPTED'
    return receipt
