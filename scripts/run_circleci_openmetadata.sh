#!/usr/bin/env bash
# Job-owned ephemeral containers only. No default runner or local PC execution.
set -Eeuo pipefail
umask 077
[[ "${CIRCLECI:-}" == "true" && "${ILC_ALLOW_OPENMETADATA_DEMO:-}" == "1" ]]
[[ "$(git rev-parse HEAD)" == "${CIRCLE_SHA1:?Exact revision required}" ]]
python3 - <<'PY'
import subprocess
from urllib.parse import urlsplit
origin=subprocess.check_output(['git','remote','get-url','origin'],text=True).strip()
if origin.startswith('git@github.com:'): path=origin.split(':',1)[1]
else:
 p=urlsplit(origin)
 if p.hostname!='github.com' or p.scheme!='https':raise SystemExit('Unexpected Git host')
 path=p.path.lstrip('/')
if path.removesuffix('.git').rstrip('/')!='mehdisafer/industrial-lakehouse-contracts':
 raise SystemExit('Unexpected checkout repository')
PY
[[ ! -e .runtime/openmetadata-control && ! -e artifacts/openmetadata ]]
mkdir -p .runtime/openmetadata-control/keys artifacts/openmetadata
export COMPOSE_PROJECT_NAME="ilcg3_${CIRCLE_BUILD_NUM:?Job number required}_${CIRCLE_SHA1:0:8}"
[[ "$COMPOSE_PROJECT_NAME" =~ ^ilcg3_[0-9]+_[a-f0-9]{8}$ ]]
[[ -z "$(docker ps -aq --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME")" ]]
export ILC_OM_KEYS="$PWD/.runtime/openmetadata-control/keys"
export ILC_OM_DB_PASSWORD="$(python3 -c 'import secrets;print(secrets.token_hex(24))')"
export ILC_OM_FERNET_KEY="$(python3 -c 'import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())')"
# Generated keys apply only to the disposable server. Never upload these files.
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out .runtime/openmetadata-control/private.pem 2>/dev/null
openssl pkcs8 -topk8 -inform PEM -outform DER -in .runtime/openmetadata-control/private.pem -nocrypt -out "$ILC_OM_KEYS/private_key.der"
openssl rsa -in .runtime/openmetadata-control/private.pem -pubout -outform DER -out "$ILC_OM_KEYS/public_key.der" 2>/dev/null
# The image may use a different uid. This job-owned directory is never exported.
chmod 755 "$ILC_OM_KEYS"
chmod 644 "$ILC_OM_KEYS/"*.der
compose=(docker compose -f infra/compose.openmetadata.yml --project-name "$COMPOSE_PROJECT_NAME")
phase=preflight
started=$SECONDS
previous_map_count="$(sysctl -n vm.max_map_count)"
finish() {
 code=$?; trap - EXIT
 set +e
 # Filter and bound logs before artifact publication. Do not dump container env.
 timeout 15s "${compose[@]}" logs --no-color --tail=250 db search migrate server 2>&1 | python3 scripts/redact_catalog_logs.py > artifacts/openmetadata/services.log
 timeout 5s "${compose[@]}" ps --all --format json > artifacts/openmetadata/containers.json
 timeout 30s "${compose[@]}" stop -t 10 >/dev/null 2>&1
 stop_code=$?
 sudo sysctl -w "vm.max_map_count=$previous_map_count" >/dev/null 2>&1
 sysctl_code=$?
 python3 - "$code" "$phase" "$((SECONDS-started))" "$stop_code" "$sysctl_code" <<'PY'
import json,os,sys
from pathlib import Path
Path('artifacts/openmetadata/job-attempt.json').write_text(json.dumps({
 'exit_code':int(sys.argv[1]),'phase':sys.argv[2],'wall_seconds':int(sys.argv[3]),
 'source_sha':os.environ.get('CIRCLE_SHA1'),'workflow_id':os.environ.get('CIRCLE_WORKFLOW_ID'),
 'job_number':os.environ.get('CIRCLE_BUILD_NUM'),'resource_class':'large','executor':'machine',
 'compose_project':os.environ.get('COMPOSE_PROJECT_NAME'),'billing_credits_observed':None,
 'cleanup':{'scope':'Job-owned services only; no DROP or volume deletion','stop_exit_code':int(sys.argv[4]),'sysctl_restore_exit_code':int(sys.argv[5])},
 'budget_scope':'25-minute command watchdog; runner provisioning/artifact overhead excluded'},indent=2)+'\n')
PY
 exit "$code"
}
trap finish EXIT
sudo sysctl -w vm.max_map_count=1048576 >/dev/null
"${compose[@]}" config --quiet
phase=pull_images
# Serial phases and one workflow; no automatic retry or paid cache.
timeout --kill-after=20s 7m "${compose[@]}" pull --quiet
# Tester image is also recorded by digest, not misrepresented as a locked tag.
timeout --kill-after=20s 3m docker pull cimg/python:3.12 >/dev/null
python3 - <<'PY'
import json,subprocess
from pathlib import Path
images=['postgres:16','docker.elastic.co/elasticsearch/elasticsearch:9.3.0','docker.getcollate.io/openmetadata/server:1.12.0','cimg/python:3.12']
records=[]
for name in images:
 d=json.loads(subprocess.check_output(['docker','image','inspect',name],text=True))[0]
 if not d.get('RepoDigests'):raise SystemExit('Missing resolved image digest')
 records.append({'requested':name,'image_id':d['Id'],'repo_digests':d['RepoDigests'],'architecture':d['Architecture'],'os':d['Os']})
Path('artifacts/openmetadata/images.json').write_text(json.dumps(records,indent=2)+'\n')
PY
phase=start_dependencies
timeout --kill-after=20s 4m "${compose[@]}" up -d --wait db search
phase=migration
timeout --kill-after=20s 6m "${compose[@]}" up --no-deps --abort-on-container-exit --exit-code-from migrate migrate 2>&1 | python3 scripts/redact_catalog_logs.py | tee artifacts/openmetadata/migration.log
phase=start_server
"${compose[@]}" up -d --no-deps server
python3 - <<'PY'
import time,urllib.request,urllib.error
end=time.monotonic()+180
while time.monotonic()<end:
 try:
  with urllib.request.urlopen('http://127.0.0.1:8585/api/v1/system/version',timeout=3) as r:
   if r.status==200:break
 except urllib.error.HTTPError as e:
  if e.code==401:break
 except (OSError,TimeoutError):pass
 time.sleep(2)
else:raise SystemExit('OpenMetadata API readiness timeout')
PY
phase=live_qualification
# Python dependencies are isolated in an ignored workspace virtualenv. The
# tester has host-network access only inside this new disposable CircleCI VM.
timeout --kill-after=30s 7m docker run --rm --network host \
 --user "$(id -u):$(id -g)" --workdir "$PWD" --volume "$PWD:$PWD" \
 --env HOME=/tmp/ilc-home --env ILC_ALLOW_OPENMETADATA_DEMO=1 --env "CIRCLE_SHA1=$CIRCLE_SHA1" \
 --env PYTHONUTF8=1 --env PYTHONDONTWRITEBYTECODE=1 --env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
 cimg/python:3.12 bash -c '
   set -euo pipefail
   mkdir -p "$HOME"
   git config --global --add safe.directory "$PWD"
   python -m venv .runtime/openmetadata-venv
   .runtime/openmetadata-venv/bin/python -m pip install -e ".[test]" --disable-pip-version-check >/dev/null
   .runtime/openmetadata-venv/bin/python -m pip check
   .runtime/openmetadata-venv/bin/python -m pytest tests/test_openmetadata_live_harness.py --junitxml=artifacts/openmetadata/harness-junit.xml
   .runtime/openmetadata-venv/bin/python scripts/qualify_openmetadata.py --output .runtime/openmetadata-live
 ' 2>&1 | python3 scripts/redact_catalog_logs.py | tee artifacts/openmetadata/qualification.log
phase=completed
