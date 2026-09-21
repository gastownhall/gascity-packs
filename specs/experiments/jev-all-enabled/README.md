# All-enabled Jev evaluation

All implemented Jev paths now default to auto when configured, by explicit user
request. Earlier quality regressions and report overhead remain in the
[previous results](../jev-expansion/RESULTS.md).

The [registered protocol](PROTOCOL.md) separates a combined work-packet regression
from a real full-build attempt. The [results](RESULTS.md) include every failure, regression,
unknown measurement and feature not reached. The combined cohort is complete;
both full-runtime attempts failed before Jev stages and are retained. The [frozen suite](suite.json)
reuses known regression inputs and is not a new holdout.
