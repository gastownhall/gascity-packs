import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('jev_claude_usage',ROOT/'scripts/jev_claude_usage.py')
usage=importlib.util.module_from_spec(spec)
spec.loader.exec_module(usage)


def event(request='req1',model='sonnet',**extra):
    return {'event.name':'api_request','request_id':request,'session.id':'session',
            'model':model,'input_tokens':2,'output_tokens':3,'cache_read_tokens':100,
            'cache_creation_tokens':4,**extra}


def test_duplicate_delivery_does_not_double_count_and_auxiliary_is_included():
    summary=usage.summarize([event(),event(),event('req2','haiku',input_tokens=7)])
    assert summary['request_count']==2
    assert summary['totals']['input_tokens']==9
    assert summary['totals']['total_tokens']==223
    assert set(summary['models'])=={'sonnet','haiku'}


def test_missing_counters_remain_unknown():
    row=event();del row['cache_read_tokens']
    summary=usage.summarize([row])
    assert summary['status']=='incomplete' and summary['totals'] is None


def test_filter_excludes_prompt_and_personal_attributes():
    attrs={**event(),'user.email':'private@example.invalid','prompt':'private prompt'}
    payload={'resourceLogs':[{'scopeLogs':[{'logRecords':[{'attributes':[
        {'key':k,'value':{'intValue':str(v)} if type(v) is int else {'stringValue':v}}
        for k,v in attrs.items()]}]}]}]}
    rows=usage.extract(payload)
    assert len(rows)==1
    assert 'prompt' not in rows[0] and 'user.email' not in rows[0]
