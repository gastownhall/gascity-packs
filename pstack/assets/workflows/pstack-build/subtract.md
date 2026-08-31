# Assess subtraction before addition

List existing behavior, code paths, dependencies, and interfaces that can be removed or reused before adding new surface. Record the decision and rejected alternatives in `pstack.decision.v1`. If nothing can be removed safely, record `status: no_removal_opportunity` with a non-empty subtraction assessment and rationale. The gate fails when a new layer is proposed without a subtraction assessment.

This runtime asset is executed by the Gas City graph.
