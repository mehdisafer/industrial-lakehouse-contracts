"""Offline guards for the publication scanner; not a real secret scan."""
import importlib.util
import subprocess
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('publication_gate',ROOT/'scripts/publication_gate.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

@pytest.mark.parametrize('origin',[
 'https://github.com/mehdisafer/industrial-lakehouse-contracts.git',
 'git@github.com:mehdisafer/industrial-lakehouse-contracts.git',
 'ssh://git@github.com/mehdisafer/industrial-lakehouse-contracts'])
def test_exact_repository_origins(origin):assert gate.valid_origin(origin)

@pytest.mark.parametrize('origin',[
 'https://github.com/another/repository',
 'https://token@github.com/mehdisafer/industrial-lakehouse-contracts',
 'https://github.com.evil.example/mehdisafer/industrial-lakehouse-contracts',
 'https://github.com/mehdisafer/industrial-lakehouse-contracts/extra'])
def test_other_origins_refused(origin):assert not gate.valid_origin(origin)

@pytest.mark.parametrize('name',['../leak','/etc/passwd','a/../../b','a\\b',''])
def test_export_path_refuses_escape(name):
 with pytest.raises(ValueError):gate.safe_relative(name)

def test_deleted_historical_blob_is_still_exported(tmp_path):
 repo=tmp_path/'repo';repo.mkdir()
 def git(*args):return subprocess.check_output(['git',*args],cwd=repo)
 git('init','-q');git('config','user.name','P01 test');git('config','user.email','test@example.invalid')
 (repo/'retired.txt').write_text('historical content\n');git('add','.');git('commit','-qm','first')
 (repo/'retired.txt').unlink();(repo/'current.txt').write_text('current content\n')
 git('add','-A');git('commit','-qm','second')
 exported=tmp_path/'export';result=gate.export_history(repo,exported)
 assert result['commits']==2 and result['unique_blobs']==2
 assert any(p.name=='retired.txt' and p.read_text()=='historical content\n' for p in exported.rglob('*') if p.is_file())

def test_existing_export_is_never_overwritten(tmp_path):
 with pytest.raises(ValueError):gate.export_history(tmp_path,tmp_path)

def test_git_failure_is_not_a_scan_success(tmp_path):
 with pytest.raises(ValueError):gate.git(tmp_path,'rev-parse','HEAD')

def test_non_ci_run_never_creates_output(monkeypatch,tmp_path):
 monkeypatch.delenv('CIRCLECI',raising=False)
 monkeypatch.setattr('sys.argv',['publication_gate.py','--output',str(tmp_path/'output')])
 with pytest.raises(ValueError):gate.main()
 assert not (tmp_path/'output').exists()
