# File I/O and Subprocess

### Prefer `pathlib.Path` Methods
Use `Path.read_text()` and `Path.write_text()` for whole-file text operations:
```python
content = Path("config.json").read_text(encoding="utf-8")
Path("output.txt").write_text(rendered, encoding="utf-8")
```

### Always Specify Encoding
Always pass `encoding="utf-8"` for text file operations. Never rely on platform default encoding.

### JSON via Pathlib
```python
data = json.loads(Path("config.json").read_text(encoding="utf-8"))
```

### Subprocess Safety
`subprocess.run()` must use safe defaults:
- Always pass `check=True` to raise on non-zero exit.
- Always pass `capture_output=True` to capture stdout/stderr.
- Always pass `text=True` for string output.
- **Never use `shell=True`.**
- Pass the command as a list, not a string.

```python
completed = subprocess.run(["echo", "hello"], check=True, capture_output=True, text=True)
```

### Temporary Directory Pattern
Use `TemporaryDirectory` with pathlib for temp operations.

### Entry Point Pattern
Use `raise SystemExit(main())`, not `sys.exit(main())`:
```python
if __name__ == "__main__":
    raise SystemExit(main())
```

---
[Back to Overview](./OVERVIEW.md)
