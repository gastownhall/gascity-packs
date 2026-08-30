Use the built-in Gas City implementation stage contract.

Implement the approved decomposition with the inherited artifact root, context
path, drain policy, implementation target, iteration limit, push flag, and open
PR flag. Store the implementation summary path and outcome on the workflow root
bead.

Close this step only after implementation reports a clean result or an explicit
failure artifact.

The assigned implementation worker executes one implementation convoy through
the Gas City graph. Use `{{implementation_target}}`, record the implementation
summary, and close the claimed source anchor only after verification. Do not invoke provider-native subagents.
