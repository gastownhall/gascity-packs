# Testing and Validation

### Compilation Validation

```bash
az bicep build --file main.bicep
```

### Linting

```bash
az bicep lint --file main.bicep
```

Configure rules in `bicepconfig.json`. **Fail CI pipelines on linter errors.**

### What-If Analysis

```bash
# Standard what-if
az deployment group what-if \
  --resource-group myResourceGroup \
  --template-file main.bicep \
  --parameters @parameters/prod.bicepparam

# Full resource payloads (verbose diff)
az deployment group what-if \
  --resource-group myResourceGroup \
  --template-file main.bicep \
  --parameters @parameters/prod.bicepparam \
  --result-format FullResourcePayloads

# Exclude noise
az deployment group what-if \
  --resource-group myResourceGroup \
  --template-file main.bicep \
  --parameters @parameters/prod.bicepparam \
  --exclude-change-types Ignore NoChange

# Subscription-scope what-if
az deployment sub what-if \
  --location eastus \
  --template-file subscription.bicep \
  --parameters @parameters/prod.bicepparam
```

Review what-if output for unexpected changes. Integrate into pull request workflows for change visibility.

### ARM-TTK Validation

Validate compiled ARM templates with ARM Template Test Toolkit:

```bash
az bicep build --file main.bicep --outfile main.json
Test-AzTemplate -TemplatePath main.json
```

### Unit Testing with PSRule

Use PSRule for Azure to validate against Azure Well-Architected Framework:

```bash
Assert-PSRule -Module PSRule.Rules.Azure -InputPath ./main.bicep -Outcome Fail, Error
```

### Integration Testing

Deploy to ephemeral environments and validate:
- Resources exist with expected configuration
- Connectivity works between components
- Application health checks pass
- Security controls are effective

Destroy ephemeral environments after testing to control costs.

---
[Back to Overview](./OVERVIEW.md)
