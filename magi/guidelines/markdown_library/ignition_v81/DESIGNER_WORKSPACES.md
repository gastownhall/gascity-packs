# Designer Workspaces

Custom resource workspaces and undo/redo integration.

### TabbedResourceWorkspace

```java
public class MyWorkspace extends TabbedResourceWorkspace {

    public MyWorkspace(DesignerContext context) {
        super(context, RESOURCE_DESCRIPTOR);
    }

    @Override
    public ResourceEditor<MyResource> newResourceEditor(ResourcePath path) {
        return new MyResourceEditor(context, path);
    }

    @Override
    protected void addNewResourceActions(ResourceFolderNode folder, JPopupMenu popupMenu) {
        popupMenu.add(new NewMyResourceAction(folder));
    }
}

// DesignerHook.startup
context.registerResourceWorkspace(new MyWorkspace(context));
```

### ResourceEditor

```java
public class MyResourceEditor extends ResourceEditor<MyResource> {
    @Override
    protected void init(MyResource resource) {
        // build UI from resource state
    }

    @Override
    protected MyResource getObjectForSave() {
        // extract typed object from current UI state
    }

    @Override
    protected void serializeResource(ProjectResourceBuilder builder, MyResource res) {
        builder.putAttribute("name", res.getName());
        builder.putData(res.getPayload());
    }

    @Override
    protected MyResource deserialize(ProjectResource resource) {
        // convert back to typed object
    }
}
```

### Undo / Redo

```java
public class RenameAction implements UndoAction {
    private final MyResource resource;
    private final String oldName;
    private final String newName;

    @Override public boolean execute() { resource.setName(newName); return true; }
    @Override public void undo()        { resource.setName(oldName); }
    @Override public String getDescription() { return "Rename resource"; }
}

UndoManager.getInstance().add(new RenameAction(resource, "old", "new"));
```

Actions registered within 700 ms with identical descriptions auto-coalesce ("undo typing one character at a time").

---
[Back to Overview](./OVERVIEW.md)
