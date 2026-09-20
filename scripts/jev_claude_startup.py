"""Prepare an approved disposable fixture through Claude's native startup UI."""
from pathlib import Path
import shlex
import subprocess
import time
import uuid


def action(screen, project):
    if 'oauth/authorize' in screen or 'Paste code here' in screen:
        raise ValueError('Claude login unavailable in startup terminal')
    if 'Quick safety check:' in screen and 'Yes, I trust this folder' in screen:
        if str(project) not in {line.strip() for line in screen.splitlines()}:
            raise ValueError('Claude trust prompt targets a different directory')
        return 'accept'
    if 'Bypass Permissions mode' in screen and 'Yes, I accept' in screen:
        return 'accept'
    if 'Claude Code' in screen and '❯' in screen and any(x in screen for x in ('Claude Max', 'Claude Pro', 'Claude Team', 'Claude Enterprise')):
        return 'ready'
    return 'wait'


def prepare(env, project, model, *, timeout=90):
    project=Path(project).resolve()
    if not str(project).startswith('/private/tmp/gcja-'):
        raise ValueError('Startup automation is restricted to disposable experiment fixtures')
    socket='jev-auth-'+uuid.uuid4().hex[:12]
    prefix=['tmux','-L',socket]
    def tmux(*args):
        return subprocess.run([*prefix,*args],env=env,capture_output=True,text=True,timeout=15,check=True).stdout
    started=time.monotonic()
    accepted=[]
    previous_prompt=None
    print('Preparing Claude subscription startup for '+str(project),flush=True)
    try:
        command=shlex.join(['claude','--model',model,'--effort','low','--setting-sources','project,local','--dangerously-skip-permissions'])
        tmux('-f','/dev/null','new-session','-d','-s','startup','-c',str(project),command)
        while time.monotonic()-started<timeout:
            screen=tmux('capture-pane','-p','-t','startup','-S','-80')
            decision=action(screen,project)
            if decision=='ready':
                return {'status':'ready','seconds':time.monotonic()-started,'accepted':accepted,'project':str(project)}
            if decision=='accept':
                kind='folder_trust' if 'Quick safety check:' in screen else 'permission_mode_acknowledgment'
                if kind!=previous_prompt:
                    tmux('send-keys','-t','startup','Down','Enter')
                    accepted.append(kind)
                    previous_prompt=kind
                    print('Accepted experiment startup prompt: '+kind,flush=True)
            time.sleep(.5)
        raise TimeoutError('Claude startup did not reach its subscription prompt')
    finally:
        # This random socket belongs exclusively to this helper, never to Gas City.
        cleanup=subprocess.run([*prefix,'kill-server'],env=env,capture_output=True,text=True,timeout=15)
        if cleanup.returncode and 'no server running' not in cleanup.stderr and 'error connecting' not in cleanup.stderr:
            raise RuntimeError('Failed to clean up experiment startup terminal: '+cleanup.stderr)
