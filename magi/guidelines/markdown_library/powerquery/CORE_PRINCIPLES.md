# Core Principles

These guidelines define strict, performant, and maintainable patterns for Power Query (M language) implementations across Power BI, Excel, and Dataflows, optimizing for:

- **Query Folding First**: Every transformation decision considers whether operations push to the source system; local computation is the fallback, not the default.
- **Lazy Evaluation Awareness**: M is lazily evaluated; understanding when and how expressions execute determines both correctness and performance.
- **Type Safety**: Explicit type declarations at every boundary; implicit typing creates runtime failures that surface only on data refresh.
- **Modular Query Design**: Queries are composable units; monolithic query chains become unmaintainable; reference queries and functions create reusable building blocks.
- **Source System Respect**: Data sources have capacity limits, rate limits, and concurrent connection constraints; query design must account for source system health.

### Primary Rule: Query Folding Is Performance

Power Query's ability to translate M expressions into native source queries (SQL, OData, API calls) is called **query folding**. Folded operations execute at the source with full optimization; unfolded operations pull raw data and process locally. **A single unfolded step can transform a 2-second query into a 20-minute data pull.** Before writing any transformation, ask: *"Will this fold?"* If the answer is no, evaluate whether the operation is necessary at that position in the query chain, or whether restructuring preserves folding.

Correct (filtering folds to source):

```powerquery
Table.SelectRows(Source, each [Status] = "Active")
```

Incorrect (custom function breaks folding):

```powerquery
Table.TransformColumns(Source, {{"Name", Text.Proper}})
```

### Secondary Rule: Explicit Over Implicit

M's type inference is convenient but dangerous at scale. Implicit types propagate through query chains, creating failures that manifest only when specific data patterns appear. **Column types declared explicitly at ingestion catch schema drift immediately.** Function signatures with explicit parameter and return types document intent and enable editor tooling. The verbosity cost of explicit typing is trivial compared to debugging production refresh failures.

### Language Fundamentals

Power Query uses M (informally "Mashup"), a functional, case-sensitive, lazily-evaluated language:

- **Expressions, not statements** — every construct returns a value; no side effects by design.
- **Immutable data** — tables, records, and lists are immutable; transformations produce new values.
- **Case sensitivity** — `Column1` and `column1` are different identifiers; source system case must match exactly.
- **Whitespace insignificance** — formatting is for humans; the engine ignores whitespace outside strings.
- **Let expressions** — primary structuring mechanism; each step binds a name to a value.

### Execution Context

| Context | Query Folding | Gateway Required | Scheduled Refresh | Custom Connectors |
|:--------|:--------------|:-----------------|:------------------|:------------------|
| Power BI Desktop | Full | No | N/A | Yes |
| Power BI Service | Full | For on-prem | Yes | Certified only |
| Excel Power Query | Full | No | Manual | Limited |
| Dataflows (Gen1) | Full | For on-prem | Yes | No |
| Dataflows (Gen2 / Fabric) | Full | Managed | Yes | Via pipelines |

Design queries for the most constrained target environment. A query that works in Desktop may fail in Service due to connector certification or gateway requirements.

---
[Back to Overview](./OVERVIEW.md)
