# Heredocs and Remote Execution

## Heredocs and Embedding

### When Heredocs Are Forbidden
- Reusable shell logic.
- Helper functions.
- Configuration templates.
- JSON/YAML documents.
- Any content that could be a discrete file.

### When Heredocs Are Permitted
- Dynamically generated content.
- Ephemeral, non-reusable content.
- Unavoidable inline remote execution.

### Quoting the Delimiter
Quote the delimiter to prevent variable expansion when literal content is intended.
```bash
# Literal — no expansion
cat << 'EOF'
This $variable is literal.
EOF

# Intentional expansion
cat << EOF
Hello, ${USER}.
EOF
```

## Remote Execution

Remote blocks follow the same discipline as local scripts.

### Authentication
- Use `sshpass` for non-interactive SSH in scripts.
- Never use interactive authentication in automation.

### Requirements
- Strict mode enabled on remote.
- Colors defined explicitly if used.
- Framed status output.
- Error handling present.

### Inline Remote Command
```bash
ssh "${host}" "set -Eeuo pipefail; command -v docker >/dev/null 2>&1 || exit 1; docker ps"
```

### File Transfer + Execute Pattern (Preferred)
Copy scripts rather than embedding logic:
```bash
scp "${SCRIPT_DIR}/remote_task.sh" "${host}:/tmp/"
ssh "${host}" "chmod +x /tmp/remote_task.sh && /tmp/remote_task.sh"
```

---
[Back to Overview](./OVERVIEW.md)
