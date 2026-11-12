"""Harness boundary checks; they never pretend that native engines ran."""
import importlib.util
import os
from pathlib import Path
import pytest
from ilc.errors import NativeUnavailable

def load(repo):
    spec=importlib.util.spec_from_file_location('p01_native_harness',repo/'scripts/qualify_native.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def test_missing_dependencies_refuse_before_output_creation(repo,tmp_path,monkeypatch):
    module=load(repo)
    monkeypatch.setattr(module,'require_native',lambda:(_ for _ in ()).throw(NativeUnavailable('missing')))
    with pytest.raises(NativeUnavailable):module.qualify(tmp_path/'not-created')
    assert not (tmp_path/'not-created').exists()

def test_native_authorization_not_implied_by_imports(repo,tmp_path,monkeypatch):
    module=load(repo);monkeypatch.setattr(module,'require_native',lambda:None)
    monkeypatch.delenv('ILC_ALLOW_NATIVE_DEMO',raising=False)
    with pytest.raises(NativeUnavailable):module.qualify(tmp_path/'not-created')
    assert not (tmp_path/'not-created').exists()

def test_source_schema_is_separate_for_each_fixture(repo,tmp_path):
    module=load(repo);template={'source_schema':'ilc_demo','engine':'native_spark'}
    names={module.scenario_profile(template,tmp_path,name)['source_schema']
        for name in ('base','recovery','duplicate_key','invalid_amount','schema_drift')}
    assert len(names)==5 and all(n.startswith('ilc_demo_') and len(n)<=63 for n in names)
    assert template['source_schema']=='ilc_demo'
    with pytest.raises(ValueError):module.scenario_profile(template,tmp_path,'production')
