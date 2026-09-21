# Duplicate investigation order

No duplicate verdict is supplied. Investigate candidates before applying the existing triage policy.

## Source issue
CSV import rejects BOM
A valid UTF-8 CSV beginning with a byte-order mark fails header validation.

## Candidate 1: C3
UTF-8 BOM breaks header detection
Import treats the UTF-8 BOM as part of the first header and rejects a valid CSV.

## Candidate 2: C2
CSV empty file
An empty CSV file raises a different exception before parsing headers.

## Candidate 3: C1
CSV export quoting
Exports need to quote fields containing commas.
