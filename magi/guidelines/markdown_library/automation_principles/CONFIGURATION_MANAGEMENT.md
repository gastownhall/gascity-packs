# Configuration Management

Configuration is external data that parameterizes automation behavior. Self-healing automation loads configuration from multiple sources with clear precedence and validates all values before use.

### Configuration Sources (Precedence Order)

1. **Command-line arguments** — Highest precedence; explicit operator intent
2. **Environment variables** — Process-level configuration; container-friendly
3. **Configuration files** — Persistent settings; version controllable
4. **Discovered defaults** — Environment-detected reasonable values
5. **Hardcoded defaults** — Last resort; documented baseline behavior

Higher precedence sources override lower. This allows defaults to be overridden at deployment time without modifying automation code.

### Environment Variable Conventions

- **Naming** — Uppercase with underscores, prefixed by application or domain identifier: `MYAPP_DATABASE_URL`, `MYAPP_LOG_LEVEL`.
- **Required variables** — Fail explicitly when missing. Never proceed with empty values for required configuration.
- **Optional variables** — Provide sensible defaults. Document what the default is and why.
- **Sensitive variables** — Never log sensitive values. Mask in diagnostic output. Clear from environment after reading when possible.

### Configuration File Patterns

- **Location discovery** — Check multiple standard locations in order: current directory, user home, system configuration directory. Document the search order.
- **Format selection** — Prefer structured formats (YAML, TOML, JSON) over custom formats. Custom formats require custom parsers that become maintenance burdens.
- **Validation** — Parse configuration files into validated structures. Type-check values. Range-check numeric values. Verify referenced files and endpoints exist.

### Configuration Validation

Every configuration value must be validated before use:

- **Type validation** — Strings are strings, numbers are numbers, booleans are booleans
- **Range validation** — Ports are 1-65535, timeouts are positive, percentages are 0-100
- **Format validation** — URLs are valid URLs, IPs are valid IPs, dates are parseable
- **Existence validation** — File paths point to existing files, hostnames resolve
- **Semantic validation** — Combinations make sense (start time before end time, min less than max)

```bash
validate_config() {
    local config_file="$1"
    eval "$(jq -r '@sh "
    DB_HOST=\(.database.host)
    DB_PORT=\(.database.port)
    DB_NAME=\(.database.name)
    API_TIMEOUT=\(.api.timeout)
    LOG_LEVEL=\(.logging.level)
    "' "${config_file}")"
    [[ -z "${DB_HOST}" ]] && die "Database host is required"
    [[ -z "${DB_NAME}" ]] && die "Database name is required"
    [[ "${DB_PORT}" =~ ^[0-9]+$ ]] || die "Database port must be numeric"
    (( DB_PORT >= 1 && DB_PORT <= 65535 )) || die "Database port out of range"
    [[ "${API_TIMEOUT}" =~ ^[0-9]+$ ]] || die "API timeout must be numeric"
    (( API_TIMEOUT > 0 )) || die "API timeout must be positive"
    case "${LOG_LEVEL}" in
        ERROR|WARN|INFO|DEBUG|TRACE) ;;
        *) die "Invalid log level: ${LOG_LEVEL}" ;;
    esac
    nc -z "${DB_HOST}" "${DB_PORT}" 2>/dev/null || die "Cannot connect to database"
}
```

### Configuration Templating

```bash
render_template() {
    local template="$1"
    local output="$2"
    envsubst < "${template}" > "${output}.tmp"
    if validate_config "${output}.tmp"; then
        mv "${output}.tmp" "${output}"
    else
        rm -f "${output}.tmp"
        return 1
    fi
}
```

### Configuration Change Detection

Long-running automation should detect configuration changes and adapt:

- Watch configuration files for modifications
- Periodically refresh configuration from remote sources
- Provide signal handlers for manual configuration reload triggers
- Validate new configuration before applying; reject invalid changes

---
[Back to Overview](./OVERVIEW.md)
