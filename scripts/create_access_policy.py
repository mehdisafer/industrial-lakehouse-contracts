"""Create local demo token digests; print fresh tokens once, never write plaintext."""
import argparse
import hashlib
from pathlib import Path
import secrets
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from ilc.canonical import canonical,immutable_write,read_json


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Refusing to replace an existing policy')
    sites=read_json(ROOT/'contracts/sales.json')['sites'];principals=[];tokens=[]
    for name,scope,permissions in [('admin',sites,['report','catalog','evidence']),('site-a',['SITE_A'],['report'])]:
        token=secrets.token_urlsafe(32);tokens.append((name,token))
        principals.append({'name':name,'sites':scope,'permissions':permissions,'token_sha256':hashlib.sha256(token.encode()).hexdigest()})
    immutable_write(args.output,canonical({'schema_version':'ilc-access/1','principals':principals}))
    for name,token in tokens:print(f'{name} token (shown once): {token}')
    print('Use only on loopback. Do not commit these tokens or console output.')

if __name__=='__main__':main()
