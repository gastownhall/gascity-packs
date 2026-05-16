# Synthetic Monitoring

Synthetic monitors execute scripted checks against running services from Datadog's network of locations, providing baseline availability and performance signals independent of real user traffic.

### API Tests

```yaml
test:
  type: api
  frequency: 5m
  endpoint: https://api.example.com/health
  assertions:
    - type: status-code
      value: 200
    - type: response-time
      operator: lt
      value: 1000
    - type: body-json
      path: status
      value: healthy
  locations: [us-east-1, eu-west-1, ap-southeast-1]
```

### Browser Tests

```yaml
test:
  type: browser
  frequency: 15m
  device: laptop_large
  steps:
    - action: navigate
      url: https://app.example.com
    - action: type
      selector: "#username"
      value: test@example.com
    - action: type
      selector: "#password"
      value: "{{SECRET.password}}"
    - action: click
      selector: "#login-button"
    - action: wait
      selector: ".dashboard"
    - action: assert
      selector: ".user-name"
      value: Test User
```

### Multi-Step API Tests

```yaml
test:
  type: multistep-api
  frequency: 10m
  steps:
    - name: authenticate
      request:
        method: POST
        url: https://api.example.com/auth/login
        body: '{"username":"test","password":"{{SECRET.password}}"}'
      extract:
        variable: token
        from: body
        path: token
    - name: create-resource
      request:
        method: POST
        url: https://api.example.com/orders
        headers:
          Authorization: Bearer {{token}}
        body: '{"product":"test","quantity":1}'
      assertions:
        - type: status-code
          value: 201
```

---
[Back to Overview](./OVERVIEW.md)
