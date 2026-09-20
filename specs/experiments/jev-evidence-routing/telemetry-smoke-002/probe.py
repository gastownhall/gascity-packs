import sys,os,json,subprocess,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'gascity-jev/scripts'))
from jev_claude_usage import Collector
out=Path(__file__).resolve().parent/'telemetry-smoke-002';out.mkdir()
collector=Collector(out/'usage.jsonl')
env=dict(os.environ)
for key in ('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL','CLAUDE_CODE_USE_BEDROCK','CLAUDE_CODE_USE_VERTEX','CLAUDE_CODE_USE_FOUNDRY','OTEL_EXPORTER_OTLP_HEADERS','OTEL_EXPORTER_OTLP_LOGS_HEADERS'):
 env.pop(key,None)
env.update(collector.env)
try:
 result=subprocess.run(['claude','-p','--tools','','--setting-sources','project,local','--no-session-persistence','--model','claude-sonnet-5','--effort','low','--output-format','json','Reply with exactly OK.'],env=env,capture_output=True,text=True,timeout=90)
 (out/'stdout.json').write_text(result.stdout);(out/'stderr.txt').write_text(result.stderr)
 print('CLI exit:',result.returncode,flush=True)
finally:
 summary=collector.close();(out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
