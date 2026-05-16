# Networking: HTTP, WebSocket, SSE

### HTTP (gloo-net)

```rust
use gloo_net::http::{Request, RequestCredentials};

async fn fetch_data<T: for<'de> serde::Deserialize<'de>>(url: &str) -> Result<T, String> {
    Request::get(url)
        .credentials(RequestCredentials::Include) // For cookies
        .header("Accept", "application/json")
        .send()
        .await
        .map_err(|e| e.to_string())?
        .json::<T>()
        .await
        .map_err(|e| e.to_string())
}
```

### WebSocket

```rust
use gloo_net::websocket::{futures::WebSocket, Message};
use futures::{SinkExt, StreamExt};

async fn connect_ws(url: &str) -> Result<(), String> {
    let ws = WebSocket::open(url).map_err(|e| e.to_string())?;
    let (mut write, mut read) = ws.split();
    write.send(Message::Text("Hello".into())).await.map_err(|e| e.to_string())?;
    while let Some(msg) = read.next().await {
        match msg {
            Ok(Message::Text(text)) => log::info!("Received: {}", text),
            Ok(Message::Bytes(bytes)) => log::info!("Received {} bytes", bytes.len()),
            Err(e) => log::error!("WebSocket error: {:?}", e),
        }
    }
    Ok(())
}
```

### Server-Sent Events

```rust
use gloo_net::eventsource::{EventSource, EventSourceError};
use futures::StreamExt;

async fn listen_sse(url: &str) -> Result<(), String> {
    let mut es = EventSource::new(url).map_err(|e| e.to_string())?;
    let mut stream = es.subscribe("message").map_err(|e| e.to_string())?;
    while let Some(event) = stream.next().await {
        match event {
            Ok((event_type, msg)) => log::info!("Event {}: {}", event_type, msg.data()),
            Err(EventSourceError::ConnectionError) => {
                log::error!("Connection lost, reconnecting...");
                // Implement reconnection logic
            }
            Err(e) => log::error!("SSE error: {:?}", e),
        }
    }
    Ok(())
}
```

### Rules

- **For cookies/sessions, add `.credentials(RequestCredentials::Include)`** on requests and configure server CORS accordingly.
- Reconnect strategies belong in a small abstraction; **avoid sprinkling retry logic across components**.

---
[Back to Overview](./OVERVIEW.md)
