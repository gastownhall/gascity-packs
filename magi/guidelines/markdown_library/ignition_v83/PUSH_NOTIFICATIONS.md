# Push Notifications

Gateway-to-Designer/Client push with explicit serialization.

### Sending

```java
context.getGatewaySessionManager().sendNotification(
    ApplicationScope.ALL,           // DESIGNER, CLIENT, ALL, GATEWAY
    "com.company.module",
    "device-status-changed",
    payload,
    serializer);
```

| Constraint | Detail |
|:-----------|:-------|
| Scope values | `ApplicationScope.DESIGNER`, `CLIENT`, `ALL`, `GATEWAY` |
| Serializer | Module-author-supplied serializer marshals payload to bytes. Protobuf-based pair typical; Gson acceptable for simple payloads |

### Receiving

```java
GatewayConnectionManager.getInstance().addPushNotificationListener(
    new FilteredPushNotification("com.company.module", "device-status-changed") {
        @Override
        protected void receive(byte[] bytes) {
            DeviceStatus status = STATUS_DESERIALIZER.fromBytes(bytes);
            updateUi(status);
        }

        @Override
        public boolean dispatchOnEDT() { return true; }
    },
    deserializer);
```

| Constraint | Detail |
|:-----------|:-------|
| `FilteredPushNotification` base class | Filters by module ID and message type automatically. **Manual filtering wastes CPU on every notification.** |
| EDT dispatch | Override `dispatchOnEDT()` returning `true` for listeners that update Swing UI; base class wraps in `EventQueue.invokeLater` |

### Performance

Each notification incurs per-session serialization and listener invocation overhead. For sub-second updates across 100+ sessions, prefer pull-based polling with cache TTL.

---
[Back to Overview](./OVERVIEW.md)
