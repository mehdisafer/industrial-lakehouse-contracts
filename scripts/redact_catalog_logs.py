"""Bound diagnostic output and redact credential-shaped strings before upload."""
from __future__ import annotations
import os
import re
import sys

MAX_BYTES=2_000_000


def redact(line: str) -> str:
    for key in ('ILC_OM_DB_PASSWORD','ILC_OM_FERNET_KEY'):
        value=os.environ.get(key)
        if value:line=line.replace(value,'[REDACTED]')
    line=re.sub(r'(?i)(Bearer\s+)\S+',r'\1[REDACTED]',line)
    line=re.sub(r'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[REDACTED_JWT]',line)
    line=re.sub(r'(?i)((?:password|accessToken|refreshToken|JWTToken)\s*[=:]\s*)[^\s,}]+',r'\1[REDACTED]',line)
    return line


def main():
    written=0;truncated=False
    # Continue consuming the producer after the output budget is reached so a
    # successful migration is not killed by a downstream broken pipe.
    for line in sys.stdin:
        value=redact(line)
        size=len(value.encode('utf-8'))
        if written+size<=MAX_BYTES:
            sys.stdout.write(value);sys.stdout.flush();written+=size
        elif not truncated:
            print('[DIAGNOSTIC OUTPUT TRUNCATED]');truncated=True

if __name__=='__main__':main()
