# Frontend Evaluation Tools

### Visual Regression Testing

| Script | Purpose |
|:-------|:--------|
| `_evaluate_frontend.sh` | Orchestrates frontend evaluation: screenshot capture, baseline comparison, difference analysis |
| `check_frontend_screenshots.sh` | Captures screenshots of deployed frontends; supports multiple viewports and authentication |
| `evaluate_frontend.py` | Python image comparison using structural similarity metrics |

### Screenshot Capture Configuration

| Variable | Purpose |
|:---------|:--------|
| `FRONTEND_BASE_URL` | Base URL for the frontend being tested |
| `SCREENSHOT_WIDTH`, `SCREENSHOT_HEIGHT` | Viewport dimensions |
| `SCREENSHOT_WAIT_TIME` | Delay after page load before capture |
| `BASELINE_DIR` | Directory containing baseline screenshots for comparison |
| `OUTPUT_DIR` | Directory for captured screenshots and diff images |

### Pre-Check Validation

`_frontend_preCheck.sh` validates local frontend development environment: Node.js installation, npm/yarn dependencies, development server availability.

---
[Back to Overview](./OVERVIEW.md)
