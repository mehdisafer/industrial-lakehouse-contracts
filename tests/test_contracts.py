import copy
import json
from decimal import Decimal
import pytest
from ilc.contracts import validate_contract,validate_profile,parse_rows,coerce,compatibility
from ilc.canonical import canonical,digest,utc,read_json,within
from ilc.errors import ContractError


def test_supplied_contract_and_profile(contract,profile):
    assert validate_contract(contract)==contract
    assert validate_profile(profile,contract)==profile

@pytest.mark.parametrize('fault',['private','executable_model','missing_entity','duplicate_field','nullable_key','large_decimal','bad_field_name','unknown_property','unsupported_schema','no_owner'])
def test_reject_unreviewed_contracts(contract,fault):
    if fault=='private':contract['classification']='CLIENT_PRIVATE'
    elif fault=='executable_model':contract['gold_model']='eval(source)'
    elif fault=='missing_entity':del contract['entities']['orders']
    elif fault=='duplicate_field':contract['entities']['products']['fields'].append(contract['entities']['products']['fields'][0])
    elif fault=='nullable_key':contract['entities']['orders']['fields'][0]['nullable']=True
    elif fault=='large_decimal':contract['entities']['order_lines']['fields'][4]['type']='decimal(40,2)'
    elif fault=='bad_field_name':contract['entities']['orders']['fields'][0]['name']='order_id;DROP'
    elif fault=='unknown_property':contract['sql']='SELECT 1'
    elif fault=='unsupported_schema':contract['schema_version']='other'
    elif fault=='no_owner':contract['owner_role']=''
    with pytest.raises(ContractError):validate_contract(contract)

@pytest.mark.parametrize('fault',['external','unsafe_table','unsafe_file','missing_source','budget','target'])
def test_reject_profile_drift(contract,profile,fault):
    if fault=='external':profile['egress']='internet'
    elif fault=='unsafe_table':profile['entity_sources']['orders']['location']='orders;DROP TABLE'
    elif fault=='unsafe_file':profile['entity_sources']['products']['location']='../products.csv'
    elif fault=='missing_source':del profile['entity_sources']['orders']
    elif fault=='budget':profile['max_total_rows']=False
    elif fault=='target':profile['target']='delta_spark'
    with pytest.raises(ContractError):validate_profile(profile,contract)

@pytest.mark.parametrize('value', [True,1.5,'1e2','NaN','Infinity','-0.01','1.001','10000000000000000.00'])
def test_decimal_invalid_values(value):
    with pytest.raises((ValueError,ArithmeticError)):
        coerce(value,{'type':'decimal(18,2)','nullable':False,'min':0})

@pytest.mark.parametrize('value,expected',[('0','0.00'),('123.4','123.40'),('123.450','123.45'),('9999999999999999.99','9999999999999999.99')])
def test_exact_decimal(value,expected):
    assert coerce(value,{'type':'decimal(18,2)','nullable':False,'min':0})==expected

@pytest.mark.parametrize('value',[True,'1.0','1e2',1.5,2**64,'01'])
def test_invalid_integer(value):
    with pytest.raises(ValueError):coerce(value,{'type':'integer','nullable':False})

@pytest.mark.parametrize('value',['2026-11-12','2026-11-12T10:00:00','2026-11-12T11:00:00+01:00','2026-19-12T10:00:00Z'])
def test_utc_mandatory(value):
    with pytest.raises(ValueError):utc(value)

def test_utc_canonicalization():
    assert utc('2026-11-12T10:00:00Z')==utc('2026-11-12T10:00:00.000000+00:00')

def test_duplicate_json_keys_rejected(tmp_path):
    p=tmp_path/'x.json';p.write_text('{"owner":1,"owner":2}')
    with pytest.raises(ContractError):read_json(p)

def test_duplicate_row_quarantines_both_members(contract):
    entity=contract['entities']['products']
    row={'product_id':'P1','product_label':'Part','category':'x','updated_at':'2026-11-12T10:00:00Z'}
    good,bad=parse_rows([row,dict(row)],entity)
    assert good==[] and len(bad)==2
    assert {r['reasons'][0] for r in bad}=={'duplicate_primary_key'}

def test_schema_fields_are_not_silently_ignored(contract):
    row={'product_id':'P1','product_label':'Part','category':'x','updated_at':'2026-11-12T10:00:00Z','unknown':'x'}
    good,bad=parse_rows([row],contract['entities']['products'])
    assert not good and bad[0]['reasons']==['schema_fields']

def test_contract_compatibility_reports_breaking_type(contract):
    after=copy.deepcopy(contract);after['version']='1.0.0'
    after['entities']['order_lines']['fields'][1]['type']='string'
    after['entities']['order_lines']['fields'][1].pop('min')
    result=compatibility(contract,after)
    assert not result['compatible']

def test_canonical_hash_order_independent():
    assert digest({'b':2,'a':1})==digest({'a':1,'b':2})

@pytest.mark.parametrize('value', ['../outside','/outside','x\\..\\outside'])
def test_paths_cannot_escape(tmp_path,value):
    with pytest.raises(ContractError):within(tmp_path,value)
