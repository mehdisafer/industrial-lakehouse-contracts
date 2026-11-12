"""Optional native adapters. Never fall back to the reference engine on failure.

This module is shipped for qualification with real PostgreSQL / Spark / Delta.
It is not labelled validated unless those paths have actually been executed.
"""
from __future__ import annotations
import importlib.util
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from .canonical import canonical, digest, read_json, IDENTIFIER
from .contracts import DECIMAL
from .errors import NativeUnavailable, IntegrityError, SourceError
from .sources import validate_pg_dsn


def require_native():
    missing=[name for name in ['psycopg','pyspark','delta','dagster'] if importlib.util.find_spec(name) is None]
    if missing:
        raise NativeUnavailable('Missing native dependencies: '+', '.join(missing))


def seed_postgres(fixture: Path, contract: dict, profile: dict):
    """Create new source tables only in a dedicated ilc_demo database/schema.

    Existing source tables are refused, not truncated or overwritten.
    """
    if os.environ.get('ILC_ALLOW_NATIVE_DEMO')!='1':
        raise NativeUnavailable('Explicit native demo initialization opt-in is required')
    require_native()
    import psycopg
    from psycopg import sql
    parsed=validate_pg_dsn(os.environ.get('ILC_SOURCE_DSN',''))
    schema=profile['source_schema']
    if not parsed.database.startswith('ilc_demo') or not schema.startswith('ilc_demo') or not IDENTIFIER.fullmatch(schema):
        raise SourceError('Initialization is confined to ilc_demo names')
    with psycopg.connect(parsed.set(drivername='postgresql').render_as_string(hide_password=False),connect_timeout=5) as db:
        db.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(sql.Identifier(schema)))
        for name, source in profile['entity_sources'].items():
            if source['kind']!='database':
                continue
            table=source['location']
            exists=db.execute('SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s',(schema,table)).fetchone()
            if exists:
                raise SourceError('Source table already exists; no overwrite is authorized')
            data=read_json(fixture/f'{name}.json')
            fields=[f['name'] for f in contract['entities'][name]['fields']]
            db.execute(sql.SQL('CREATE TABLE {}.{} ({})').format(sql.Identifier(schema),sql.Identifier(table),
                sql.SQL(',').join(sql.SQL('{} TEXT').format(sql.Identifier(f)) for f in fields)))
            with db.cursor() as cursor:
                query=sql.SQL('INSERT INTO {}.{} ({}) VALUES ({})').format(sql.Identifier(schema),sql.Identifier(table),
                    sql.SQL(',').join(map(sql.Identifier,fields)),sql.SQL(',').join(sql.Placeholder() for _ in fields))
                cursor.executemany(query,[[row[f] for f in fields] for row in data])
        server_version=db.info.server_version
    return {'status':'SEEDED_NEW_SYNTHETIC_TABLES','server_version':server_version,'schema':schema}


def materialize_delta(stage: Path, silver: dict, expected_facts: list, expected_summary: list, contract: dict):
    require_native()
    from pyspark.sql import types as T
    os.environ.setdefault('SPARK_LOCAL_IP','127.0.0.1')
    os.environ['TZ']='UTC'
    if hasattr(time,'tzset'):
        time.tzset()
    spark = native_spark_session()
    def sql_type(field):
        if field['type']=='integer': return T.LongType()
        if field['type']=='string': return T.StringType()
        if field['type']=='timestamp_utc': return T.TimestampType()
        precision,scale=map(int,DECIMAL.fullmatch(field['type']).groups())
        return T.DecimalType(precision,scale)
    def typed(value,field):
        if value is None:return None
        if field['type']=='timestamp_utc':return datetime.fromisoformat(value.replace('Z','+00:00'))
        if DECIMAL.fullmatch(field['type']):return Decimal(value)
        return value
    try:
        counts={}
        for name,entity in contract['entities'].items():
            schema=T.StructType([T.StructField(f['name'],sql_type(f),f['nullable']) for f in entity['fields']])
            data=[tuple(typed(row[f['name']],f) for f in entity['fields']) for row in silver[name]]
            frame=spark.createDataFrame(data,schema=schema)
            path=stage/'delta'/'silver'/name
            frame.write.format('delta').mode('errorifexists').save(str(path))
            pinned=spark.read.format('delta').option('versionAsOf',0).load(str(path))
            counts[name]=pinned.count()
            if counts[name]!=len(silver[name]):
                raise IntegrityError('Native Silver count differs')
            pinned.createOrReplaceTempView('ilc_'+name)
        for dim, source in [('dim_customer','customers'),('dim_product','products')]:
            path=stage/'delta'/'gold'/dim
            spark.table('ilc_'+source).write.format('delta').mode('errorifexists').save(str(path))
            actual=[normalize_native_row(row) for row in spark.read.format('delta').option('versionAsOf',0).load(str(path)).collect()]
            if sorted(actual,key=canonical)!=sorted(silver[source],key=canonical):
                raise IntegrityError('Native snapshot dimension differs from Silver')
        site_path=stage/'delta'/'gold'/'dim_site'
        spark.createDataFrame([(site,) for site in contract['sites']],schema='site_id string').write.format('delta').mode('errorifexists').save(str(site_path))
        if {r.site_id for r in spark.read.format('delta').option('versionAsOf',0).load(str(site_path)).collect()}!=set(contract['sites']):
            raise IntegrityError('Native site dimension differs from its contract')
        facts=spark.sql('''
            WITH shipped AS (
             SELECT s.order_id,s.line_id,SUM(s.quantity) AS shipped_qty,
                    SUM(CASE WHEN s.delivered_at<=o.promised_at THEN s.quantity ELSE 0 END) AS on_time_qty
             FROM ilc_shipments s JOIN ilc_orders o ON o.order_id=s.order_id GROUP BY s.order_id,s.line_id
            )
            SELECT l.order_id,l.line_id,o.customer_id,o.site_id,o.currency,l.product_id,l.quantity,
              l.amount AS ordered_amount,COALESCE(s.shipped_qty,0L) AS shipped_qty,
              COALESCE(s.on_time_qty,0L) AS on_time_qty,
              l.quantity-COALESCE(s.shipped_qty,0L) AS backlog_qty,
              CAST((l.quantity-COALESCE(s.shipped_qty,0L))*l.unit_price AS DECIMAL(18,2)) AS backlog_amount
            FROM ilc_order_lines l JOIN ilc_orders o ON l.order_id=o.order_id
            LEFT JOIN shipped s ON s.order_id=l.order_id AND s.line_id=l.line_id
        ''')
        facts.createOrReplaceTempView('ilc_fact')
        summaries=spark.sql('''
            SELECT site_id,currency,COUNT(DISTINCT order_id) AS order_count,COUNT(*) AS line_count,
              SUM(quantity) AS quantity,SUM(shipped_qty) AS shipped_qty,SUM(on_time_qty) AS on_time_qty,
              SUM(backlog_qty) AS backlog_qty,SUM(ordered_amount) AS ordered_amount,SUM(backlog_amount) AS backlog_amount
            FROM ilc_fact GROUP BY site_id,currency
        ''')
        for name,frame,expected in [('fact_order_fulfillment',facts,expected_facts),('site_kpi',summaries,expected_summary)]:
            path=stage/'delta'/'gold'/name
            frame.write.format('delta').mode('errorifexists').save(str(path))
            actual=[normalize_native_row(row) for row in spark.read.format('delta').option('versionAsOf',0).load(str(path)).collect()]
            if sorted(actual,key=canonical)!=sorted(expected,key=canonical):
                raise IntegrityError('Native Gold differs from the independently computed reference')
        return {'status':'EXECUTED_AND_RECONCILED','spark_version':spark.version,
                'silver_counts':counts,'delta_table_version':0,'gold_fact_rows':len(expected_facts),
                'gold_result_sha256':digest(sorted(expected_facts,key=canonical)),
                'scope':'bounded single-host native materialization; not distributed scale qualification'}
    finally:
        spark.stop()



def normalize_native_row(row):
    """Normalize Spark scalars without truncating a contractual decimal scale.

    Spark timestamps are read in the UTC session created below. Decimal values
    retain their declared scale; hard-coded two-place formatting loses data on
    metadata-only extensions such as decimal(12,4).
    """
    result = {}
    for name, value in row.asDict(recursive=True).items():
        if isinstance(value, Decimal):
            result[name] = format(value, "f")
        elif isinstance(value, datetime):
            aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
            result[name] = aware.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        else:
            result[name] = value
    return result


def native_spark_session():
    """Create the explicitly requested real engine; never substitute a fake."""
    require_native()
    from delta import configure_spark_with_delta_pip
    from pyspark.sql import SparkSession
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    os.environ["TZ"] = "UTC"
    if hasattr(time, "tzset"):
        time.tzset()
    builder = (SparkSession.builder.master("local[2]")
        .appName("P01 bounded native qualification")
        .config("spark.ui.enabled", "false")
        .config("spark.driver.bindAddress", "127.0.0.1")
        .config("spark.driver.host", "127.0.0.1")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog"))
    return configure_spark_with_delta_pip(builder).getOrCreate()


def verify_delta_at_final_path(target: Path, contract: dict):
    """Read version 0 at the FINAL location, not only the former staging path.

    The driver compares actual Delta rows to the bounded deterministic JSON
    projections. This is intentionally single-host, not a scalable collect-based
    implementation. A read, count, decimal, or key mismatch blocks acceptance.
    """
    from .canonical import within
    target = target.resolve()
    if target.name != "target":
        raise IntegrityError("Native verification requires the final target path")
    expected = {"silver/" + name: "silver/" + name + ".json"
                for name in contract["entities"]}
    expected.update({"gold/" + name: "gold/" + name + ".json" for name in
                    ("dim_customer", "dim_product", "dim_site", "fact_order_fulfillment", "site_kpi")})
    spark = native_spark_session()
    tables = {}
    try:
        for logical_path, json_path in sorted(expected.items()):
            wanted = read_json(within(target, json_path))
            path = within(target, "delta/" + logical_path)
            frame = spark.read.format("delta").option("versionAsOf", 0).load(str(path))
            # Bound driver materialization even if the stored table is corrupt.
            actual = [normalize_native_row(row) for row in frame.limit(len(wanted) + 1).collect()]
            if sorted(actual, key=canonical) != sorted(wanted, key=canonical):
                raise IntegrityError("Final-path Delta data differ from their accepted projection: " + logical_path)
            tables[logical_path] = {"version": 0, "rows": len(actual),
                "logical_sha256": digest(sorted(actual, key=canonical))}
        return {"status": "EXECUTED_AND_RECONCILED_FINAL_PATH",
                "spark_version": spark.version, "tables": tables,
                "scope": "bounded single-host Delta reads; not provider or scale qualification"}
    finally:
        spark.stop()
