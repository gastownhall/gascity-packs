# Async/Await Patterns

### Compact Async
```rust
let response = client.get(&url).send().await?.json::<Value>().await?;
let (r1, r2) = tokio::join!(fetch_data(), fetch_config());
let task = tokio::spawn(async move { process(data).await.unwrap_or_default() });
```

### Async Function Signatures
```rust
pub async fn fetch_user(&self, id: UserId) -> Result<User, ApiError> {
    let url = format!("{}/users/{}", self.base_url, id);
    self.client.get(&url).send().await?.json().await.map_err(Into::into)
}
```

### Concurrent Execution
```rust
let (users, posts, comments) = tokio::try_join!(fetch_users(), fetch_posts(), fetch_comments())?;
let results: Vec<_> = futures::future::join_all(ids.iter().map(|id| fetch_item(id))).await;
let results: Vec<_> = stream::iter(items).map(|item| async move { process(item).await }).buffer_unordered(10).collect().await;
```

### Timeout Patterns
```rust
let result = tokio::time::timeout(Duration::from_secs(30), long_operation()).await??;
let result = tokio::select! {
    res = operation() => res,
    _ = tokio::time::sleep(Duration::from_secs(30)) => Err(Error::Timeout),
};
```

### Cancellation Safety
```rust
tokio::select! {
    biased;
    _ = shutdown.recv() => { cleanup().await; return Ok(()); },
    result = process() => result,
}
```

---
[Back to Overview](./OVERVIEW.md)
