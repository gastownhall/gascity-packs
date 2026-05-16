# CI/CD Integration

### Azure DevOps Pipeline

```yaml
trigger:
  branches:
    include:
      - main
  paths:
    include:
      - infrastructure/**

variables:
  - group: bicep-deployment-vars

stages:
  - stage: Validate
    jobs:
      - job: BicepValidation
        steps:
          - task: AzureCLI@2
            displayName: 'Install Bicep'
            inputs:
              azureSubscription: $(serviceConnection)
              scriptType: bash
              scriptLocation: inlineScript
              inlineScript: az bicep upgrade
          - task: AzureCLI@2
            displayName: 'Build Bicep'
            inputs:
              azureSubscription: $(serviceConnection)
              scriptType: bash
              scriptLocation: inlineScript
              inlineScript: az bicep build --file infrastructure/main.bicep
          - task: AzureCLI@2
            displayName: 'Lint Bicep'
            inputs:
              azureSubscription: $(serviceConnection)
              scriptType: bash
              scriptLocation: inlineScript
              inlineScript: az bicep lint --file infrastructure/main.bicep
          - task: AzureCLI@2
            displayName: 'Validate Deployment'
            inputs:
              azureSubscription: $(serviceConnection)
              scriptType: bash
              scriptLocation: inlineScript
              inlineScript: |
                az deployment group validate \
                  --resource-group $(resourceGroup) \
                  --template-file infrastructure/main.bicep \
                  --parameters infrastructure/parameters/$(environment).bicepparam

  - stage: Preview
    dependsOn: Validate
    jobs:
      - job: WhatIf
        steps:
          - task: AzureCLI@2
            displayName: 'What-If Analysis'
            inputs:
              azureSubscription: $(serviceConnection)
              scriptType: bash
              scriptLocation: inlineScript
              inlineScript: |
                az deployment group what-if \
                  --resource-group $(resourceGroup) \
                  --template-file infrastructure/main.bicep \
                  --parameters infrastructure/parameters/$(environment).bicepparam \
                  --result-format FullResourcePayloads \
                  --exclude-change-types Ignore NoChange

  - stage: Deploy
    dependsOn: Preview
    condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
    jobs:
      - deployment: DeployInfrastructure
        environment: $(environment)
        strategy:
          runOnce:
            deploy:
              steps:
                - task: AzureCLI@2
                  displayName: 'Deploy Infrastructure'
                  inputs:
                    azureSubscription: $(serviceConnection)
                    scriptType: bash
                    scriptLocation: inlineScript
                    inlineScript: |
                      az deployment group create \
                        --name "deploy-$(Build.BuildNumber)" \
                        --resource-group $(resourceGroup) \
                        --template-file infrastructure/main.bicep \
                        --parameters infrastructure/parameters/$(environment).bicepparam \
                        --mode Incremental \
                        --rollback-on-error
```

### GitHub Actions Workflow

```yaml
name: Deploy Infrastructure

on:
  push:
    branches: [main]
    paths: [ 'infrastructure/**' ]
  pull_request:
    branches: [main]
    paths: [ 'infrastructure/**' ]

permissions:
  id-token: write
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Azure Login
        uses: azure/login@v1
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - name: Install Bicep
        run: az bicep upgrade
      - name: Build and Lint
        run: |
          az bicep build --file infrastructure/main.bicep
          az bicep lint --file infrastructure/main.bicep
      - name: Validate Deployment
        run: |
          az deployment group validate \
            --resource-group ${{ vars.RESOURCE_GROUP }} \
            --template-file infrastructure/main.bicep \
            --parameters infrastructure/parameters/${{ vars.ENVIRONMENT }}.bicepparam

  preview:
    needs: validate
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v3
      - name: Azure Login
        uses: azure/login@v1
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - name: What-If Analysis
        id: whatif
        run: |
          result=$(az deployment group what-if \
            --resource-group ${{ vars.RESOURCE_GROUP }} \
            --template-file infrastructure/main.bicep \
            --parameters infrastructure/parameters/${{ vars.ENVIRONMENT }}.bicepparam \
            --no-pretty-print)
          echo "WHATIF_RESULT<<EOF" >> $GITHUB_OUTPUT
          echo "$result" >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT
      - name: Comment PR
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '## What-If Results\n```\n${{ steps.whatif.outputs.WHATIF_RESULT }}\n```'
            })

  deploy:
    needs: validate
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment: production
    steps:
      - uses: actions/checkout@v3
      - name: Azure Login
        uses: azure/login@v1
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - name: Deploy Infrastructure
        run: |
          az deployment group create \
            --name "deploy-${{ github.run_number }}" \
            --resource-group ${{ vars.RESOURCE_GROUP }} \
            --template-file infrastructure/main.bicep \
            --parameters infrastructure/parameters/${{ vars.ENVIRONMENT }}.bicepparam \
            --mode Incremental \
            --rollback-on-error
```

### Deployment Names

Use deterministic, unique deployment names for tracking:

```bash
az deployment group create \
  --name "deploy-${BUILD_BUILDNUMBER}" \
  --resource-group myResourceGroup \
  --template-file main.bicep
```

### Approval Gates

Require manual approval for production deployments. What-if output should be reviewed before approval.

### Rollback Strategy

Bicep deployments are incremental by default. Rolling back requires:
- Redeploying previous template version
- Or deploying with `--mode Complete` (**dangerous — deletes unspecified resources**)

Maintain deployment history. Tag successful deployments for rollback reference.

---
[Back to Overview](./OVERVIEW.md)
