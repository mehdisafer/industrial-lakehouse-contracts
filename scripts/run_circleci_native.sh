#!/usr/bin/env bash
# One disposable native CI job. Never connects to a shared or client database.
set -Eeuo pipefail
umask 077
[[ "${CIRCLECI:-}" == "true" ]]
# GitHub App project variables can contain CircleCI display names, not VCS names.
# Verify the checkout origin without printing its authentication material.
python - <<'PYORIGIN'
import subprocess
from urllib.parse import urlsplit
origin=subprocess.check_output(['git','remote','get-url','origin'],text=True).strip()
if origin.startswith('git@github.com:'):
    path=origin[len('git@github.com:'):]
else:
    parsed=urlsplit(origin)
    if parsed.scheme!='https' or parsed.hostname!='github.com':
        raise SystemExit('Unexpected checkout origin host')
    path=parsed.path.lstrip('/')
if path.removesuffix('.git').rstrip('/')!='mehdisafer/industrial-lakehouse-contracts':
    raise SystemExit('Unexpected checkout repository')
PYORIGIN
[[ "${ILC_ALLOW_NATIVE_DEMO:-}" == "1" && "${ILC_NATIVE_TESTS:-}" == "1" ]]
[[ "$(git rev-parse HEAD)" == "${CIRCLE_SHA1:?Expected CircleCI revision}" ]]
[[ ! -e .runtime/circleci-native-qualification ]]
mkdir -p artifacts/native/tests
phase=preflight
started=$SECONDS
finish() {
  code=$?
  trap - EXIT
  python - "$code" "$phase" "$((SECONDS-started))" <<'PY'
import json, os, sys
from pathlib import Path
code,phase,elapsed=sys.argv[1:]
Path('artifacts/native/attempt.json').write_text(json.dumps({
 'exit_code':int(code),'last_phase':phase,'wall_seconds':int(elapsed),
 'commit':os.getenv('CIRCLE_SHA1'),'workflow_id':os.getenv('CIRCLE_WORKFLOW_ID'),
 'job_number':os.getenv('CIRCLE_BUILD_NUM'),'job_url':os.getenv('CIRCLE_BUILD_URL'),
 'classification':'PUBLIC_SYNTHETIC','resource_class':'large',
 'budget_scope':'35-minute command watchdog; setup and artifact overhead not included',
 'billing_credits_observed':None
},indent=2)+'\n')
PY
  exit "$code"
}
trap finish EXIT
python --version
phase=java_bootstrap
timeout --kill-after=20s 4m python scripts/bootstrap_java.py --destination .runtime/java17 --receipt artifacts/native/java-install.json 2>&1 | tee artifacts/native/java-install.log
export JAVA_HOME="$(python -c 'import json; print(json.load(open("artifacts/native/java-install.json"))["java_home"])')"
export PATH="$JAVA_HOME/bin:$PATH"
java -version
export PYSPARK_PYTHON="$(command -v python)"
phase=install
# No lockfile exists. Record the resolved environment; do not claim a locked build.
timeout --kill-after=20s 8m python -m pip install -e '.[native,test]' 2>&1 | tee artifacts/native/install.log
python -m pip check
python -m pip freeze > artifacts/native/resolved-dependencies.txt
phase=postgres_readiness
python - <<'PY'
import json, os, platform, re, subprocess, time
from pathlib import Path
import psycopg
from ilc.sources import validate_pg_dsn
version=subprocess.run(['java','-version'],capture_output=True,text=True,check=True).stderr
match=re.search(r'version "(\d+)',version)
if not match or int(match[1]) not in (17,21):
    raise RuntimeError('Spark 4.0 qualification requires Java 17 or 21')
for key in ('ILC_SOURCE_DSN','ILC_STATE_DSN'):
    p=validate_pg_dsn(os.environ[key])
    if p.host!='127.0.0.1' or p.database!='ilc_demo' or p.username!='ilc_demo':
        raise RuntimeError('Only the disposable CircleCI service is admitted')
deadline=time.monotonic()+60
while True:
    try:
        with psycopg.connect(os.environ['ILC_SOURCE_DSN'],connect_timeout=2) as db:
            server=db.info.server_version
            assert 160000 <= server < 170000, server
            assert db.execute('SELECT current_database()').fetchone()[0]=='ilc_demo'
        break
    except psycopg.OperationalError:
        if time.monotonic()>=deadline: raise RuntimeError('Disposable PostgreSQL not ready') from None
        time.sleep(1)
Path('artifacts/native/environment.json').write_text(json.dumps({
 'python':platform.python_version(),'java':version.splitlines(),
 'postgres_server_version':server,'source_and_state':'loopback ilc_demo',
 'credentials_included':False
},indent=2)+'\n')
PY
python -m compileall -q src tests scripts fabric
python -m ilc.cli validate
phase=native_pytest
timeout --kill-after=30s 10m python -m pytest -m native --basetemp=.runtime/circleci-native-tests --junitxml=artifacts/native/tests/junit.xml 2>&1 | tee artifacts/native/native-tests.log
phase=native_scenarios
timeout --kill-after=30s 20m python scripts/qualify_native.py --output .runtime/circleci-native-qualification --rows 10000 2>&1 | tee artifacts/native/native-qualification.log
phase=verify_evidence
python - <<'PYEXPORT'
from pathlib import Path
from ilc.canonical import immutable_write, read_json
from ilc.storage import batch_path
output=Path('.runtime/circleci-native-qualification')
evidence=output/'evidence'
receipt=read_json(evidence/'accepted-receipt.json')
proof=batch_path(output/'work/runtime',receipt['batch_id'])/'native_final_readback.json'
immutable_write(evidence/'accepted-final-readback.json',proof.read_bytes())
PYEXPORT
python scripts/verify_native_ci.py --evidence .runtime/circleci-native-qualification/evidence --junit artifacts/native/tests/junit.xml --expected-sha "$CIRCLE_SHA1" --output artifacts/native/verified-evidence.json
phase=completed
