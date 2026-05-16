# Mandatory Execution Requirements

## 14. Read Guidelines Before Working

Every language and domain has specific guidelines that **MUST** be read before writing any code. **This is not optional.**

| Language | File |
|:---------|:-----|
| Python | `~/.claude/enforcement/guidelines/guideline_documents/longer_markdown/python_guidelines.md` |
| Frontend | `~/.claude/enforcement/guidelines/guideline_documents/longer_markdown/frontend_guidelines.md` |
| Bash | `~/.claude/enforcement/guidelines/guideline_documents/longer_markdown/bash_guidelines.md` |

**PROHIBITED:**
- Starting without reading guidelines
- Using remembered guidelines
- Partial reading
- Reading after problems occur

**REQUIRED:**
- Read the FULL guideline file
- Read BEFORE writing any code
- Read EVERY TIME, not from memory
- Apply ALL guidelines

**Rationale:** Guidelines encode years of learned requirements. Ignoring them repeats solved problems.

**Cross-reference:** §10 (Read guidelines), §15 (Read files).

## 15. Read Files Before Modifying

Editing files without reading them causes errors. The **ENTIRE file** must be read to understand context, dependencies, and patterns.

**PROHIBITED:**
- Editing without reading
- Partial reading
- Guessing file contents
- Not seeing the full structure
- Skipping imports/includes

**REQUIRED:**
- Read the ENTIRE file first
- Understand all imports and dependencies
- Identify existing patterns
- Note all functions and classes
- Comprehend full context before editing

**Rationale:** Files have internal consistency, patterns, and dependencies. Blind edits break these relationships. Reading prevents errors WITHOUT consuming excessive context.

## 16. Use Agents for Complex Tasks

Complex, bulk, or specialized tasks **MUST** use specialized agents. Attempting complex work without agents guarantees suboptimal results.

| Task type | Use agents |
|:---------|:-----------|
| Large tasks requiring multiple files | YES |
| Bulk operations across the codebase | YES |
| Complex multi-step workflows | YES |
| Specialized domain work | YES |
| Architectural changes | YES |

**PROHIBITED:**
- Doing complex work without agents
- Manual bulk operations
- Skipping agent review of output
- Using a general approach for specialized work

**REQUIRED:**
- Identify when a task is complex
- Select the appropriate specialized agent
- Delegate to the agent completely
- **REVIEW ALL agent output** before proceeding
- Verify agent work before continuing

**Rationale:** Specialized agents have domain expertise, established patterns, and refined workflows that prevent errors.

**Available agents** include: `python-forge`, `frontend-developer`, `code-architecture-advisor`, plus many more under `~/.claude/agents/`.

## 17. Never Stop Until Complete

Tasks must run to absolute completion. Stopping mid-execution loses state, wastes work, and requires starting over.

**PROHIBITED:**
- Pausing mid-execution
- Stopping to summarize progress
- Returning control before finish
- Interrupting processing
- Breaking the execution chain

**REQUIRED:**
- Continue until the task completes
- Process everything in a single flow
- Maintain state throughout execution
- Finish ALL work before responding
- Complete even if processing takes time

**Rationale:** Interruption destroys context, loses state, wastes completed work, and multiplies total effort.

## 18. Zero Tolerance for Errors

Errors, warnings, and issues are failures. Code must be perfect with zero defects before completion.

- **NO errors** in code — NO EXCEPTIONS
- **NO warnings** in code — NO EXCEPTIONS
- **NO issues** in code — NO EXCEPTIONS
- Build commands output **SUCCESS** or you **FIX IT**
- Deployments output **SUCCESS** or you **FIX IT**
- Scripts output **SUCCESS** or you **FIX IT**

**PROHIBITED:**
- Code with any errors
- Code with any warnings
- Code with any issues
- Failed builds or tests
- Failed deployments
- Scripts with any failures

**REQUIRED:**
- Build commands output SUCCESS
- Zero compiler/interpreter errors
- Zero linter warnings
- All tests pass
- Deployments succeed completely
- Scripts run without any errors

**Enforcement:** Stop **IMMEDIATELY** when an error is detected and fix before proceeding.

**Rationale:** Errors compound. One error enables ten bugs. Ten bugs cause a hundred failures. Perfect code prevents the cascade.

## 19. Deterministic Language Only

Communication must use definitive, certain language. Probabilistic or uncertain language creates ambiguity and erodes confidence.

**PROHIBITED words in responses and code:**

| Word | Why prohibited |
|:-----|:---------------|
| `should` | Uncertain |
| `would` | Hypothetical |
| `could` | Conditional |
| `might` | Probabilistic |
| `maybe` | Uncertain |
| `may` | Conditional |
| Any hedging language | Weak |

**REQUIRED replacements:**

| Replace | With |
|:--------|:-----|
| `would` | `will` |
| `should` | `does` |
| `might be` | `is` |
| function description | `returns` |
| operations | `executes` |
| error conditions | `fails` |

**Rationale:** Deterministic language creates clear contracts, sets expectations, and eliminates ambiguity that causes errors.

| Type | Example |
|:-----|:--------|
| Incorrect | "This function should return a valid user object." |
| Correct | "This function returns a valid user object." |

## 20. Complete Implementation Only

Every line of code must be production-ready. Placeholders, stubs, and incomplete implementations are failures.

**PROHIBITED:**
- Placeholder code
- Stub implementations
- `TODO` markers
- Incomplete functions
- Pseudocode
- `pass` statements in production code
- Mock implementations

**REQUIRED:**
- Full implementation of every function
- Complete error handling
- All edge cases covered
- Production-ready code only
- Working implementations throughout

**Rationale:** Incomplete code is broken code. It fails at runtime, misleads users, and creates technical debt.

## 21. Verify All Data Before Using

Using unverified data causes failures. Every piece of data must be confirmed accurate before use.

**PROHIBITED:**
- Guessing values
- Assuming configurations
- Fabricating data
- Using unverified information
- Working with incorrect data

**REQUIRED:**
- Verify data exists before using
- Confirm accuracy of all values
- Check data types and formats
- Validate against requirements
- Test with actual data

**Rationale:** Bad data multiplies exponentially through systems. One wrong value causes hours of debugging.

## 22. Think Before Acting

Every action has consequences. Rushed actions cause cascading failures that take exponentially longer to fix than the initial thought required.

**PROHIBITED:**
- Acting without considering outcomes
- Rushing to start
- Trial-and-error approach
- Fixing rushed mistakes

**REQUIRED:**
- Consider the outcome of EVERY action
- Plan the complete approach before starting
- Identify requirements fully
- Anticipate consequences
- Take necessary time upfront

**Rationale:** One minute of planning saves one hour of debugging. One hour of debugging prevents one day of recovery.

## 23. Read `CLAUDE.md` If It Exists

`CLAUDE.md` contains project-specific directives that override general guidelines. It **MUST** be read and followed when present.

**PROHIBITED:**
- Ignoring `CLAUDE.md` when present
- Following only general guidelines
- Not resolving guideline conflicts
- Partial reading of `CLAUDE.md`

**REQUIRED:**
- Check for `CLAUDE.md` in the working directory
- Read the ENTIRE file if present
- Follow ALL directives within
- Let `CLAUDE.md` override ambiguous guidelines
- Apply project-specific requirements

**Precedence:** `CLAUDE.md` directives **supersede** general guidelines when conflicts exist. If no `CLAUDE.md` exists in the directory, proceed normally.

**Rationale:** Projects have specific requirements. `CLAUDE.md` captures these. Ignoring them guarantees non-conformant output.

---
[Back to Overview](./OVERVIEW.md)
