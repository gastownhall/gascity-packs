# Color-Coded Output Standards

### Severity-to-Color Mapping

| Color | Use |
|:------|:----|
| `${RED}` | Errors and failures |
| `${YELLOW}` | Warnings and cautions |
| `${GREEN}` | Success and completion |
| `${CYAN}` | Informational messages |
| `${GRAY}` | Debug output |
| `${BLUE}` | Section headers |

### Output Pattern

```bash
echo -e "${GREEN}✓${NC} Operation completed successfully"
echo -e "${RED}✗${NC} Error: Operation failed"
echo -e "${YELLOW}⚠${NC} Warning: Potential issue detected"
echo -e "${CYAN}ℹ${NC} Info: Processing file..."
echo -e "${BLUE}═══${NC} Section: Test Results ${BLUE}═══${NC}"
```

### ANSI Stripping for Logs

Strip ANSI codes when writing to log files. Use `tee_to_log_strip_ansi` for dual output:

```bash
echo -e "${GREEN}Success${NC}" | tee_to_log_strip_ansi "${LOG_FILE}"
```

This produces colorized terminal output **and** plain text log entries simultaneously.

---
[Back to Overview](./OVERVIEW.md)
