# Module Services

Module-to-module API exposure via `ModuleServicesManager`.

```java
// Common scope: marker interface
public interface MyService extends ModuleService {
    DeviceStatus getStatus(String deviceId);
}

// Provider's GatewayHook
@Override
public void setup(GatewayContext context) {
    context.getModuleServicesManager().registerService(MyService.class, new MyServiceImpl(context));
}

@Override
public void startup(LicenseState license) {
    context.getModuleServicesManager().notifyServiceReady(this);
}

@Override
public void shutdown() {
    context.getModuleServicesManager().notifyServiceShutdown(this);
    context.getModuleServicesManager().unregisterService(MyService.class);
}

// Consumer's GatewayHook (implements ModuleServiceConsumer)
@Override
public void setup(GatewayContext context) {
    context.getModuleServicesManager().subscribe(MyService.class, this);
}

@Override
public void serviceReady(Class<?> serviceClass) {
    if (serviceClass == MyService.class) {
        myService = context.getModuleServicesManager().getService(MyService.class);
    }
}

@Override
public void serviceShutdown(Class<?> serviceClass) {
    if (serviceClass == MyService.class) {
        myService = null;          // null out cached reference
    }
}
```

---
[Back to Overview](./OVERVIEW.md)
