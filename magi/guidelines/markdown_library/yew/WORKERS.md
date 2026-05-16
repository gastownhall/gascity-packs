# Web Workers and Agents

Background processing with Yew Agents (reactor pattern).

```rust
use yew_agent::prelude::*;
use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize)]
pub struct WorkerInput {
    pub data: Vec<u8>,
}

#[derive(Serialize, Deserialize)]
pub struct WorkerOutput {
    pub result: String,
}

#[reactor]
pub async fn ProcessorAgent(scope: ReactorScope<WorkerInput, WorkerOutput>) {
    while let Some(input) = scope.next().await {
        // Heavy processing
        let result = process_data(&input.data);
        scope.send(WorkerOutput { result }).await;
    }
}

// Usage in component
let worker = use_reactor::<ProcessorAgent>();
worker.send(WorkerInput { data: vec![] });
```

---
[Back to Overview](./OVERVIEW.md)
