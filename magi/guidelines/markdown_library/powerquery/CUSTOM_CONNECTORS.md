# Custom Connectors

### Architecture

A connector consists of:

- **Data Source Kind** — unique identifier and authentication configuration.
- **Publish** — UI metadata for Power BI Service.
- **Functions** — M functions exposed by the connector.
- **Authentication** — OAuth2, API Key, Windows, Anonymous handlers.

### Development Setup

- Visual Studio with Power Query SDK extension.
- Power BI Desktop with custom connector preview enabled.
- `.mez` file deployment to Custom Connectors folder.

### Connector Structure

```powerquery
[DataSource.Kind = "MyConnector", Publish = "MyConnector.Publish"]
shared MyConnector.Contents = (url as text) as table =>
    let
        Source = Web.Contents(url, [Headers = [Authorization = "Bearer " & Extension.CurrentCredential()[access_token]]]),
        Result = Json.Document(Source)
    in
        Table.FromRecords(Result[data]);

MyConnector = [
    Authentication = [
        OAuth = [
            StartLogin  = StartLogin,
            FinishLogin = FinishLogin,
            Refresh     = Refresh
        ]
    ],
    Label = "My Custom Connector"
];

MyConnector.Publish = [
    Category = "Other",
    ButtonText = {"My Connector", "Connect to My Service"}
];
```

### OAuth2 Implementation

```powerquery
StartLogin = (resourceUrl, state, display) =>
    let
        AuthorizeUrl = "https://auth.service.com/authorize?" &
            Uri.BuildQueryString([
                client_id     = client_id,
                redirect_uri  = redirect_uri,
                response_type = "code",
                state         = state
            ])
    in
        [LoginUri = AuthorizeUrl, CallbackUri = redirect_uri, WindowHeight = 720, WindowWidth = 1024];

FinishLogin = (context, callbackUri, state) =>
    let
        Parts = Uri.Parts(callbackUri)[Query],
        TokenResponse = Web.Contents("https://auth.service.com/token", [
            Content = Text.ToBinary(Uri.BuildQueryString([
                grant_type   = "authorization_code",
                code         = Parts[code],
                client_id    = client_id,
                redirect_uri = redirect_uri
            ]))
        ])
    in
        Json.Document(TokenResponse);
```

### Certification Requirements

For Power BI Service deployment, connectors must be certified:

- Security review by Microsoft.
- Documentation and support plan.
- Compliance with connector guidelines.
- No hardcoded credentials or secrets.

Non-certified connectors work only in Power BI Desktop.

---
[Back to Overview](./OVERVIEW.md)
