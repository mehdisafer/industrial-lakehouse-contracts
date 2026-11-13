"""Offline bootstrap tests: synthetic metadata/archives, not JDK execution."""
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
from types import SimpleNamespace
import pytest

spec = importlib.util.spec_from_file_location('java_bootstrap', Path(__file__).parents[1]/'scripts/bootstrap_java.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)
URL = 'https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.16%2B8/jdk.tar.gz'


def metadata(digest='a'*64, size=100):
    return [{'release_type':'ga','vendor':'eclipse','release_name':'jdk-17.0.16+8',
             'version_data':{'major':17}, 'binaries':[{
                 'architecture':'x64','os':'linux','image_type':'jdk',
                 'jvm_impl':'hotspot','heap_size':'normal',
                 'package':{'link':URL,'checksum':digest,'size':size}}]}]


def archive_bytes(name='jdk-17.0.16+8/bin/java', kind=None, link=''):
    data=io.BytesIO()
    with tarfile.open(fileobj=data,mode='w:gz') as output:
        entry=tarfile.TarInfo(name);entry.mode=0o755
        if kind is not None:
            entry.type=kind;entry.linkname=link
            output.addfile(entry)
        else:
            payload=b'synthetic fixture, never executed'
            entry.size=len(payload);output.addfile(entry,io.BytesIO(payload))
    return data.getvalue()


def test_selects_exact_platform_and_records_identity():
    selected=bootstrap.select_package(metadata())
    assert selected=={'release':'jdk-17.0.16+8','url':URL,'sha256':'a'*64,'bytes':100}


@pytest.mark.parametrize('mutate',[
    lambda a:a[0].update(release_type='ea'),
    lambda a:a[0]['version_data'].update(major=11),
    lambda a:a[0].update(vendor='other'),
    lambda a:a[0]['binaries'][0].update(architecture='aarch64'),
    lambda a:a[0]['binaries'][0]['package'].update(checksum='invalid'),
    lambda a:a[0]['binaries'][0]['package'].update(size=bootstrap.MAX_ARCHIVE+1),
    lambda a:a[0]['binaries'][0]['package'].update(link='https://github.com/other/archive.tar.gz'),
    lambda a:a[0].update(release_name='jdk-17.0.16+8-early'),
])
def test_rejects_wrong_or_unverifiable_package(mutate):
    assets=metadata();mutate(assets)
    with pytest.raises(ValueError):bootstrap.select_package(assets)


@pytest.mark.parametrize('url',[
    'http://github.com/adoptium/test',
    'https://example.invalid/jdk.tar.gz',
    'https://secret@github.com/adoptium/test',
    'https://github.com:444/adoptium/test',
    'https://github.com/adoptium/test#fragment',
])
def test_rejects_unapproved_download_or_redirect(url):
    with pytest.raises(ValueError):bootstrap.safe_url(url)


def test_extracts_exact_verified_bytes_to_new_home(tmp_path):
    raw=archive_bytes();archive=tmp_path/'jdk.tar.gz';archive.write_bytes(raw)
    home=bootstrap.extract_verified(archive,tmp_path/'java',hashlib.sha256(raw).hexdigest())
    assert home==tmp_path/'java/jdk-17.0.16+8'
    assert (home/'bin/java').read_bytes()==b'synthetic fixture, never executed'
    with pytest.raises(ValueError):bootstrap.extract_verified(archive,tmp_path/'java',hashlib.sha256(raw).hexdigest())


def test_checksum_failure_never_extracts(tmp_path):
    archive=tmp_path/'jdk.tar.gz';archive.write_bytes(archive_bytes())
    with pytest.raises(ValueError,match='checksum'):bootstrap.extract_verified(archive,tmp_path/'java','b'*64)
    assert not (tmp_path/'java').exists()


@pytest.mark.parametrize('name,kind,link',[
    ('../../outside',None,''),('/tmp/unsafe',None,''),
    ('jdk/link',tarfile.SYMTYPE,'../../outside'),('jdk/fifo',tarfile.FIFOTYPE,''),
])
def test_unsafe_archive_refused_before_extraction(tmp_path,name,kind,link):
    raw=archive_bytes(name,kind,link);archive=tmp_path/'jdk.tar.gz';archive.write_bytes(raw)
    with pytest.raises((ValueError,tarfile.FilterError)):
        bootstrap.extract_verified(archive,tmp_path/'java',hashlib.sha256(raw).hexdigest())
    assert not (tmp_path/'java').exists()


def test_install_stub_transport_and_version_process(tmp_path,monkeypatch):
    raw=archive_bytes();digest=hashlib.sha256(raw).hexdigest()
    assets=json.dumps(metadata(digest,len(raw))).encode()
    def opened(url):
        assert url in (bootstrap.API,URL)
        return io.BytesIO(assets if url==bootstrap.API else raw)
    monkeypatch.setattr(bootstrap,'open_official',opened)
    monkeypatch.setattr(bootstrap.subprocess,'run',lambda *a,**kw:SimpleNamespace(stderr='openjdk version "17.0.16"\n',stdout=''))
    result=bootstrap.install(tmp_path/'java',tmp_path/'receipt.json')
    assert result['integrity']=='SHA256_MATCH'
    assert result['signature_verification']=='NOT_RUN'
    assert json.loads((tmp_path/'receipt.json').read_text())['sha256']==digest


def test_truncated_download_never_extracts(tmp_path,monkeypatch):
    raw=archive_bytes();assets=json.dumps(metadata(hashlib.sha256(raw).hexdigest(),len(raw)+1)).encode()
    monkeypatch.setattr(bootstrap,'open_official',lambda url:io.BytesIO(assets if url==bootstrap.API else raw))
    with pytest.raises(ValueError,match='Incomplete'):bootstrap.install(tmp_path/'java',tmp_path/'receipt.json')
    assert not (tmp_path/'java').exists() and not (tmp_path/'receipt.json').exists()
