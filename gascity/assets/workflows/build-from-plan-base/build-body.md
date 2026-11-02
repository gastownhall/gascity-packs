# Build completion scope

This native build-base scope completes when its required stages finish. A terminal
member failure aborts the scope. Child overrides must retain every required stage
in this scope.
