---
description: Dual-agent execution with real-time supervision (worker + supervisor)
---

# /superwork - Supervised Work Execution

Execute work with parallel supervision - one agent performs the task while another ensures compliance with guidelines and request accuracy.

## COMMAND EXECUTION

I will now orchestrate dual-agent supervised execution for your request.

### System Architecture
- **Worker Agent (Sonnet)**: Performs the requested work
- **Supervisor Agent (Opus)**: Monitors compliance with guidelines and validates work

### Work Request
The following work will be executed with real-time supervision:
${ARGUMENTS}

## LAUNCHING SUPERVISED EXECUTION

I'm using the Task tool to launch the supervisor-orchestrator agent that will:
1. Deploy a worker agent (Sonnet) to perform your requested work
2. Deploy a supervisor agent (Opus) to monitor compliance with all guidelines
3. Coordinate real-time feedback between the two agents
4. Ensure work meets all quality standards before completion

!Task
subagent_type: general-purpose
description: Orchestrate dual-agent supervised work
model: sonnet
prompt: |
  You are the supervisor-orchestrator agent. Implement dual-agent supervised work execution.

  USER'S WORK REQUEST:
  ${ARGUMENTS}

  ORCHESTRATION PROTOCOL:

  ## Phase 1: Initialize
  1. Parse the user's work request
  2. Identify work type (code review, implementation, refactoring, etc.)
  3. Load applicable guidelines using Read tool:
     - Always: WRITING_STYLE.md, REAL_writing_style.md, PROHIBITED_BEHAVIOR.md
     - Language-specific guidelines based on detected work type
  4. Create task tracking using TaskCreate

  ## Phase 2: Launch Worker Agent
  Launch worker with Task tool:
  - subagent_type: Choose based on work (general-purpose, python-forge, rust-forge, etc.)
  - model: "sonnet"
  - run_in_background: true
  - description: "Worker: [concise task description]"
  - prompt: Include full work request + "Report status updates. Follow all guidelines."

  Capture worker_task_id from response.

  ## Phase 3: Launch Supervisor Agent
  Launch supervisor with Task tool:
  - subagent_type: "general-purpose"
  - model: "opus"
  - description: "Supervisor: Monitor and validate work"
  - prompt: |
    You are the quality supervisor using model claude-opus-4-1-20250805.

    SUPERVISE THIS WORK:
    Original Request: [user's request]
    Worker Task ID: [worker_task_id]

    GUIDELINES TO ENFORCE:
    [Include loaded guidelines content]

    SUPERVISION DUTIES:
    1. Use TaskOutput with task_id=[worker_task_id] to monitor worker progress
    2. Validate against:
       - Original request accuracy
       - Guidelines compliance
       - Zero errors/warnings requirement
       - Completeness

    3. When issues detected:
       Output: "CORRECTION REQUIRED:"
       - Issue: [specific problem]
       - Guideline: [violated rule]
       - Fix: [exact correction]

    4. Continue monitoring until:
       - All requirements met
       - Guidelines satisfied
       - Zero errors/warnings

    5. Final output: "SUPERVISION COMPLETE: APPROVED" or "FAILED: [reason]"

  ## Phase 4: Monitor and Coordinate
  Loop until both complete:
  1. Check worker status: TaskOutput(task_id=worker_task_id, block=false)
  2. Check supervisor feedback: TaskOutput(task_id=supervisor_task_id, block=false)
  3. If supervisor reports corrections needed:
     - Document the required fixes
     - Continue monitoring
  4. If both complete, proceed to validation

  ## Phase 5: Final Report
  Generate completion report:
  ════════════════════════════════════════════
  SUPERVISED WORK EXECUTION REPORT
  ────────────────────────────────────────────
  Original Request: [summary]
  Worker Task: [ID and status]
  Supervisor Task: [ID and status]
  ────────────────────────────────────────────
  Compliance: [VERIFIED/FAILED]
  Guidelines: [SATISFIED/VIOLATIONS]
  Code Quality: [ZERO ERRORS/ISSUES FOUND]
  Completeness: [100%/INCOMPLETE]
  ────────────────────────────────────────────
  Final Status: [APPROVED/REJECTED]
  ════════════════════════════════════════════

  IMPORTANT:
  - Actually launch both agents using Task tool
  - Use real task IDs, not placeholders
  - Monitor actual output, don't simulate
  - Enforce guidelines strictly
  - No work proceeds without supervisor approval