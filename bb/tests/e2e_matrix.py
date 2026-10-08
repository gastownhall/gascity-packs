"""Required behavior is declared independently from implemented test functions."""

COMMON_CASES = (
    'installation.fresh', 'installation.upgrade_rollback',
    'native.personal', 'native.project_global', 'native.project_rig',
    'native.configured_agent', 'launcher.global', 'launcher.rig',
    'provider.switch', 'reasoning.immutable',
    'trust.fresh', 'workspace.underscores', 'workspace.mismatch',
    'approvals.approve', 'approvals.deny', 'approvals.repeated', 'approvals.interrupt',
    'lifecycle.busy_followup', 'lifecycle.interrupt',
    'lifecycle.release_resume', 'lifecycle.agent_resume',
    'lifecycle.bridge_idle_crash', 'lifecycle.bridge_busy_crash',
    'lifecycle.bb_host_restart', 'lifecycle.bb_server_restart',
    'lifecycle.gc_controller_restart', 'lifecycle.gc_binary_replacement',
    'fault.create_response', 'fault.submit_response', 'fault.stream_disconnect',
    'fault.bridge_uncertain_delivery',
    'error.provider', 'error.startup', 'error.timeout',
)


def required_cases(reasoning_levels, *, desktop=False):
    if not reasoning_levels or reasoning_levels[0] != 'none' or len(set(reasoning_levels)) != len(reasoning_levels):
        raise ValueError('The matrix requires a complete unique advertised reasoning ladder including Agent default')
    return [*COMMON_CASES, *('reasoning.' + level for level in reasoning_levels),
            *(['desktop.native'] if desktop else [])]
