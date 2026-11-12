"""Dagster job for the native profile; no import or fallback in reference runs."""
from pathlib import Path
from dagster import Definitions, job, op
from .pipeline import Pipeline

@op(config_schema={name:str for name in ['repo','root','contract','profile','fixture','api_url','key','until']})
def execute_accepted_batch(context):
    cfg=context.op_config
    repo=Path(cfg['repo'])
    pipeline=Pipeline(repo,Path(cfg['root']),repo/cfg['contract'],repo/cfg['profile'])
    try:
        receipt=pipeline.execute(cfg['key'],cfg['until'],Path(cfg['fixture']),cfg['api_url'])
        if receipt['status']!='ACCEPTED':
            raise RuntimeError('The business dataset was not accepted')
        context.add_output_metadata({'batch_id':receipt['batch_id'],
            'captured_rows':receipt['observed_captured_rows'],'target_manifest':receipt['target_manifest_sha256']})
        return receipt
    finally:
        pipeline.close()

@job
def accepted_sales_job():
    execute_accepted_batch()

defs=Definitions(jobs=[accepted_sales_job])
