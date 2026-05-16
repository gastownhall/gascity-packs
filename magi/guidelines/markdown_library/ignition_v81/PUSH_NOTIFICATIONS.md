# Push Notifications

Gateway-to-Client/Designer push notifications in 8.1.

```java
// Gateway: send
context.getGatewaySessionManager().sendNotification(
    ApplicationScope.ALL,           // DESIGNER, CLIENT, ALL
    "com.company.module",
    "device-status-changed",
    serializableMessage);

// Client/Designer: receive
GatewayConnectionManager.getInstance().addPushNotificationListener(new PushNotificationListener() {
    @Override
    public void receiveNotification(String moduleId, String messageType, Object payload) {
        if (!"com.company.module".equals(moduleId)) return;
        if (!"device-status-changed".equals(messageType)) return;
        // handle payload
    }
});
```

| Constraint | Detail |
|:-----------|:-------|
| Scope | `ApplicationScope.DESIGNER`, `ApplicationScope.CLIENT`, `ApplicationScope.ALL` |
| Listener filtering | Listener filters by module ID and message type itself |
| Serialization | Java serialization. Payload class must implement `Serializable` |

---
[Back to Overview](./OVERVIEW.md)
