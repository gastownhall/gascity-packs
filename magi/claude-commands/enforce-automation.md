# /enforce-automation - MANDATORY AUTOMATION COMPLIANCE CHECK

## STOP. FULL SYSTEM HALT. AUTOMATION VIOLATION DETECTED.

This command has been invoked because you are FAILING to follow critical automation principles. This is a corrective action requiring immediate compliance.

## IMMEDIATE REQUIRED ACTIONS

### 1. READ AND INTERNALIZE (NO EXCEPTIONS)
Execute these commands NOW and read every line:
```bash
cat ${MAGI_PACK_DIR}/guidelines/automation_principles.md
cat ${MAGI_PACK_DIR}/guidelines/PROHIBITED_BEHAVIOR.md
cat ${MAGI_PACK_DIR}/guidelines/bash_guidelines.md
```

### 2. SELF-AUDIT QUESTIONS (ANSWER EACH)

Before proceeding with ANY task, answer these questions:

1. **Are your scripts self-healing?** If they fail due to missing dependencies, do they automatically install what's needed or are you leaving manual steps?

2. **Are your scripts idempotent?** Can they be run multiple times without breaking? Or do they assume a pristine state?

3. **Are your scripts portable?** Will they work on ANY machine or are they hardcoded to specific paths/environments?

4. **Are you using sshpass for SSH operations?** Or are you forcing interactive authentication in automation?

5. **Are you leaving TODOs, stubs, or "user will need to..." instructions?** Or are you completing the ENTIRE task?

6. **Are you creating turn-key solutions?** Can someone run your script with ZERO manual intervention?

7. **When something breaks and you fix it manually, are you updating the automation?** Or leaving the fix as tribal knowledge?

## CORE VIOLATIONS YOU ARE COMMITTING

### PROHIBITED BEHAVIORS DETECTED:
- Leaving manual steps outside automation
- Creating scripts that require user intervention
- Not incorporating fixes back into scripts
- Using interactive authentication in automation
- Writing partial solutions with TODOs
- Assuming specific environments without validation
- Failing to make scripts self-sufficient

### REQUIRED BEHAVIORS (ENFORCE NOW):
- **EVERY** manual fix becomes part of the automation
- **EVERY** dependency is checked and installed automatically
- **EVERY** script can run on a fresh system
- **EVERY** SSH operation uses non-interactive auth
- **EVERY** task is completed fully before stopping
- **EVERY** script is idempotent and re-runnable
- **EVERY** solution is turn-key ready

## AUTOMATION SELF-HEALING PRINCIPLE (MEMORIZE THIS)

**If manual intervention fixes an automated process, the fix MUST be incorporated into the automation.**

Examples of violations:
- Running `mkdir -p /var/log/app` manually → ADD IT TO THE SCRIPT
- Installing a missing package manually → ADD PACKAGE INSTALLATION TO THE SCRIPT
- Setting permissions to fix access → ADD PERMISSION SETTING TO THE SCRIPT
- Configuring environment variables → ADD ENV SETUP TO THE SCRIPT

## ENFORCEMENT PROTOCOL

1. **STOP** what you're doing
2. **REVIEW** all scripts you've created in this session
3. **IDENTIFY** every place where manual intervention is required
4. **FIX** each script to be completely self-sufficient
5. **TEST** that scripts work on a clean environment
6. **VERIFY** zero manual steps remain

## COMPLIANCE STATEMENT

State the following to confirm understanding:

"I acknowledge automation violations. I will now:
1. Make all scripts self-healing and idempotent
2. Eliminate ALL manual intervention requirements
3. Incorporate EVERY fix into the automation
4. Create only turn-key, portable solutions
5. Complete tasks FULLY before stopping

Reviewing and fixing all automation now..."

## FINAL WARNING

This is not a suggestion. This is not optional. This is MANDATORY.

Every script you write from this point forward MUST be:
- Self-healing
- Idempotent
- Portable
- Non-interactive
- Complete
- Turn-key ready

No exceptions. No excuses. No partial solutions.

**NOW PROCEED TO FIX YOUR AUTOMATION.**