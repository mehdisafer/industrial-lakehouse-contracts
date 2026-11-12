"""Opt-in, READ-ONLY Fabric inventory. Not a deployment or provider acceptance test."""
from __future__ import annotations
import argparse
import json
import os
import uuid
from urllib.parse import urlsplit
import httpx


def inspect_workspace(workspace_id: str, token: str, *, transport=None):
    workspace_id=str(uuid.UUID(workspace_id))
    base='https://api.fabric.microsoft.com'
    url=f'{base}/v1/workspaces/{workspace_id}/items'
    seen=set();items=[]
    with httpx.Client(headers={'Authorization':'Bearer '+token},timeout=20,follow_redirects=False,
                      trust_env=False,transport=transport) as client:
        for _ in range(20):
            parsed=urlsplit(url)
            if parsed.scheme!='https' or parsed.netloc!='api.fabric.microsoft.com' or parsed.path!=f'/v1/workspaces/{workspace_id}/items' or parsed.fragment:
                raise ValueError('Refusing to forward a credential to an unapproved continuation target')
            if url in seen:raise ValueError('Pagination cycle')
            seen.add(url)
            response=client.get(url)
            if response.status_code!=200:
                # Do not serialize server body, token or user workspace details.
                raise RuntimeError(f'Fabric inventory returned HTTP {response.status_code}')
            body=response.json()
            if not isinstance(body.get('value'),list):raise ValueError('Invalid item list')
            for item in body['value']:
                items.append({'id':str(uuid.UUID(item['id'])),'type':item['type']})
            continuation=body.get('continuationUri')
            if not continuation:
                return {'status':'READ_ONLY_INVENTORY_OBSERVED','workspace_id':workspace_id,
                        'items':items,'pages':len(seen),'integration_qualified':False,
                        'power_bi_report_tested':False,'mutations':0}
            url=continuation
    raise ValueError('Pagination budget exceeded')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace-id',required=True)
    parser.add_argument('--allow-read-only-network',action='store_true')
    args=parser.parse_args()
    if not args.allow_read_only_network:parser.error('Explicit read-only network opt-in required')
    token=os.environ.get('FABRIC_ACCESS_TOKEN')
    if not token:parser.error('Provide FABRIC_ACCESS_TOKEN outside Git')
    print(json.dumps(inspect_workspace(args.workspace_id,token),indent=2))

if __name__=='__main__':main()
