"""Install and restore the real pack while preserving an existing conversation."""
import hashlib
import json
import os
from pathlib import Path
import secrets

from live_assertions import AcceptanceFailure


def tree_hash(root):
    digest = hashlib.sha256()
    for path in sorted(Path(root).rglob('*')):
        if any(part in {'node_modules', 'dist', '.git'} for part in path.relative_to(root).parts): continue
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode() + b'\0')
            digest.update(path.read_bytes())
    return digest.hexdigest()


def registration(runner):
    rows = runner.bb('plugin', 'list', '--json')['plugins']
    matches = [row for row in rows if row['id'] == 'gas-city']
    if len(matches) != 1 or matches[0]['status'] != 'running':
        raise AcceptanceFailure('Expected one running installed Gas City plugin')
    return matches[0]


def install_restore(runner):
    c = runner.conversations['native.personal']
    current = Path(runner.env['GC_BB_INSTALL_DIR']) / 'current'
    before = registration(runner)
    previous = current.resolve(strict=True)
    if previous != Path(before['rootDir']).resolve(strict=True) or not previous.is_relative_to(runner.root):
        raise AcceptanceFailure('Installed registration/pointer is outside the owned installation')
    source_before = tree_hash(previous)
    config = Path(runner.env['GC_BB_CONFIG'])
    config_before = config.read_bytes()
    evidence = runner.private / 'installation.upgrade_rollback.json'
    evidence.write_text(json.dumps({'previousSource': before['source'], 'previousTreeSha256': source_before,
        'configSha256': hashlib.sha256(config_before).hexdigest()}, indent=2))
    # The installer creates another version and retains the previous code and
    # BB settings. It must exercise the real BB plugin registration/build path.
    runner.command(runner.manifest['commands']['gc'], 'bb', 'install', '--yes', timeout=180)
    upgraded = registration(runner)
    next_path = current.resolve(strict=True)
    if next_path == previous or next_path != Path(upgraded['rootDir']).resolve(strict=True):
        raise AcceptanceFailure('Upgrade did not install/register a distinct version')
    if source_before != tree_hash(previous) or config.read_bytes() != config_before:
        raise AcceptanceFailure('Upgrade changed preserved version files or connection settings')
    runner.verify_artifacts()
    upgrade_result = runner.recall('installation.upgrade', c)
    # Restore the actual previous path source using BB's public installer. Keep
    # both versions and all state; no remove/uninstall operation is involved.
    runner.bb('plugin', 'install', before['source'], '--yes')
    restored = registration(runner)
    if restored['source'] != before['source'] or restored['enabled'] != before['enabled']:
        raise AcceptanceFailure('BB did not restore the previous registration')
    temporary = current.parent / ('.e2e-restore-' + secrets.token_hex(8))
    os.symlink(previous, temporary)
    if current.resolve(strict=True) != next_path:
        raise AcceptanceFailure('Installation pointer changed concurrently; leaving evidence intact')
    os.replace(temporary, current)
    if source_before != tree_hash(previous) or config.read_bytes() != config_before:
        raise AcceptanceFailure('Rollback changed previous source files or connection settings')
    runner.verify_artifacts()
    restored_result = runner.recall('installation.rollback', c)
    return {'upgraded_conversation': upgrade_result, 'restored_conversation': restored_result,
            'previous_source_preserved': True, 'connection_settings_preserved': True}


def case_functions(runner):
    return {'installation.upgrade_rollback': lambda: install_restore(runner)}
