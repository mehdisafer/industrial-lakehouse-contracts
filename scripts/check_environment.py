"""Read-only capability receipt. Never installs packages or contacts a DB."""
import argparse
from importlib.metadata import version,PackageNotFoundError
import json
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from ilc.canonical import canonical,immutable_write


def inspect(network=False):
    packages={}
    for name in ('psycopg','pyspark','delta-spark','dagster','SQLAlchemy','pytest'):
        try:packages[name]=version(name)
        except PackageNotFoundError:packages[name]='NOT_INSTALLED'
    java=None
    if shutil.which('java'):
        r=subprocess.run(['java','-version'],capture_output=True,timeout=10,text=True)
        java={'returncode':r.returncode,'version_lines':r.stderr.splitlines()[:3]}
    probes={}
    if network:
        for host in ('pypi.org','repo.maven.apache.org','deb.debian.org'):
            try:socket.getaddrinfo(host,443);probes[host]='DNS_RESOLVED'
            except OSError:probes[host]='DNS_UNAVAILABLE'
    missing=[n for n in ('psycopg','pyspark','delta-spark','dagster') if packages[n]=='NOT_INSTALLED']
    return {'schema_version':'ilc-environment/1','python':platform.python_version(),'os':platform.system(),
        'packages':packages,'java':java,'docker_cli_present':shutil.which('docker') is not None,
        'postgres_server_binary_present':shutil.which('postgres') is not None,
        'dependency_gate':'BLOCKED' if missing else 'PACKAGES_PRESENT_NOT_RUNTIME_QUALIFIED',
        'missing_native_packages':missing,'network_dns':probes,
        'postgres_connected':False,'spark_started':False,'dagster_executed':False,
        'openmetadata_product_started':False,'fabric_authenticated':False,
        'credentials_inspected':False,'mutations':0}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--check-public-dns',action='store_true');a=p.parse_args()
    result=inspect(a.check_public_dns);immutable_write(a.output,canonical(result));print(json.dumps(result,indent=2))
    return 2 if result['dependency_gate']=='BLOCKED' else 0

if __name__=='__main__':sys.exit(main())
