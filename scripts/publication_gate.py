"""Bounded, fail-closed secret scan of reachable P01 Git history before publication.

Run only in the dedicated CircleCI checkout. All remote heads/tags are fetched;
unique blob bytes and commit metadata are exported to a fresh local directory.
Gitleaks scans that directory (including archives), not an unchecked git-log
pipeline. This is a rule-based disclosure gate, not a security certification.
No repository visibility, GitHub permissions, shared files or billing are changed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import string
import subprocess
import tarfile
import tempfile
import time
from urllib.request import urlopen, Request

REPOSITORY = 'mehdisafer/industrial-lakehouse-contracts'
VERSION = '8.30.1'
ARCHIVE_URL = 'https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz'
ARCHIVE_SHA256 = '551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb'
ARCHIVE_BYTES = 8230402
MAX_BLOB_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_OBJECTS = 10000

def require(condition, message):
    if not condition:
        raise ValueError(message)

def git(repo, *args):
    process = subprocess.run(['git', *args], cwd=repo, capture_output=True, timeout=120)
    require(process.returncode == 0, 'Git operation failed: '+args[0])
    return process.stdout

def valid_origin(value):
    return value.strip().removesuffix('.git') in {
        'https://github.com/'+REPOSITORY, 'git@github.com:'+REPOSITORY,
        'ssh://git@github.com/'+REPOSITORY}

def safe_relative(name):
    p=PurePosixPath(name)
    require(bool(name) and not p.is_absolute() and '..' not in p.parts and '\\' not in name
            and '\x00' not in name, 'Unsafe history path')
    return p

def export_history(repo: Path, destination: Path):
    require(not destination.exists(), 'History output must be new')
    destination.mkdir(parents=True)
    objects=git(repo,'rev-list','--objects','--all').decode().splitlines()
    require(0 < len(objects) <= MAX_OBJECTS, 'History inventory outside the bounded budget')
    seen=set(); inventory=[]; total=0; commits=0
    for line in objects:
        sha, _, name=line.partition(' ')
        require(re.fullmatch('[0-9a-f]{40}',sha) is not None, 'Invalid Git object identity')
        if sha in seen: continue
        seen.add(sha)
        kind=git(repo,'cat-file','-t',sha).decode().strip()
        if kind not in {'blob','commit','tag'}: continue
        size=int(git(repo,'cat-file','-s',sha))
        require(size <= MAX_BLOB_BYTES and total+size <= MAX_TOTAL_BYTES, 'History bytes exceed scan budget')
        data=git(repo,'cat-file',kind,sha)
        require(len(data)==size, 'Incomplete Git object read')
        require(hashlib.sha1(f'{kind} {size}\0'.encode()+data).hexdigest()==sha, 'Git object bytes do not match identity')
        relative=safe_relative(name) if kind=='blob' and name else PurePosixPath(kind+'.txt')
        path=destination/kind/sha/relative
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        inventory.append({'sha':sha,'kind':kind,'path':str(relative),'bytes':size,
                          'sha256':hashlib.sha256(data).hexdigest()})
        total+=size;commits+=kind=='commit'
    blobs=sum(o['kind']=='blob' for o in inventory)
    require(blobs>0 and commits>0, 'No source/history scanned')
    return {'objects':inventory,'unique_blobs':blobs,'commits':commits,'bytes':total}

def install_scanner(directory: Path):
    archive=directory/'gitleaks.tar.gz'
    with urlopen(Request(ARCHIVE_URL,headers={'User-Agent':'P01-publication-gate/1'}),timeout=30) as response:
        raw=response.read(ARCHIVE_BYTES+1)
    require(len(raw)==ARCHIVE_BYTES and hashlib.sha256(raw).hexdigest()==ARCHIVE_SHA256,
            'Gitleaks archive identity mismatch')
    archive.write_bytes(raw)
    with tarfile.open(archive,'r:gz') as tf:
        matches=[m for m in tf.getmembers() if m.name=='gitleaks']
        require(len(matches)==1 and matches[0].isfile() and matches[0].size < 40*1024*1024,
                'Unexpected scanner archive member')
        stream=tf.extractfile(matches[0]);require(stream is not None,'Scanner binary absent')
        binary=directory/'gitleaks';binary.write_bytes(stream.read());binary.chmod(0o700)
    version=subprocess.run([str(binary),'version'],capture_output=True,text=True,check=True,timeout=20).stdout.strip()
    require(version==VERSION,'Wrong scanner version')
    return binary

def scan(binary: Path, target: Path, report: Path):
    env={k:v for k,v in os.environ.items() if not k.startswith('GITLEAKS_')}
    command=[str(binary),'dir',str(target),'--no-banner','--no-color','--redact=100',
             '--ignore-gitleaks-allow','--max-archive-depth=2','--max-decode-depth=2',
             '--timeout=120','--report-format=json','--report-path='+str(report)]
    process=subprocess.run(command,cwd=target.parent,env=env,capture_output=True,timeout=150)
    require(process.returncode in (0,1), 'Scanner did not complete successfully')
    require(report.is_file(), 'Scanner omitted its result')
    result=json.loads(report.read_text())
    require(isinstance(result,list), 'Scanner result is not a finding list')
    require((process.returncode==0)==(len(result)==0), 'Scanner exit/result disagreement')
    # Never persist arbitrary log text, line content, matches or secret values.
    findings=[{k:f.get(k) for k in ('RuleID','File','StartLine','Fingerprint')} for f in result]
    return findings

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    require(os.environ.get('CIRCLECI')=='true','Only a disposable CircleCI checkout is admitted')
    expected=os.environ.get('CIRCLE_SHA1','')
    require(re.fullmatch('[0-9a-f]{40}',expected) is not None,'Exact source SHA required')
    require(git(root,'rev-parse','HEAD').decode().strip()==expected,'Wrong checkout')
    require(not git(root,'status','--porcelain','--untracked-files=no').strip(),
            'Tracked checkout differs from its committed identity')
    require(valid_origin(git(root,'remote','get-url','origin').decode()),'Wrong repository origin')
    require(not args.output.exists(),'Use a new audit output directory')
    args.output.mkdir(parents=True);started=time.monotonic()
    result={'source_sha':expected,'status':'NOT_COMPLETED','billing_credits_observed':None}
    try:
        if git(root,'rev-parse','--is-shallow-repository').strip()==b'true':
            git(root,'fetch','--unshallow','--no-recurse-submodules','origin')
        git(root,'fetch','--no-recurse-submodules','origin',
            '+refs/heads/*:refs/remotes/origin/*','+refs/tags/*:refs/tags/*')
        require(git(root,'rev-parse','--is-shallow-repository').strip()==b'false','History remains shallow')
        refs=git(root,'for-each-ref','--format=%(refname) %(objectname)','refs/remotes/origin','refs/tags').decode().splitlines()
        require(bool(refs),'No fetched refs')
        with tempfile.TemporaryDirectory(prefix='ilc-publication-') as temp:
            tmp=Path(temp);inventory=export_history(root,tmp/'history');binary=install_scanner(tmp)
            control=tmp/'positive-control';control.mkdir()
            fake='ghp_'+''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(36))
            (control/'synthetic.txt').write_text('access_token="'+fake+'"\n')
            positive=scan(binary,control,tmp/'positive.json')
            require(any(f['RuleID']=='github-pat' for f in positive),'Positive control did not detect a synthetic GitHub-token pattern')
            findings=scan(binary,tmp/'history',tmp/'history-scan.json')
            result.update(scanner={'name':'Gitleaks','version':VERSION,'archive_sha256':ARCHIVE_SHA256,
                          'signature_verification':'NOT_RUN','positive_control_detected':True},
                          refs=refs,unique_blobs=inventory['unique_blobs'],commits=inventory['commits'],
                          bytes_scanned=inventory['bytes'],finding_count=len(findings),findings=findings)
            (args.output/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
            require(not findings,'Potential secret findings require review; publication refused')
        result['status']='RULE_BASED_HISTORY_SCAN_NO_FINDINGS'
        result['limits']=['Reachable Git objects and commit metadata only; not GitHub issues/actions/CircleCI settings',
            'Default Gitleaks rules plus a positive control; no guarantee that all confidential information is detected',
            'No dependency vulnerability, ownership or license certification',
            'Temporary export directories are deleted; no repository history is rewritten']
    finally:
        result['elapsed_seconds']=round(time.monotonic()-started,3)
        (args.output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k not in {'findings','refs'}},indent=2))

if __name__=='__main__':main()
