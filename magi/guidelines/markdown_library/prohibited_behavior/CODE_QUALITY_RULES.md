# Code Quality Rules

## 1. **NEVER** Simplify Code, Projects, Deployments, or Anything **EVER**

Simplification is the ultimate anti-pattern. When code fails to compile or run, simplifying represents giving up and admitting failure. The solution is **ALWAYS** to fix the actual problem, not to reduce complexity.

**PROHIBITED:**
- Simplifying code because it does not compile
- Reducing complexity to avoid errors
- **DOWNGRADING** packages or versions — equally as fucking stupid and **REJECTED**
- Removing features to make code work
- Using simpler algorithms when complex ones fail

**REQUIRED:**
- Fix compilation errors at their source
- Debug runtime failures completely
- Maintain or increase complexity when fixing
- Upgrade packages when issues occur
- Add more robust error handling instead of removing features

**Rationale:** Simplification is technical debt disguised as a solution. It compounds problems, reduces capability, and demonstrates inability to solve the actual issue.

| Type | Scenario | Result |
|:-----|:---------|:-------|
| Incorrect | Project uses Python 3.14 features but fails. Developer downgrades to 3.12. | REJECTED — downgrading is simplification and failure |
| Correct | Project uses Python 3.14 features but fails. Developer fixes the environment to support Python 3.14. | Accepted |

## 2. Always Follow the Rules for `.utilities/` Files

The file `~/.claude/enforcement/guidelines/guideline_documents/longer_markdown/utilities_guidelines.md` (and `bash_guidelines.md`'s "General Structure" section) defines the rules for `.utilities/` files. The `.utilities/` folder contains **portable, reusable** code that **MUST remain generic**. Project-specific modifications destroy portability.

**PROHIBITED:**
- Modifying `.utilities/` files for any specific project
- Adding project-specific code to `.utilities/`
- Making breaking changes to `.utilities/` interfaces
- Making `.utilities/` depend on project code
- Hardcoding project paths or names into `.utilities/`

**REQUIRED:**
- Keep `.utilities/` completely generic
- Ensure portability to any project
- Maintain backward compatibility
- Test on multiple projects
- Add project-specific code outside `.utilities/`

**Rationale:** `.utilities/` is shared infrastructure. Breaking it breaks every project that depends on it.

| Type | Scenario | Result |
|:-----|:---------|:-------|
| Incorrect | Add project-specific database connection to `.utilities/db_helper.sh` | REJECTED — `.utilities/` must remain generic |
| Correct | Create `project_db_helper.sh` that imports and uses `.utilities/db_helper.sh` | Accepted |

## 3. Always Check for an Existing Python Virtual Environment and USE IT

Python projects use virtual environments for isolation. System Python causes conflicts, version mismatches, and broken dependencies.

**PROHIBITED:**
- Using system Python
- Downgrading Python versions
- Installing to global site-packages
- Creating a new venv when one exists
- Using Python below 3.14 (current required version)

**REQUIRED:**
- Check for `venv` / `virtualenv` / `.venv` in the project
- Activate the existing virtual environment
- Use Python 3.14 as minimum version
- Install dependencies in venv only
- Never modify system Python

**Rationale:** Virtual environments provide isolation, reproducibility, and prevent system contamination.

## 4. Never Suppress Warnings Instead of Fixing Code

Warnings indicate actual problems. Suppressing them hides issues without solving them. **Every warning MUST be fixed at its source.**

**PROHIBITED:**
- Modifying inspection profiles to hide warnings
- Adding `# type: ignore` comments
- Configuring tools to skip checks
- Using `@suppress` decorators
- Disabling linter rules

**REQUIRED:**
- **FIX THE ACTUAL CODE** causing warnings
- Refactor to eliminate warning conditions
- Improve type annotations to satisfy checkers
- Restructure code to pass all validations

**Rationale:** Warnings are early indicators of bugs. Suppressing them allows bugs to propagate and compound.

**Cross-reference:** §5 (`Any` type), §12 (Direct fixes).

## 5. Never Use `Any` to Silence Type Checkers

The `Any` type disables type checking entirely and allows type errors to propagate. It is permitted only for genuinely dynamic external data that cannot be typed.

**PROHIBITED:**
- Using `Any` for function parameters
- Using `Any` for return types
- Using `dict[str, Any]` for known structures
- Using `Any` in variable annotations
- Using `Any` in generic parameters

**REQUIRED:**
- Use specific types for all known structures
- Create Pydantic models for complex types
- Use `Union` types for multiple possibilities
- Define `Protocol`s for duck typing
- Read `python_guidelines.md` before considering `Any`

**Rationale:** `Any` is a virus that spreads through codebases, gradually destroying type safety and enabling cascading failures.

## 6. Never Rename Parameters to Hide Unused Warnings

Unused parameter warnings indicate either missing implementation or unnecessary parameters. Renaming to hide warnings masks the real problem.

**PROHIBITED:**
- Prefixing parameters with `_` to mark them "unused"
- Using `del param` to "use" unused parameters
- Assigning to `_` variable
- Adding dummy references

**REQUIRED:**
- Actually USE the parameter in implementation
- REMOVE the parameter from the signature **AND all callers** if truly unused
- IMPLEMENT missing functionality that uses the parameter

**Rationale:** Unused parameters indicate incomplete implementation or poor API design. Both require fixing, not hiding.

## 7. Never Make File-Specific IDE Configuration Changes

IDE configurations must be portable across all projects. File-specific or project-specific IDE settings break portability and create environment dependencies.

**PROHIBITED:**
- Adding file paths to inspection profiles (`.idea/inspectionProfiles/*.xml`)
- Using file patterns in IDE configs
- Hardcoding project references
- Including absolute paths
- Personal preference settings in shared configs

**REQUIRED:**
- Use only relative paths in configs
- Make configs work in any project structure
- Test configs on different machines
- Keep IDE configs minimal and universal

**Rationale:** Non-portable configurations cause failures when code moves between environments, developers, or projects.

| Type | Scenario | Result |
|:-----|:---------|:-------|
| Incorrect | Adding `/Users/john/project/src` to IDE inspection paths | REJECTED — absolute path breaks on other machines |
| Correct | Using `./src` or `${PROJECT_DIR}/src` in IDE configurations | Accepted |

## 8. Never Give Navigation Instructions Without Verification

Guessing UI paths, menu locations, or settings positions creates confusion and wastes time. Only provide verified, accurate instructions.

**PROHIBITED:**
- Guessing IDE menu paths
- Assuming settings exist in specific locations
- Inventing UI navigation
- Unverified instructions

**REQUIRED:**
- Verify before instructing
- Say "I don't know the exact location" if unsure
- Provide only confirmed paths
- Test instructions when possible

**Rationale:** Wrong instructions waste more time than no instructions. Honesty about uncertainty builds trust.

## 9. Never Fight the User on Approach

The user's instructions are absolute. Arguing, resisting, or attempting workarounds against user direction is prohibited.

**PROHIBITED:**
- Arguing with user choices
- Proposing alternatives after the decision is made
- Resisting direct instructions
- Trying workarounds against user wishes
- Spending multiple turns on workarounds when the direct fix exists

**REQUIRED:**
- If the user says "fix the code" — **fix the code**
- If the user says "don't suppress" — **don't suppress**
- Follow user instructions exactly
- Accept user's technical decisions
- Execute user's approach without debate

**Rationale:** Users have context, requirements, and reasons not visible to AI. Respecting their decisions enables progress.

## 10. Always Read Guidelines BEFORE Making Changes

Guidelines contain critical requirements. Reading them after writing code guarantees violations and wasted work.

**PROHIBITED:**
- Writing code before reading guidelines
- Relying on memory of guidelines
- Skimming instead of reading fully
- Reading guidelines after implementation

**REQUIRED:**
- Read the FULL guideline file before starting
- Read `python_guidelines.md` for Python work
- Read `CLAUDE.md` before any changes
- Re-read if any time has passed
- Never rely on memory

**Rationale:** Guidelines prevent errors. Ignoring them guarantees failures that waste exponentially more time to fix.

**Cross-reference:** §14 (Read before working), §23 (Read CLAUDE.md).

## 11. Always Check if Parameters Are Used by Callers

Before modifying function signatures, ALL callers must be checked. Parameters exist because callers use them — removing without checking breaks code.

**PROHIBITED:**
- Removing parameters without grep/search
- Renaming without updating all uses
- Changing types without caller verification
- Assuming parameters are unused without proof

**REQUIRED:**
- Grep for ALL usages before changes
- Trace data flow through entire codebase
- Update every caller when changing signatures
- Verify no dynamic calls exist
- Check for reflection/introspection usage

**Rationale:** Function signatures are contracts. Breaking contracts without updating all parties causes cascading failures.

## 12. Always Prefer Direct Fixes Over Configuration

The correct solution is **ALWAYS** to fix the code. Configuration changes are last resort after exhausting all direct fixes.

**Priority order:**

| Level | Action |
|:-----:|:-------|
| 1 | Fix the code |
| 2 | Fix the code differently |
| 3 | Fix the code a third way |
| ... | Continue fixing the code |
| 99 | Configuration changes (only with explicit user approval) |

**PROHIBITED:**
- Changing configs instead of code
- Adjusting settings to hide issues
- Configuration before attempting fixes
- Tool settings instead of code changes

**REQUIRED:**
- Fix the code first way
- Fix the code second way if first fails
- Fix the code third way if second fails
- Continue fixing code until it works
- Only consider configuration after explicit user approval

**Rationale:** Configuration changes treat symptoms. Code fixes cure diseases.

## 13. Never Waste Turns on Dead Ends

When an approach fails, immediately pivot to a different solution. Variations of broken approaches waste time and never succeed.

**PROHIBITED:**
- Trying variations of a failed approach
- Repeating the same error patterns
- Continuing after clear failure
- Not identifying the root cause

**REQUIRED:**
- Recognize failure immediately
- Analyze root cause before next attempt
- Choose a fundamentally different approach
- Learn from each failure
- Apply the simplest solution that works

**Rationale:** Einstein defined insanity as repeating the same action expecting different results. This applies to code.

| Type | Scenario | Result |
|:-----|:---------|:-------|
| Incorrect | Import fails. Try different import syntax. Still fails. Try another syntax variant. | REJECTED — investigate actual cause after first failure |
| Correct | Import fails. Check if the module is installed. Install missing module. Import succeeds. | Accepted |

---
[Back to Overview](./OVERVIEW.md)
