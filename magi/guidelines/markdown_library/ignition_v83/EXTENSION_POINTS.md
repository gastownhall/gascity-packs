# Modern Extension Points

8.3 extension point pattern with composite resources and reference properties.

### Implementation Pattern

```java
public final class MyAlarmProfile implements AlarmNotificationProfile {

    public MyAlarmProfile(GatewayContext context,
                          DecodedResource<ExtensionPointConfig<AlarmNotificationProfileConfig, MySettings>> resource,
                          MySettings settings) {
        // wire from context + settings
    }

    @Override public void start()      { ... }
    @Override public void shutdown()   { ... }
    @Override public void send(NotificationRequest req) { ... }
}

public final class MyAlarmExtensionPoint extends AlarmNotificationProfileExtensionPoint<MySettings> {

    public MyAlarmExtensionPoint() {
        super(TYPE_ID, "MyModule.alarmProfile.name", "MyModule.alarmProfile.desc", MySettings.class);
    }

    @Override
    public Optional<MySettings> defaultSettings() {
        return Optional.of(MySettings.DEFAULT);
    }

    @Override
    public void validate(MySettings settings, ValidationErrors.Builder errors) {
        errors.requireNotEmpty(settings.endpointUrl(), "endpointUrl");
        errors.requireInRange(settings.maxRetries(), 0, 10, "maxRetries");
    }

    @Override
    public AlarmNotificationProfile createProfile(GatewayContext ctx,
                                                  DecodedResource<ExtensionPointConfig<AlarmNotificationProfileConfig, MySettings>> resource,
                                                  MySettings settings) {
        return new MyAlarmProfile(ctx, resource, settings);
    }
}

// GatewayHook
@Override
public List<? extends ExtensionPointType> getExtensionPoints() {
    return List.of(new MyAlarmExtensionPoint());
}
```

| Element | Detail |
|:--------|:-------|
| Settings record | `MySettings` record with type-specific config (e.g., `endpointUrl`, `maxRetries`, `SecretConfig apiKey`) |
| Extension point class | Subclass platform-provided `ExtensionPointType` (e.g., `AlarmNotificationProfileExtensionPoint<Settings>`); pass `TYPE_ID`, `nameKey`, `descKey`, `Settings.class` to `super()` |
| Defaults | Override `defaultSettings()` |
| Validation | Override `validate(Settings, ValidationErrors.Builder)` |

### Settings-Free Extension Points

Parameterize on `Void`: `extends ExtensionPointType<Void>`.

### Soft-Deprecation

Override `canCreate()` returning `false` — existing instances continue, new creation blocked.

### Frontend Components

```java
@Override
public Optional<WebUiComponent> getWebUiComponent(ComponentType type) {
    return Optional.of(WebUiComponent.of("mounted/my-alarm-form.js", "MyAlarmForm"));
}
```

React/JS components are built separately (webpack) and bundled into the Gateway-scope jar under `resources/mounted/`.

---
[Back to Overview](./OVERVIEW.md)
