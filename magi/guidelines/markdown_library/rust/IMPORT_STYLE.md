# Import Style

### Import Organization (fixed sequence)
1. Standard library imports (`std::`)
2. External crate imports (alphabetical)
3. Internal crate imports (`crate::`, `super::`, `self::`)
4. Separate groups with single blank lines

### Compact Format (Default)
Keep imports on one line unless exceeding 220 characters:
```rust
use std::{collections::HashMap, env, fs, io::{self, BufRead, Write}, path::PathBuf, sync::Arc, time::{Duration, SystemTime, UNIX_EPOCH}};

use reqwest::{header::{HeaderMap, HeaderValue, AUTHORIZATION, CONTENT_TYPE}, Client, StatusCode};
use serde::{Deserialize, Serialize};
use tokio::sync::{mpsc, RwLock};

use crate::{config::Settings, error::AppError, utils::auth::AuthHandler};
```

### Multi-line Format (When Exceeding 220 Characters)
```rust
use very_long_module_name::{
    ExtremelyLongTypeName1,
    ExtremelyLongTypeName2,
    ExtremelyLongTypeName3,
    ExtremelyLongTypeName4,
    ExtremelyLongTypeName5,
};
```

### Import Rules
- Never use glob imports (`use module::*`) except in test modules and preludes
- Prefer importing types directly over qualifying at usage site
- Re-export public API items from `lib.rs` for clean external interface
- Use `self` for module-level imports: `use std::io::{self, Read}`

---
[Back to Overview](./OVERVIEW.md)
