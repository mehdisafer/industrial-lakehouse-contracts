"""Install a checksum-verified Temurin 17 JDK into a new disposable CI directory.

The official API selects the current Linux/x64 GA JDK 17 archive. The resolved
release, URL and digest are recorded; this is not a transitive toolchain lock.
No OS packages, persistent Java settings or account credentials are modified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

API = ('https://api.adoptium.net/v3/assets/feature_releases/17/ga'
       '?architecture=x64&heap_size=normal&image_type=jdk&jvm_impl=hotspot'
       '&os=linux&page=0&page_size=1&vendor=eclipse')
HOSTS = {'api.adoptium.net', 'github.com', 'release-assets.githubusercontent.com',
         'objects.githubusercontent.com'}
MAX_ARCHIVE = 256 * 1024 * 1024
MAX_UNPACKED = 1024 * 1024 * 1024


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def safe_url(url: str) -> str:
    parsed = urlsplit(url)
    require(parsed.scheme == 'https' and parsed.hostname in HOSTS and
            not parsed.username and not parsed.password and
            parsed.port in (None, 443) and not parsed.fragment,
            'Only HTTPS official JDK download hosts are permitted')
    return url


class OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return super().redirect_request(request, fp, code, message, headers, safe_url(newurl))


def open_official(url: str):
    request = Request(safe_url(url), headers={'User-Agent': 'P01-native-qualification/1'})
    return build_opener(OfficialRedirects()).open(request, timeout=30)


def select_package(assets: list) -> dict:
    require(isinstance(assets, list), 'Unexpected Adoptium response')
    for release in assets:
        if release.get('release_type') != 'ga' or release.get('version_data', {}).get('major') != 17:
            continue
        if release.get('vendor') != 'eclipse':
            continue
        for binary in release.get('binaries', []):
            if any(binary.get(key) != value for key, value in
                   {'architecture': 'x64', 'os': 'linux', 'image_type': 'jdk',
                    'jvm_impl': 'hotspot', 'heap_size': 'normal'}.items()):
                continue
            package = binary.get('package', {})
            url = safe_url(package.get('link', ''))
            parsed = urlsplit(url)
            require(parsed.hostname == 'github.com' and
                    parsed.path.startswith('/adoptium/temurin17-binaries/releases/download/') and
                    parsed.path.endswith('.tar.gz'), 'Not a Temurin 17 release archive')
            digest = package.get('checksum', '')
            size = package.get('size')
            require(bool(re.fullmatch('[0-9a-f]{64}', digest)), 'Missing SHA-256')
            require(type(size) is int and 0 < size <= MAX_ARCHIVE, 'Invalid archive size')
            name = release.get('release_name', '')
            require(bool(re.fullmatch(r'jdk-17(?:\.\d+){0,2}\+\d+', name)), 'Unexpected JDK release name')
            return {'release': name, 'url': url, 'sha256': digest, 'bytes': size}
    raise ValueError('No GA Linux/x64 Temurin 17 JDK found')


def extract_verified(archive: Path, destination: Path, digest: str) -> Path:
    require(hashlib.sha256(archive.read_bytes()).hexdigest() == digest,
            'JDK archive checksum mismatch')
    require(not destination.exists(), 'Refusing an existing JDK destination')
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        require(0 < len(members) <= 20000 and
                sum(max(0, m.size) for m in members) <= MAX_UNPACKED,
                'Unpacked JDK exceeds budget')
        names = set()
        for member in members:
            path = PurePosixPath(member.name)
            require(not path.is_absolute() and '..' not in path.parts and '\\' not in member.name,
                    'Unsafe JDK archive path')
            require(member.name not in names, 'Duplicate JDK archive entry')
            names.add(member.name)
            require(member.isfile() or member.isdir() or member.issym() or member.islnk(),
                    'Unsupported JDK archive entry')
            # Validate links against the destination before extracting any entries.
            tarfile.data_filter(member, str(destination))
        destination.mkdir(parents=True)
        tar.extractall(destination, members=members, filter='data')
    homes = [p.parent.parent for p in destination.glob('*/bin/java') if p.is_file()]
    require(len(homes) == 1, 'Expected exactly one JDK home')
    return homes[0].resolve()


def install(destination: Path, receipt: Path) -> dict:
    require(not destination.exists() and not receipt.exists(), 'Refusing existing JDK output')
    with open_official(API) as response:
        body = response.read(2 * 1024 * 1024 + 1)
    require(len(body) <= 2 * 1024 * 1024, 'Oversized JDK metadata')
    package = select_package(json.loads(body))
    destination.parent.mkdir(parents=True, exist_ok=True)
    archive = destination.parent / (destination.name + '.tar.gz')
    # Exclusive creation; a failed download remains available for diagnosis.
    with archive.open('xb') as output, open_official(package['url']) as response:
        received = 0
        while chunk := response.read(1024 * 1024):
            received += len(chunk)
            require(received <= package['bytes'], 'JDK download exceeds declared size')
            output.write(chunk)
    require(received == package['bytes'], 'Incomplete JDK download')
    home = extract_verified(archive, destination, package['sha256'])
    result = subprocess.run([str(home / 'bin/java'), '-version'],
                            check=True, capture_output=True, text=True, timeout=20)
    version = result.stderr + result.stdout
    require(bool(re.search(r'version "17(?:\.|\")', version)), 'Installed Java is not 17')
    proof = {**package, 'java_home': str(home), 'version_output': version.splitlines(),
             'integrity': 'SHA256_MATCH', 'selection': 'official_latest_GA_major_17',
             'signature_verification': 'NOT_RUN'}
    receipt.parent.mkdir(parents=True, exist_ok=True)
    with receipt.open('x', encoding='utf-8') as output:
        output.write(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof, indent=2))
    return proof


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    install(args.destination, args.receipt)


if __name__ == '__main__':
    main()
