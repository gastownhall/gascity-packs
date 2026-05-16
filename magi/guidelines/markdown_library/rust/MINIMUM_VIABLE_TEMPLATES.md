# Minimum Viable Templates

### Library Crate
```rust
//! # My Library
//! Brief description of what this library does.
mod error;
mod types;
pub use error::Error;
pub use types::{Config, Result};

pub fn process(input: &str) -> Result<String> {
    let validated = validate(input)?;
    Ok(transform(validated))
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn test_process_valid_input() { assert!(process("valid").is_ok()); }
}
```

### Binary Crate
```rust
use anyhow::{Context, Result};
use clap::Parser;
use tracing::{error, info};
use tracing_subscriber::{fmt, prelude::*, EnvFilter};

#[derive(Parser)]
#[command(name = "app", about = "Application description")]
struct Args {
    #[arg(short, long, default_value = "config.toml")]
    config: String,
}

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::registry().with(fmt::layer()).with(EnvFilter::from_default_env()).init();
    let args = Args::parse();
    info!("Starting application");
    let config = load_config(&args.config).context("Failed to load configuration")?;
    if let Err(e) = run(config).await { error!(error = ?e, "Application error"); return Err(e); }
    Ok(())
}
async fn run(config: Config) -> Result<()> { todo!() }
fn load_config(path: &str) -> Result<Config> { todo!() }
struct Config;
```

---
[Back to Overview](./OVERVIEW.md)
