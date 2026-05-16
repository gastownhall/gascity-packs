# LM Studio REST API

LM Studio offers a powerful REST API with first-class support for local inference and model management. In addition to the native API, LM Studio provides OpenAI-compatible endpoints and Anthropic-compatible endpoints.

## What's New

Previously, there was a v0 REST API. With LM Studio 0.4.0, the native v1 REST API at `/api/v1/*` endpoints has been officially released and is the recommended API.

The v1 REST API includes enhanced features such as:

- MCP via API
- Stateful chats
- Authentication configuration with API tokens
- Model download, load, and unload endpoints

## Supported Endpoints (v1)

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/v1/chat` | POST | Chat |
| `/api/v1/models` | GET | List Models |
| `/api/v1/models/load` | POST | Load |
| `/api/v1/models/unload` | POST | Unload |
| `/api/v1/models/download` | POST | Download |
| `/api/v1/models/download/status` | GET | Download Status |

## Inference Endpoint Comparison

The table below compares the features of LM Studio's `/api/v1/chat` endpoint with the OpenAI-compatible and Anthropic-compatible inference endpoints.

| Feature | `/api/v1/chat` | `/v1/responses` | `/v1/chat/completions` | `/v1/messages` |
| --- | :---: | :---: | :---: | :---: |
| Streaming | ✅ | ✅ | ✅ | ✅ |
| Stateful chat | ✅ | ✅ | ❌ | ❌ |
| Remote MCPs | ✅ | ✅ | ❌ | ❌ |
| MCPs you have in LM Studio | ✅ | ✅ | ❌ | ❌ |
| Custom tools | ❌ | ✅ | ✅ | ✅ |
| Include assistant messages in the request | ❌ | ✅ | ✅ | ✅ |
| Model load streaming events | ✅ | ❌ | ❌ | ❌ |
| Prompt processing streaming events | ✅ | ❌ | ❌ | ❌ |
| Specify context length in the request | ✅ | ❌ | ❌ | ❌ |

---

## Start the Server

Install and launch LM Studio. Then ensure the server is running through the toggle at the top left of the Developer page, or through `lms` in the terminal:

```bash
lms server start
```

By default, the server is available at `http://localhost:1234`.

If you don't have a model downloaded yet, you can download one:

```bash
lms get ibm/granite-4-micro
```

## API Authentication

By default, the LM Studio API server does **not** require authentication. You can configure the server to require authentication by API token in the server settings for added security.

To authenticate API requests, generate an API token from the Developer page in LM Studio, and include it in the `Authorization` header of your requests as `Authorization: Bearer $LM_API_TOKEN`.

## Chat with a Model

Use the chat endpoint to send a message to a model. By default, the model will be automatically loaded if it is not already.

The `/api/v1/chat` endpoint is stateful, which means you do not need to pass the full history in every request.

### curl

```bash
curl http://localhost:1234/api/v1/chat \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro",
    "input": "Write a short haiku about sunrise."
  }'
```

### Python

```python
import os
import requests
import json

response = requests.post(
  "http://localhost:1234/api/v1/chat",
  headers={
    "Authorization": f"Bearer {os.environ['LM_API_TOKEN']}",
    "Content-Type": "application/json"
  },
  json={
    "model": "ibm/granite-4-micro",
    "input": "Write a short haiku about sunrise."
  }
)
print(json.dumps(response.json(), indent=2))
```

### TypeScript

```typescript
const response = await fetch("http://localhost:1234/api/v1/chat", {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${process.env.LM_API_TOKEN}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    model: "ibm/granite-4-micro",
    input: "Write a short haiku about sunrise."
  })
});
const data = await response.json();
console.log(data);
```

## Use MCP Servers via API

Enable the model to interact with ephemeral Model Context Protocol (MCP) servers in `/api/v1/chat` by specifying servers in the `integrations` field.

### Ephemeral MCP server (curl)

```bash
curl http://localhost:1234/api/v1/chat \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro",
    "input": "What is the top trending model on hugging face?",
    "integrations": [
      {
        "type": "ephemeral_mcp",
        "server_label": "huggingface",
        "server_url": "https://huggingface.co/mcp",
        "allowed_tools": ["model_search"]
      }
    ],
    "context_length": 8000
  }'
```

### Python

```python
import os
import requests
import json

response = requests.post(
  "http://localhost:1234/api/v1/chat",
  headers={
    "Authorization": f"Bearer {os.environ['LM_API_TOKEN']}",
    "Content-Type": "application/json"
  },
  json={
    "model": "ibm/granite-4-micro",
    "input": "What is the top trending model on hugging face?",
    "integrations": [
      {
        "type": "ephemeral_mcp",
        "server_label": "huggingface",
        "server_url": "https://huggingface.co/mcp",
        "allowed_tools": ["model_search"]
      }
    ],
    "context_length": 8000
  }
)
print(json.dumps(response.json(), indent=2))
```

### Using locally configured MCP plugins

You can also use locally configured MCP plugins (from your `mcp.json`) via the `integrations` field. Using locally run MCP plugins requires authentication via an API token passed through the `Authorization` header.

```bash
curl http://localhost:1234/api/v1/chat \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro",
    "input": "Open lmstudio.ai",
    "integrations": [
      {
        "type": "plugin",
        "id": "mcp/playwright",
        "allowed_tools": ["browser_navigate"]
      }
    ],
    "context_length": 8000
  }'
```

## Download a Model

Use the download endpoint to download models by identifier from the LM Studio model catalog, or by Hugging Face model URL.

```bash
curl http://localhost:1234/api/v1/models/download \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro"
  }'
```

The response will return a `job_id` that you can use to track download progress:

```bash
curl -H "Authorization: Bearer $LM_API_TOKEN" \
  http://localhost:1234/api/v1/models/download/status/{job_id}
```

---

## Stateful Chats

The `/api/v1/chat` endpoint is stateful by default. This means you don't need to pass the full conversation history in every request — LM Studio automatically stores and manages the context for you.

### How It Works

When you send a chat request, LM Studio stores the conversation in a chat thread and returns a `response_id` in the response. Use this `response_id` in subsequent requests to continue the conversation.

```bash
# Start a new conversation
curl http://localhost:1234/api/v1/chat \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro",
    "input": "My favorite color is blue."
  }'
```

The response includes a `response_id`:

> Every response includes a unique `response_id` that you can use to reference that specific point in the conversation for future requests. This allows you to branch conversations.

```json
{
  "model_instance_id": "ibm/granite-4-micro",
  "output": [
    {
      "type": "message",
      "content": "That's great! Blue is a beautiful color..."
    }
  ],
  "response_id": "resp_abc123xyz..."
}
```

### Continue a Conversation

Pass the `previous_response_id` in your next request to continue the conversation. The model will remember the previous context.

```bash
curl http://localhost:1234/api/v1/chat \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro",
    "input": "What color did I just mention?",
    "previous_response_id": "resp_abc123xyz..."
  }'
```

The model can reference the previous message without you needing to resend it, and will return a new `response_id` for further continuation.

### Disable Stateful Storage

If you don't want to store the conversation, set `store` to `false`. The response will not include a `response_id`.

```bash
curl http://localhost:1234/api/v1/chat \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro",
    "input": "Tell me a joke.",
    "store": false
  }'
```

This is useful for one-off requests where you don't need to maintain context.

---

## Streaming Events

Streaming events let you render chat responses incrementally over Server-Sent Events (SSE). When you call `POST /api/v1/chat` with `stream: true`, the server emits a series of named events that you can consume. These events arrive in order and may include multiple deltas (for reasoning and message content), tool call boundaries and payloads, and any errors encountered. The stream always begins with `chat.start` and concludes with `chat.end`, which contains the aggregated result equivalent to a non-streaming response.

List of event types that can be sent in an `/api/v1/chat` response stream:

- `chat.start`
- `model_load.start`
- `model_load.progress`
- `model_load.end`
- `prompt_processing.start`
- `prompt_processing.progress`
- `prompt_processing.end`
- `reasoning.start`
- `reasoning.delta`
- `reasoning.end`
- `tool_call.start`
- `tool_call.arguments`
- `tool_call.success`
- `tool_call.failure`
- `message.start`
- `message.delta`
- `message.end`
- `error`
- `chat.end`

Events are streamed in the following raw format:

```
event: <event type>
data: <JSON event data>
```

### `chat.start`

Emitted at the start of a chat response stream.

| Field | Type | Description |
| --- | --- | --- |
| `model_instance_id` | string | Unique identifier for the loaded model instance that will generate the response. |
| `type` | `"chat.start"` | The type of the event. Always `chat.start`. |

```json
{
  "type": "chat.start",
  "model_instance_id": "openai/gpt-oss-20b"
}
```

### `model_load.start`

Signals the start of a model being loaded to fulfill the chat request. Will not be emitted if the requested model is already loaded.

| Field | Type | Description |
| --- | --- | --- |
| `model_instance_id` | string | Unique identifier for the model instance being loaded. |
| `type` | `"model_load.start"` | The type of the event. Always `model_load.start`. |

```json
{
  "type": "model_load.start",
  "model_instance_id": "openai/gpt-oss-20b"
}
```

### `model_load.progress`

Progress of the model load.

| Field | Type | Description |
| --- | --- | --- |
| `model_instance_id` | string | Unique identifier for the model instance being loaded. |
| `progress` | number | Progress of the model load as a float between `0` and `1`. |
| `type` | `"model_load.progress"` | The type of the event. Always `model_load.progress`. |

```json
{
  "type": "model_load.progress",
  "model_instance_id": "openai/gpt-oss-20b",
  "progress": 0.65
}
```

### `model_load.end`

Signals a successfully completed model load.

| Field | Type | Description |
| --- | --- | --- |
| `model_instance_id` | string | Unique identifier for the model instance that was loaded. |
| `load_time_seconds` | number | Time taken to load the model in seconds. |
| `type` | `"model_load.end"` | The type of the event. Always `model_load.end`. |

```json
{
  "type": "model_load.end",
  "model_instance_id": "openai/gpt-oss-20b",
  "load_time_seconds": 12.34
}
```

### `prompt_processing.start`

Signals the start of the model processing a prompt.

```json
{
  "type": "prompt_processing.start"
}
```

### `prompt_processing.progress`

Progress of the model processing a prompt.

| Field | Type | Description |
| --- | --- | --- |
| `progress` | number | Progress of the prompt processing as a float between `0` and `1`. |
| `type` | `"prompt_processing.progress"` | The type of the event. |

```json
{
  "type": "prompt_processing.progress",
  "progress": 0.5
}
```

### `prompt_processing.end`

Signals the end of the model processing a prompt.

```json
{
  "type": "prompt_processing.end"
}
```

### `reasoning.start`

Signals the model is starting to stream reasoning content.

```json
{
  "type": "reasoning.start"
}
```

### `reasoning.delta`

A chunk of reasoning content. Multiple deltas may arrive.

| Field | Type | Description |
| --- | --- | --- |
| `content` | string | Reasoning text fragment. |
| `type` | `"reasoning.delta"` | The type of the event. |

```json
{
  "type": "reasoning.delta",
  "content": "Need to"
}
```

### `reasoning.end`

Signals the end of the reasoning stream.

```json
{
  "type": "reasoning.end"
}
```

### `tool_call.start`

Emitted when the model starts a tool call.

| Field | Type | Description |
| --- | --- | --- |
| `tool` | string | Name of the tool being called. |
| `provider_info` | object | Information about the tool provider. Discriminated union; see below. |
| `type` | `"tool_call.start"` | The type of the event. |

**Plugin provider info:**

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"plugin"` | Provider type. |
| `plugin_id` | string | Identifier of the plugin. |

**Ephemeral MCP provider info:**

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"ephemeral_mcp"` | Provider type. |
| `server_label` | string | Label of the MCP server. |

```json
{
  "type": "tool_call.start",
  "tool": "model_search",
  "provider_info": {
    "type": "ephemeral_mcp",
    "server_label": "huggingface"
  }
}
```

### `tool_call.arguments`

Arguments streamed for the current tool call.

| Field | Type | Description |
| --- | --- | --- |
| `tool` | string | Name of the tool being called. |
| `arguments` | object | Arguments passed to the tool. Keys/values depend on the tool definition. |
| `provider_info` | object | Information about the tool provider. |
| `type` | `"tool_call.arguments"` | The type of the event. |

```json
{
  "type": "tool_call.arguments",
  "tool": "model_search",
  "arguments": {
    "sort": "trendingScore",
    "limit": 1
  },
  "provider_info": {
    "type": "ephemeral_mcp",
    "server_label": "huggingface"
  }
}
```

### `tool_call.success`

Result of the tool call, along with the arguments used.

| Field | Type | Description |
| --- | --- | --- |
| `tool` | string | Name of the tool that was called. |
| `arguments` | object | Arguments that were passed to the tool. |
| `output` | string | Raw tool output string. |
| `provider_info` | object | Information about the tool provider. |
| `type` | `"tool_call.success"` | The type of the event. |

```json
{
  "type": "tool_call.success",
  "tool": "model_search",
  "arguments": {
    "sort": "trendingScore",
    "limit": 1
  },
  "output": "[{\"type\":\"text\",\"text\":\"Showing first 1 models...\"}]",
  "provider_info": {
    "type": "ephemeral_mcp",
    "server_label": "huggingface"
  }
}
```

### `tool_call.failure`

Indicates that the tool call failed.

| Field | Type | Description |
| --- | --- | --- |
| `reason` | string | Reason for the tool call failure. |
| `metadata` | object | Metadata about the invalid tool call. |
| `type` | `"tool_call.failure"` | The type of the event. |

**`metadata` fields:**

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"invalid_name"` \| `"invalid_arguments"` | Type of error that occurred. |
| `tool_name` | string | Name of the tool that was attempted to be called. |
| `arguments` | object (optional) | Arguments passed to the tool (only for `invalid_arguments` errors). |
| `provider_info` | object (optional) | Tool provider info (only for `invalid_arguments` errors). |

```json
{
  "type": "tool_call.failure",
  "reason": "Cannot find tool with name open_browser.",
  "metadata": {
    "type": "invalid_name",
    "tool_name": "open_browser"
  }
}
```

### `message.start`

Signals the model is about to stream a message.

```json
{
  "type": "message.start"
}
```

### `message.delta`

A chunk of message content. Multiple deltas may arrive.

| Field | Type | Description |
| --- | --- | --- |
| `content` | string | Message text fragment. |
| `type` | `"message.delta"` | The type of the event. |

```json
{
  "type": "message.delta",
  "content": "The current"
}
```

### `message.end`

Signals the end of the message stream.

```json
{
  "type": "message.end"
}
```

### `error`

An error occurred during streaming. The final payload will still be sent in `chat.end` with whatever was generated.

| Field | Type | Description |
| --- | --- | --- |
| `error.type` | enum | One of `invalid_request`, `unknown`, `mcp_connection_error`, `plugin_connection_error`, `not_implemented`, `model_not_found`, `job_not_found`, `internal_error`. |
| `error.message` | string | Human-readable error message. |
| `error.code` | string (optional) | More detailed error code (e.g., validation issue code). |
| `error.param` | string (optional) | Parameter associated with the error, if applicable. |
| `type` | `"error"` | The type of the event. |

```json
{
  "type": "error",
  "error": {
    "type": "invalid_request",
    "message": "\"model\" is required",
    "code": "missing_required_parameter",
    "param": "model"
  }
}
```

### `chat.end`

Final event containing the full aggregated response, equivalent to the non-streaming `POST /api/v1/chat` response body.

| Field | Type | Description |
| --- | --- | --- |
| `result` | object | Final response with `model_instance_id`, `output`, `stats`, and optional `response_id`. |
| `type` | `"chat.end"` | The type of the event. |

```json
{
  "type": "chat.end",
  "result": {
    "model_instance_id": "openai/gpt-oss-20b",
    "output": [
      { "type": "reasoning", "content": "Need to call function." },
      {
        "type": "tool_call",
        "tool": "model_search",
        "arguments": { "sort": "trendingScore", "limit": 1 },
        "output": "[{\"type\":\"text\",\"text\":\"Showing first 1 models...\"}]",
        "provider_info": { "type": "ephemeral_mcp", "server_label": "huggingface" }
      },
      { "type": "message", "content": "The current top-trending model is..." }
    ],
    "stats": {
      "input_tokens": 329,
      "total_output_tokens": 268,
      "reasoning_output_tokens": 5,
      "tokens_per_second": 43.73,
      "time_to_first_token_seconds": 0.781
    },
    "response_id": "resp_02b2017dbc06c12bfc353a2ed6c2b802f8cc682884bb5716"
  }
}
```

---

## `POST /api/v1/chat` — Full Reference

### Request Body

| Field | Type | Required | Description |
| --- | --- | :---: | --- |
| `model` | string | Yes | Unique identifier for the model to use. |
| `input` | string \| array\<object\> | Yes | Message to send to the model. Can be a plain string, or an array of input items (text or image). |
| `system_prompt` | string | No | System message that sets model behavior or instructions. |
| `integrations` | array\<string \| object\> | No | List of integrations (plugins, ephemeral MCP servers, etc.) to enable for this request. |
| `stream` | boolean | No | Whether to stream partial outputs via SSE. Default `false`. |
| `temperature` | number | No | Randomness in token selection. `0` is deterministic, higher values increase creativity. Range `[0,1]`. |
| `top_p` | number | No | Minimum cumulative probability for the possible next tokens. Range `[0,1]`. |
| `top_k` | integer | No | Limits next token selection to the top-k most probable tokens. |
| `min_p` | number | No | Minimum base probability for a token to be selected for output. Range `[0,1]`. |
| `repeat_penalty` | number | No | Penalty for repeating token sequences. `1` is no penalty; higher values discourage repetition. |
| `max_output_tokens` | integer | No | Maximum number of tokens to generate. |
| `reasoning` | `"off"` \| `"low"` \| `"medium"` \| `"high"` \| `"on"` | No | Reasoning setting. Errors if the model does not support the chosen setting. |
| `context_length` | integer | No | Number of tokens to consider as context. Higher values recommended for MCP usage. |
| `store` | boolean | No | Whether to store the chat. If set, response will return a `response_id` field. Default `true`. |
| `previous_response_id` | string | No | Identifier of existing response to append to. Must start with `resp_`. |

#### `input` as an array of objects

**Text input:**

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"message"` | Type of input item. |
| `content` | string | Text content of the message. |

**Image input:**

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"image"` | Type of input item. |
| `data_url` | string | Image data as a base64-encoded data URL. |

#### `integrations` entries

- **Plugin id (shorthand):** a string matching `mcp/<server_label>`.
- **Plugin object:**

  | Field | Type | Description |
    | --- | --- | --- |
  | `type` | `"plugin"` | Type of integration. |
  | `id` | string | Unique identifier of the plugin. |
  | `allowed_tools` | array\<string\> (optional) | List of tool names the model can call from this plugin. If omitted, all tools are allowed. |

- **Ephemeral MCP server:**

  | Field | Type | Description |
    | --- | --- | --- |
  | `type` | `"ephemeral_mcp"` | Type of integration. |
  | `server_label` | string | Label to identify the MCP server. |
  | `server_url` | string | URL of the MCP server. |
  | `allowed_tools` | array\<string\> (optional) | List of tool names the model can call from this server. |
  | `headers` | object (optional) | Custom HTTP headers to send with requests to the server. |

### Example Request — with MCP

```bash
curl http://localhost:1234/api/v1/chat \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro",
    "input": "Tell me the top trending model on hugging face and navigate to https://lmstudio.ai",
    "integrations": [
      {
        "type": "ephemeral_mcp",
        "server_label": "huggingface",
        "server_url": "https://huggingface.co/mcp",
        "allowed_tools": ["model_search"]
      },
      {
        "type": "plugin",
        "id": "mcp/playwright",
        "allowed_tools": ["browser_navigate"]
      }
    ],
    "context_length": 8000,
    "temperature": 0
  }'
```

### Example Request — with Images

```bash
# Image is a small red square encoded as a base64 data URL
curl http://localhost:1234/api/v1/chat \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen/qwen3-vl-4b",
    "input": [
      {
        "type": "text",
        "content": "Describe this image in two sentences"
      },
      {
        "type": "image",
        "data_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAAFUlEQVR42mP8z8BQz0AEYBxVSF+FABJADveWkH6oAAAAAElFTkSuQmCC"
      }
    ],
    "context_length": 2048,
    "temperature": 0
  }'
```

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `model_instance_id` | string | Unique identifier for the loaded model instance that generated the response. |
| `output` | array\<object\> | Array of output items generated. Each item is a message, tool call, reasoning, or invalid tool call. |
| `stats` | object | Token usage and performance metrics. |
| `response_id` | string (optional) | Identifier of the response for subsequent requests. Present when `store` is `true`. |

#### `output` item types

**Message:**

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"message"` | Type of output item. |
| `content` | string | Text content of the message. |

**Tool call:**

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"tool_call"` | Type of output item. |
| `tool` | string | Name of the tool called. |
| `arguments` | object | Arguments passed to the tool. |
| `output` | string | Result returned from the tool. |
| `provider_info` | object | Information about the tool provider. |

**Reasoning:**

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"reasoning"` | Type of output item. |
| `content` | string | Text content of the reasoning. |

**Invalid tool call:**

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"invalid_tool_call"` | Type of output item. |
| `reason` | string | Reason why the tool call was invalid. |
| `metadata` | object | Metadata about the invalid tool call. |

#### `stats` fields

| Field | Type | Description |
| --- | --- | --- |
| `input_tokens` | number | Number of input tokens. Includes formatting, tool definitions, and prior messages. |
| `total_output_tokens` | number | Total number of output tokens generated. |
| `reasoning_output_tokens` | number | Number of tokens used for reasoning. |
| `tokens_per_second` | number | Generation speed in tokens per second. |
| `time_to_first_token_seconds` | number | Time in seconds to generate the first token. |
| `model_load_time_seconds` | number (optional) | Time taken to load the model for this request. Present only if the model was not already loaded. |

### Example Response — with MCP

```json
{
  "model_instance_id": "ibm/granite-4-micro",
  "output": [
    {
      "type": "tool_call",
      "tool": "model_search",
      "arguments": {
        "sort": "trendingScore",
        "query": "",
        "limit": 1
      },
      "output": "...",
      "provider_info": {
        "server_label": "huggingface",
        "type": "ephemeral_mcp"
      }
    },
    {
      "type": "message",
      "content": "..."
    },
    {
      "type": "tool_call",
      "tool": "browser_navigate",
      "arguments": {
        "url": "https://lmstudio.ai"
      },
      "output": "...",
      "provider_info": {
        "plugin_id": "mcp/playwright",
        "type": "plugin"
      }
    },
    {
      "type": "message",
      "content": "**Top Trending Model on Hugging Face** ... more details on the model or LM Studio itself!"
    }
  ],
  "stats": {
    "input_tokens": 646,
    "total_output_tokens": 586,
    "reasoning_output_tokens": 0,
    "tokens_per_second": 29.753900615398926,
    "time_to_first_token_seconds": 1.088,
    "model_load_time_seconds": 2.656
  },
  "response_id": "resp_4ef013eba0def1ed23f19dde72b67974c579113f544086de"
}
```

### Example Response — with Images

```json
{
  "model_instance_id": "qwen/qwen3-vl-4b",
  "output": [
    {
      "type": "message",
      "content": "This image is a solid, vibrant red square that fills the entire frame, with no discernible texture, pattern, or other elements. It presents a minimalist, uniform visual field of pure red, evoking a sense of boldness or urgency."
    }
  ],
  "stats": {
    "input_tokens": 17,
    "total_output_tokens": 50,
    "reasoning_output_tokens": 0,
    "tokens_per_second": 51.03762685242662,
    "time_to_first_token_seconds": 0.814
  },
  "response_id": "resp_0182bd7c479d7451f9a35471f9c26b34de87a7255856b9a4"
}
```

---

## `GET /api/v1/models` — List Models

This endpoint has no request parameters.

```bash
curl http://localhost:1234/api/v1/models \
  -H "Authorization: Bearer $LM_API_TOKEN"
```

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `models` | array | List of available models (both LLMs and embedding models). |

Each model object contains:

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"llm"` \| `"embedding"` | Type of model. |
| `publisher` | string | Model publisher name. |
| `key` | string | Unique identifier for the model. |
| `display_name` | string | Human-readable model name. |
| `architecture` | string \| null (optional) | Model architecture (e.g., `"llama"`, `"mistral"`). Absent for embedding models. |
| `quantization` | object \| null | Quantization information (`name`, `bits_per_weight`). |
| `size_bytes` | number | Size of the model in bytes. |
| `params_string` | string \| null | Human-readable parameter count (e.g., `"7B"`, `"13B"`). |
| `loaded_instances` | array | List of currently loaded instances of this model. |
| `max_context_length` | number | Maximum context length supported by the model in tokens. |
| `format` | `"gguf"` \| `"mlx"` \| null | Model file format. |
| `capabilities` | object (optional) | Model capabilities (`vision`, `trained_for_tool_use`, `reasoning`). Absent for embedding models. |
| `description` | string \| null (optional) | Model description. Absent for embedding models. |
| `variants` | array (optional) | List of available quantization variant names. |
| `selected_variant` | string (optional) | The currently selected variant name. |

### Example Response

```json
{
  "models": [
    {
      "type": "llm",
      "publisher": "google",
      "key": "google/gemma-4-26b-a4b",
      "display_name": "Gemma 4 26B A4B",
      "architecture": "gemma4",
      "quantization": {
        "name": "Q4_K_M",
        "bits_per_weight": 4
      },
      "size_bytes": 17990911801,
      "params_string": "26B-A4B",
      "loaded_instances": [
        {
          "id": "google/gemma-4-26b-a4b",
          "config": {
            "context_length": 4096,
            "eval_batch_size": 512,
            "parallel": 4,
            "flash_attention": true,
            "num_experts": 8,
            "offload_kv_cache_to_gpu": true
          }
        }
      ],
      "max_context_length": 262144,
      "format": "gguf",
      "capabilities": {
        "vision": true,
        "trained_for_tool_use": true,
        "reasoning": {
          "allowed_options": ["off", "on"],
          "default": "on"
        }
      },
      "description": null,
      "variants": ["google/gemma-4-26b-a4b@q4_k_m"],
      "selected_variant": "google/gemma-4-26b-a4b@q4_k_m"
    },
    {
      "type": "llm",
      "publisher": "deepseek",
      "key": "deepseek-r1",
      "display_name": "DeepSeek R1",
      "architecture": "deepseek",
      "quantization": {
        "name": "Q4_K_M",
        "bits_per_weight": 4
      },
      "size_bytes": 40492610355,
      "params_string": "671B",
      "loaded_instances": [],
      "max_context_length": 131072,
      "format": "gguf",
      "capabilities": {
        "vision": false,
        "trained_for_tool_use": true,
        "reasoning": {
          "allowed_options": ["on"],
          "default": "on"
        }
      },
      "description": null
    },
    {
      "type": "embedding",
      "publisher": "gaianet",
      "key": "text-embedding-nomic-embed-text-v1.5-embedding",
      "display_name": "Nomic Embed Text v1.5",
      "quantization": {
        "name": "F16",
        "bits_per_weight": 16
      },
      "size_bytes": 274290560,
      "params_string": null,
      "loaded_instances": [],
      "max_context_length": 2048,
      "format": "gguf"
    }
  ]
}
```

---

## `POST /api/v1/models/load` — Load Model

### Request Body

| Field | Type | Required | Description |
| --- | --- | :---: | --- |
| `model` | string | Yes | Unique identifier for the model to load. Can be an LLM or embedding model. |
| `context_length` | number | No | Maximum number of tokens that the model will consider. |
| `eval_batch_size` | number | No | Number of input tokens to process together in a single batch during evaluation. `llama.cpp` engine only. |
| `flash_attention` | boolean | No | Whether to optimize attention computation. Can decrease memory usage and improve generation speed. `llama.cpp` engine only. |
| `num_experts` | number | No | Number of experts to use during inference for MoE models. `llama.cpp` engine only. |
| `offload_kv_cache_to_gpu` | boolean | No | Whether KV cache is offloaded to GPU memory. If `false`, KV cache is stored in CPU memory/RAM. `llama.cpp` engine only. |
| `echo_load_config` | boolean | No | If `true`, echoes the final load configuration in the response under `load_config`. Default `false`. |

### Example Request

```bash
curl http://localhost:1234/api/v1/models/load \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-oss-20b",
    "context_length": 16384,
    "flash_attention": true,
    "echo_load_config": true
  }'
```

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `type` | `"llm"` \| `"embedding"` | Type of the loaded model. |
| `instance_id` | string | Unique identifier for the loaded model instance. |
| `load_time_seconds` | number | Time taken to load the model in seconds. |
| `status` | `"loaded"` | Load status. |
| `load_config` | object (optional) | The final configuration applied to the loaded model. Included only when `echo_load_config` is `true`. |

### Example Response

```json
{
  "type": "llm",
  "instance_id": "openai/gpt-oss-20b",
  "load_time_seconds": 9.099,
  "status": "loaded",
  "load_config": {
    "context_length": 16384,
    "eval_batch_size": 512,
    "flash_attention": true,
    "offload_kv_cache_to_gpu": true,
    "num_experts": 4
  }
}
```

---

## `POST /api/v1/models/download` — Download Model

### Request Body

| Field | Type | Required | Description |
| --- | --- | :---: | --- |
| `model` | string | Yes | The model to download. Accepts LM Studio model catalog identifiers (e.g., `openai/gpt-oss-20b`) and exact Hugging Face links. |
| `quantization` | string | No | Quantization level of the model to download (e.g., `Q4_K_M`). Only supported for Hugging Face links. |

### Example Request

```bash
curl http://localhost:1234/api/v1/models/download \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro"
  }'
```

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `job_id` | string (optional) | Unique identifier for the download job. Absent when `status` is `already_downloaded`. |
| `status` | enum | One of `downloading`, `paused`, `completed`, `failed`, `already_downloaded`. |
| `completed_at` | string (optional) | Download completion time in ISO 8601 format. Present when `status` is `completed`. |
| `total_size_bytes` | number (optional) | Total size of the download in bytes. |
| `started_at` | string (optional) | Download start time in ISO 8601 format. |

### Example Response

```json
{
  "job_id": "job_493c7c9ded",
  "status": "downloading",
  "total_size_bytes": 2279145003,
  "started_at": "2025-10-03T15:33:23.496Z"
}
```

---

## `POST /api/v1/models/unload` — Unload Model

### Request Body

| Field | Type | Required | Description |
| --- | --- | :---: | --- |
| `instance_id` | string | Yes | Unique identifier of the model instance to unload. |

### Example Request

```bash
curl http://localhost:1234/api/v1/models/unload \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "instance_id": "openai/gpt-oss-20b"
  }'
```

### Example Response

```json
{
  "instance_id": "openai/gpt-oss-20b"
}
```

---

## `GET /api/v1/models/download/status/:job_id` — Download Status

### Path Parameters

| Field | Type | Required | Description |
| --- | --- | :---: | --- |
| `job_id` | string | Yes | The unique identifier of the download job, returned by the download endpoint. |

### Example Request

```bash
curl -H "Authorization: Bearer $LM_API_TOKEN" \
  http://localhost:1234/api/v1/models/download/status/job_493c7c9ded
```

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `job_id` | string | Unique identifier for the download job. |
| `status` | enum | One of `downloading`, `paused`, `completed`, `failed`. |
| `bytes_per_second` | number (optional) | Current download speed. Present when `status` is `downloading`. |
| `estimated_completion` | string (optional) | Estimated completion time in ISO 8601. Present when `status` is `downloading`. |
| `completed_at` | string (optional) | Download completion time. Present when `status` is `completed`. |
| `total_size_bytes` | number (optional) | Total size of the download in bytes. |
| `downloaded_bytes` | number (optional) | Number of bytes downloaded so far. |
| `started_at` | string (optional) | Download start time in ISO 8601. |

### Example Response

```json
{
  "job_id": "job_493c7c9ded",
  "status": "completed",
  "total_size_bytes": 2279145003,
  "downloaded_bytes": 2279145003,
  "started_at": "2025-10-03T15:33:23.496Z",
  "completed_at": "2025-10-03T15:43:12.102Z"
}
```

---

## Legacy v0 REST API

> **Heads up:** LM Studio now has a v1 REST API. Use v1 for new projects. The v0 API is documented here for backwards compatibility.

Requires LM Studio 0.3.6 or newer.

### Supported v0 Endpoints

- `GET /api/v0/models` — List available models
- `GET /api/v0/models/{model}` — Get info about a specific model
- `POST /api/v0/chat/completions` — Chat Completions (messages -> assistant response)
- `POST /api/v0/completions` — Text Completions (prompt -> completion)
- `POST /api/v0/embeddings` — Text Embeddings (text -> embedding)

### Start the REST API Server

```bash
lms server start
```

> You can run LM Studio as a service and get the server to auto-start on boot without launching the GUI (Headless Mode).

### `GET /api/v0/models`

List all loaded and downloaded models.

```bash
curl -H "Authorization: Bearer $LM_API_TOKEN" http://localhost:1234/api/v0/models
```

Response:

```json
{
  "object": "list",
  "data": [
    {
      "id": "qwen2-vl-7b-instruct",
      "object": "model",
      "type": "vlm",
      "publisher": "mlx-community",
      "arch": "qwen2_vl",
      "compatibility_type": "mlx",
      "quantization": "4bit",
      "state": "not-loaded",
      "max_context_length": 32768
    },
    {
      "id": "meta-llama-3.1-8b-instruct",
      "object": "model",
      "type": "llm",
      "publisher": "lmstudio-community",
      "arch": "llama",
      "compatibility_type": "gguf",
      "quantization": "Q4_K_M",
      "state": "not-loaded",
      "max_context_length": 131072
    },
    {
      "id": "text-embedding-nomic-embed-text-v1.5",
      "object": "model",
      "type": "embeddings",
      "publisher": "nomic-ai",
      "arch": "nomic-bert",
      "compatibility_type": "gguf",
      "quantization": "Q4_0",
      "state": "not-loaded",
      "max_context_length": 2048
    }
  ]
}
```

### `GET /api/v0/models/{model}`

Get info about one specific model.

```bash
curl -H "Authorization: Bearer $LM_API_TOKEN" http://localhost:1234/api/v0/models/qwen2-vl-7b-instruct
```

Response:

```json
{
  "id": "qwen2-vl-7b-instruct",
  "object": "model",
  "type": "vlm",
  "publisher": "mlx-community",
  "arch": "qwen2_vl",
  "compatibility_type": "mlx",
  "quantization": "4bit",
  "state": "not-loaded",
  "max_context_length": 32768
}
```

### `POST /api/v0/chat/completions`

Chat Completions API. You provide a messages array and receive the next assistant response.

```bash
curl http://localhost:1234/api/v0/chat/completions \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "granite-3.0-2b-instruct",
    "messages": [
      { "role": "system", "content": "Always answer in rhymes." },
      { "role": "user", "content": "Introduce yourself." }
    ],
    "temperature": 0.7,
    "max_tokens": -1,
    "stream": false
  }'
```

Response:

```json
{
  "id": "chatcmpl-i3gkjwthhw96whukek9tz",
  "object": "chat.completion",
  "created": 1731990317,
  "model": "granite-3.0-2b-instruct",
  "choices": [
    {
      "index": 0,
      "logprobs": null,
      "finish_reason": "stop",
      "message": {
        "role": "assistant",
        "content": "Greetings, I'm a helpful AI, here to assist,\nIn providing answers, with no distress.\nI'll keep it short and sweet, in rhyme you'll find,\nA friendly companion, all day long you'll bind."
      }
    }
  ],
  "usage": {
    "prompt_tokens": 24,
    "completion_tokens": 53,
    "total_tokens": 77
  },
  "stats": {
    "tokens_per_second": 51.43709529007664,
    "time_to_first_token": 0.111,
    "generation_time": 0.954,
    "stop_reason": "eosFound"
  },
  "model_info": {
    "arch": "granite",
    "quant": "Q4_K_M",
    "format": "gguf",
    "context_length": 4096
  },
  "runtime": {
    "name": "llama.cpp-mac-arm64-apple-metal-advsimd",
    "version": "1.3.0",
    "supported_formats": ["gguf"]
  }
}
```

### `POST /api/v0/completions`

Text Completions API. You provide a prompt and receive a completion.

```bash
curl http://localhost:1234/api/v0/completions \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "granite-3.0-2b-instruct",
    "prompt": "the meaning of life is",
    "temperature": 0.7,
    "max_tokens": 10,
    "stream": false,
    "stop": "\n"
  }'
```

Response:

```json
{
  "id": "cmpl-p9rtxv6fky2v9k8jrd8cc",
  "object": "text_completion",
  "created": 1731990488,
  "model": "granite-3.0-2b-instruct",
  "choices": [
    {
      "index": 0,
      "text": " to find your purpose, and once you have",
      "logprobs": null,
      "finish_reason": "length"
    }
  ],
  "usage": {
    "prompt_tokens": 5,
    "completion_tokens": 9,
    "total_tokens": 14
  },
  "stats": {
    "tokens_per_second": 57.69230769230769,
    "time_to_first_token": 0.299,
    "generation_time": 0.156,
    "stop_reason": "maxPredictedTokensReached"
  },
  "model_info": {
    "arch": "granite",
    "quant": "Q4_K_M",
    "format": "gguf",
    "context_length": 4096
  },
  "runtime": {
    "name": "llama.cpp-mac-arm64-apple-metal-advsimd",
    "version": "1.3.0",
    "supported_formats": ["gguf"]
  }
}
```

### `POST /api/v0/embeddings`

Text Embeddings API. You provide text and a representation as an embedding vector is returned.

```bash
curl http://localhost:1234/api/v0/embeddings \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "text-embedding-nomic-embed-text-v1.5",
    "input": "Some text to embed"
  }'
```

Response:

```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "embedding": [
        -0.016731496900320053,
        0.028460891917347908,
        -0.1407836228609085,
        0.02505224384367466,
        -0.0037634256295859814,
        -0.04341062530875206
      ],
      "index": 0
    }
  ],
  "model": "text-embedding-nomic-embed-text-v1.5@q4_k_m",
  "usage": {
    "prompt_tokens": 0,
    "total_tokens": 0
  }
}
```

---

## Model Context Protocol (MCP) via API

Requires LM Studio 0.4.0 or newer. LM Studio supports MCP usage via API, allowing models to interact with external tools and services through standardized servers.

### How It Works

MCP servers provide tools that models can call during chat requests. You can enable MCP servers in two ways: as **ephemeral servers** defined per-request, or as **pre-configured servers** in your `mcp.json` file.

### Ephemeral vs `mcp.json` Servers

| Feature | Ephemeral | `mcp.json` |
| --- | --- | --- |
| How to specify in request | `integrations` -> `"type": "ephemeral_mcp"` | `integrations` -> `"type": "plugin"` |
| Configuration | Only defined per-request | Pre-configured in `mcp.json` |
| Use case | One-off requests, remote MCP tool execution | MCP servers that require `command`, frequently used servers |
| Server ID | Specified via `server_label` in integration | Specified via `id` (e.g., `mcp/playwright`) in integration |
| Custom headers | Supported via `headers` field | Configured in `mcp.json` |

### Ephemeral MCP Servers

Ephemeral MCP servers are defined on-the-fly in each request. Useful for testing or when you don't want to pre-configure servers.

> **Note:** Ephemeral MCP servers require the "Allow per-request MCPs" setting to be enabled in Server Settings.

```bash
curl http://localhost:1234/api/v1/chat \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro",
    "input": "What is the top trending model on hugging face?",
    "integrations": [
      {
        "type": "ephemeral_mcp",
        "server_label": "huggingface",
        "server_url": "https://huggingface.co/mcp",
        "allowed_tools": ["model_search"]
      }
    ],
    "context_length": 8000
  }'
```

The model can now call tools from the specified MCP server:

```json
{
  "model_instance_id": "ibm/granite-4-micro",
  "output": [
    { "type": "reasoning", "content": "..." },
    { "type": "message", "content": "..." },
    {
      "type": "tool_call",
      "tool": "model_search",
      "arguments": { "sort": "trendingScore", "limit": 1 },
      "output": "...",
      "provider_info": {
        "server_label": "huggingface",
        "type": "ephemeral_mcp"
      }
    },
    { "type": "reasoning", "content": "\n" },
    { "type": "message", "content": "The top trending model is ..." }
  ],
  "stats": {
    "input_tokens": 419,
    "total_output_tokens": 362,
    "reasoning_output_tokens": 195,
    "tokens_per_second": 27.620159487314744,
    "time_to_first_token_seconds": 1.437
  },
  "response_id": "resp_7c1a08e3d6e279efcfecb02df9de7cbd316e93422d0bb5cb"
}
```

### MCP Servers from `mcp.json`

MCP servers can be pre-configured in your `mcp.json` file. This is the recommended approach for MCP servers that take actions on your computer (like `microsoft/playwright-mcp`) and servers that you use frequently.

> **Note:** MCP servers from `mcp.json` require the "Allow calling servers from mcp.json" setting to be enabled in Server Settings.

```bash
curl http://localhost:1234/api/v1/chat \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro",
    "input": "Open lmstudio.ai",
    "integrations": ["mcp/playwright"],
    "context_length": 8000,
    "temperature": 0
  }'
```

### Restricting Tool Access

For both ephemeral and `mcp.json` servers, you can limit which tools the model can call using the `allowed_tools` field. This is useful if you do not want certain tools from an MCP server to be used, and can speed up prompt processing because the model receives fewer tool definitions.

```bash
curl http://localhost:1234/api/v1/chat \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro",
    "input": "What is the top trending model on hugging face?",
    "integrations": [
      {
        "type": "ephemeral_mcp",
        "server_label": "huggingface",
        "server_url": "https://huggingface.co/mcp",
        "allowed_tools": ["model_search"]
      }
    ],
    "context_length": 8000
  }'
```

If `allowed_tools` is not provided, all tools from the server are available to the model.

### Custom Headers for Ephemeral Servers

When using ephemeral MCP servers that require authentication, you can pass custom headers:

```bash
curl http://localhost:1234/api/v1/chat \
  -H "Authorization: Bearer $LM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro",
    "input": "Give me details about my SUPER-SECRET-PRIVATE Hugging face model",
    "integrations": [
      {
        "type": "ephemeral_mcp",
        "server_label": "huggingface",
        "server_url": "https://huggingface.co/mcp",
        "allowed_tools": ["model_search"],
        "headers": {
          "Authorization": "Bearer <YOUR_HF_TOKEN>"
        }
      }
    ],
    "context_length": 8000
  }'
```

---

## Idle TTL and Auto-Evict

### Background

- **JIT loading** makes it easy to use your LM Studio models in other apps: you don't need to manually load the model first before being able to use it. However, this also means that models can stay loaded in memory even when they're not being used. *Default: enabled.*
- **Idle TTL** (Time-To-Live) defines how long a model can stay loaded in memory without receiving any requests. When the TTL expires, the model is automatically unloaded from memory. You can set a TTL using the `ttl` field in your request payload. *Default: 60 minutes.*
- **Auto-Evict** unloads previously JIT-loaded models before loading new ones. This enables easy switching between models from client apps without having to manually unload them first. You can enable or disable this feature in Developer tab > Server Settings. *Default: enabled.*

### Idle TTL

**Use case:** imagine you're using an app like Zed, Cline, or Continue.dev to interact with LLMs served by LM Studio. These apps leverage JIT to load models on-demand the first time you use them.

**Problem:** When you're not actively using a model, you might not want it to remain loaded in memory.

**Solution:** Set a TTL for models loaded via API requests. The idle timer resets every time the model receives a request, so it won't disappear while you use it. A model is considered idle if it's not doing any work. When the idle TTL expires, the model is automatically unloaded from memory.

### Set App-default Idle TTL

By default, JIT-loaded models have a TTL of 60 minutes. You can configure a default TTL value for any model loaded via JIT from the Developer tab settings.

### Set per-model TTL in API Requests

When JIT loading is enabled, the **first request** to a model will load it into memory. You can specify a TTL for that model in the request payload. This works for both the OpenAI compatibility API and the v0 REST API:

```bash
curl http://localhost:1234/api/v0/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-r1-distill-qwen-7b",
    "ttl": 300,
    "messages": [ ... ]
  }'
```

This will set a TTL of 5 minutes (300 seconds) for this model if it is JIT-loaded.

### Set TTL for Models Loaded with `lms`

By default, models loaded with `lms load` do not have a TTL and remain loaded until manually unloaded. To set a TTL:

```bash
lms load <model> --ttl 3600
```

Loads `<model>` with a TTL of 1 hour (3600 seconds).

### Configure Auto-Evict for JIT-loaded Models

With this setting, you can ensure new models loaded via JIT automatically unload previously loaded models first. Useful when switching between models from another app without worrying about memory building up with unused models.

**When Auto-Evict is ON** (default):

- At most 1 model is kept loaded in memory at a time (when loaded via JIT)
- Non-JIT loaded models are not affected

**When Auto-Evict is OFF**:

- Switching models from an external app will keep previous models loaded in memory
- Models remain loaded until either their TTL expires, or you manually unload them

This feature works in tandem with TTL to provide better memory management for your workflow.

### Nomenclature

**TTL** (Time-To-Live) is a term borrowed from networking protocols and cache systems. It defines how long a resource can remain allocated before it's considered stale and evicted.

---

## OpenAI-Compatible API

### Supported Endpoints

| Endpoint | Method | Description |
| --- | --- | --- |
| `/v1/models` | GET | Models |
| `/v1/responses` | POST | Responses |
| `/v1/chat/completions` | POST | Chat Completions |
| `/v1/embeddings` | POST | Embeddings |
| `/v1/completions` | POST | Completions |

### Set the Base URL to Point to LM Studio

You can reuse existing OpenAI clients (in Python, JS, C#, etc.) by switching the base URL to point to your LM Studio instead of OpenAI's servers. The examples below assume the server port is `1234`.

**Python:**

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:1234/v1"
)
# ... the rest of your code ...
```

**TypeScript:**

```typescript
import OpenAI from 'openai';

const client = new OpenAI({
  baseUrl: "http://localhost:1234/v1"
});
// ... the rest of your code ...
```

**cURL:**

```bash
curl http://localhost:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "use the model identifier from LM Studio here",
    "messages": [{"role": "user", "content": "Say this is a test!"}],
    "temperature": 0.7
  }'
```

### Using Codex with LM Studio

Codex is supported because LM Studio implements the OpenAI-compatible `POST /v1/responses` endpoint.

### Chat Completions (`POST /v1/chat/completions`)

- Prompt template is applied automatically for chat-tuned models
- Provide inference parameters (temperature, top_p, etc.) in the payload
- Tip: keep a terminal open with `lms log stream` to inspect model input

Python example:

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

completion = client.chat.completions.create(
  model="model-identifier",
  messages=[
    {"role": "system", "content": "Always answer in rhymes."},
    {"role": "user", "content": "Introduce yourself."}
  ],
  temperature=0.7,
)

print(completion.choices[0].message)
```

Supported payload parameters:

```
model
top_p
top_k
messages
temperature
max_tokens
stream
stop
presence_penalty
frequency_penalty
logit_bias
repeat_penalty
seed
```

### Embeddings (`POST /v1/embeddings`)

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

def get_embedding(text, model="model-identifier"):
   text = text.replace("\n", " ")
   return client.embeddings.create(input=[text], model=model).data[0].embedding

print(get_embedding("Once upon a time, there was a cat."))
```

### List Models (`GET /v1/models`)

Returns the models visible to the server. The list may include all downloaded models when Just-In-Time loading is enabled.

```bash
curl http://localhost:1234/v1/models
```

### Responses (`POST /v1/responses`)

**Non-streaming:**

```bash
curl http://localhost:1234/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-oss-20b",
    "input": "Provide a prime number less than 50",
    "reasoning": { "effort": "low" }
  }'
```

**Stateful follow-up** — use the `id` from a previous response as `previous_response_id`:

```bash
curl http://localhost:1234/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-oss-20b",
    "input": "Multiply it by 2",
    "previous_response_id": "resp_123"
  }'
```

**Streaming:**

```bash
curl http://localhost:1234/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-oss-20b",
    "input": "Hello",
    "stream": true
  }'
```

You will receive SSE events such as `response.created`, `response.output_text.delta`, and `response.completed`.

**Tools and Remote MCP (opt-in)** — enable Remote MCP in the app (Developer → Settings):

```bash
curl http://localhost:1234/v1/responses \
  -H "Content-Type: application/json" \
  -d '{
    "model": "ibm/granite-4-micro",
    "input": "What is the top trending model on hugging face?",
    "tools": [
      {
        "type": "mcp",
        "server_label": "huggingface",
        "server_url": "https://huggingface.co/mcp",
        "allowed_tools": ["model_search"]
      }
    ]
  }'
```

---

## Structured Output

You can enforce a particular response format from an LLM by providing a JSON schema to the `/v1/chat/completions` endpoint via the REST API (or any OpenAI client). Doing this will cause the LLM to respond in valid JSON conforming to the schema provided.

This follows the same format as OpenAI's Structured Output API and is expected to work via the OpenAI client SDKs.

### Example using `curl`

```bash
curl http://localhost:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "{{model}}",
    "messages": [
      {
        "role": "system",
        "content": "You are a helpful jokester."
      },
      {
        "role": "user",
        "content": "Tell me a joke."
      }
    ],
    "response_format": {
      "type": "json_schema",
      "json_schema": {
        "name": "joke_response",
        "strict": "true",
        "schema": {
          "type": "object",
          "properties": {
            "joke": {
              "type": "string"
            }
          },
          "required": ["joke"]
        }
      }
    },
    "temperature": 0.7,
    "max_tokens": 50,
    "stream": false
  }'
```

All parameters recognized by `/v1/chat/completions` will be honored, and the JSON schema should be provided in the `json_schema` field of `response_format`.

The JSON object will be provided in string form in the typical response field, `choices[0].message.content`, and will need to be parsed into a JSON object.

### Example using Python

```python
from openai import OpenAI
import json

# Initialize OpenAI client that points to the local LM Studio server
client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio"
)

# Define the conversation with the AI
messages = [
    {"role": "system", "content": "You are a helpful AI assistant."},
    {"role": "user", "content": "Create 1-3 fictional characters"}
]

# Define the expected response structure
character_schema = {
    "type": "json_schema",
    "json_schema": {
        "name": "characters",
        "schema": {
            "type": "object",
            "properties": {
                "characters": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "occupation": {"type": "string"},
                            "personality": {"type": "string"},
                            "background": {"type": "string"}
                        },
                        "required": ["name", "occupation", "personality", "background"]
                    },
                    "minItems": 1,
                }
            },
            "required": ["characters"]
        },
    }
}

# Get response from AI
response = client.chat.completions.create(
    model="your-model",
    messages=messages,
    response_format=character_schema,
)

# Parse and display the results
results = json.loads(response.choices[0].message.content)
print(json.dumps(results, indent=2))
```

> **Important:** Not all models are capable of structured output, particularly LLMs below 7B parameters. Check the model card README if you are unsure if the model supports structured output.

### Structured Output Engine

- For `GGUF` models: uses `llama.cpp`'s grammar-based sampling APIs.
- For `MLX` models: uses Outlines. The MLX implementation is available on GitHub at `lmstudio-ai/mlx-engine`.

---

## Tool Use

Tool use enables LLMs to request calls to external functions and APIs through the `/v1/chat/completions` and `/v1/responses` endpoints, via the REST API (or via any OpenAI client). This expands model functionality far beyond text output.

### Quick Start

1. **Start LM Studio as a server:**

   ```bash
   lms server start
   ```

   Install `lms` by running `npx lmstudio install-cli`.

2. **Load a model** from the "Chat" or "Developer" tab, or via CLI:

   ```bash
   lms load
   ```

3. **Run an example** — see the curl and Python examples below.

### What Really Is "Tool Use"?

Tool use describes:

- LLMs output text requesting functions to be called (LLMs cannot directly execute code)
- Your code executes those functions
- Your code feeds the results back to the LLM

### High-Level Flow

```
┌──────────────────────────┐
│ SETUP: LLM + Tool list   │
└──────────┬───────────────┘
           ▼
┌──────────────────────────┐
│    Get user input        │◄────┐
└──────────┬───────────────┘     │
           ▼                     │
┌──────────────────────────┐     │
│ LLM prompted w/messages  │     │
└──────────┬───────────────┘     │
           ▼                     │
     Needs tools?                │
      │         │                │
    Yes         No               │
      │         │                │
      ▼         └────────────┐   │
┌─────────────┐              │   │
│Tool Response│              │   │
└──────┬──────┘              │   │
       ▼                     │   │
┌─────────────┐              │   │
│Execute tools│              │   │
└──────┬──────┘              │   │
       ▼                     ▼   │
┌─────────────┐          ┌───────────┐
│Add results  │          │  Normal   │
│to messages  │          │ response  │
└──────┬──────┘          └─────┬─────┘
       │                       ▲
       └───────────────────────┘
```

### In-Depth Flow

LM Studio supports tool use through `/v1/chat/completions` when given function definitions in the `tools` parameter of the request body. Tools are specified as an array of function definitions describing their parameters and usage.

It follows the same format as OpenAI's Function Calling API and is expected to work via the OpenAI client SDKs.

1. You provide a list of tools to the LLM that the model can *request* calls to:

   ```json
   [
     {
       "type": "function",
       "function": {
         "name": "get_delivery_date",
         "description": "Get the delivery date for a customer's order",
         "parameters": {
           "type": "object",
           "properties": {
             "order_id": {
               "type": "string"
             }
           },
           "required": ["order_id"]
         }
       }
     }
   ]
   ```

   This list is injected into the system prompt of the model based on its chat template. For example, for Qwen2.5-Instruct:

   ```
   <|im_start|>system
   You are Qwen, created by Alibaba Cloud. You are a helpful assistant.

   # Tools

   You may call one or more functions to assist with the user query.

   You are provided with function signatures within <tools></tools> XML tags:
   <tools>
   {"type": "function", "function": {"name": "get_delivery_date", ...}}
   </tools>

   For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
   <tool_call>
   {"name": <function-name>, "arguments": <args-json-object>}
   </tool_call><|im_end|>
   ```

   > **Important:** The model can only *request* calls to these tools because LLMs cannot directly call functions, APIs, or any other tools. They can only output text, which can then be parsed to programmatically call the functions.

2. When prompted, the LLM can either:

    - **Call one or more tools:**

      ```
      User: Get me the delivery date for order 123
      Model: <tool_call>
      {"name": "get_delivery_date", "arguments": {"order_id": "123"}}
      </tool_call>
      ```

    - **Respond normally:**

      ```
      User: Hi
      Model: Hello! How can I assist you today?
      ```

3. LM Studio parses the text output from the model into an OpenAI-compliant `chat.completion` response object.

    - If the model was given access to `tools`, LM Studio will attempt to parse the tool calls into the `response.choices[0].message.tool_calls` field.
    - If LM Studio cannot parse any correctly formatted tool calls, it will return the response to the standard `response.choices[0].message.content` field.
    - Smaller models or models not trained for tool use may output improperly formatted tool calls, which LM Studio cannot parse.

4. Your code parses the `chat.completion` response, checks for tool calls, and calls the appropriate tools with the parameters the model specified. Your code then adds both the model's tool call message and the tool result to the messages array:

   ```python
   # pseudocode
   if response.has_tool_calls:
       for each tool_call:
           function_to_call = tool_call.name     # e.g. "get_delivery_date"
           args = tool_call.arguments            # e.g. {"order_id": "123"}
           result = execute_function(function_to_call, args)
           add_to_messages([
               ASSISTANT_TOOL_CALL_MESSAGE,
               TOOL_RESULT_MESSAGE
           ])
   else:
       add_to_messages(response.content)
   ```

5. The LLM is then prompted again with the updated messages array, but **without access to tools**. This is because the LLM already has the tool results in the conversation history, and you want the LLM to provide a final response to the user rather than call more tools:

   ```python
   messages = [
       {"role": "user", "content": "When will order 123 be delivered?"},
       {"role": "assistant", "function_call": {
           "name": "get_delivery_date",
           "arguments": {"order_id": "123"}
       }},
       {"role": "tool", "content": "2024-03-15"},
   ]
   response = client.chat.completions.create(
       model="lmstudio-community/qwen2.5-7b-instruct",
       messages=messages
   )
   ```

   The `response.choices[0].message.content` field after this call may be something like:

   ```
   Your order #123 will be delivered on March 15th, 2024
   ```

6. The loop continues back at step 2.

This is the "pedantic" flow for tool use. You can certainly experiment with this flow to best fit your use case.

### Supported Models

Through LM Studio, all models support at least some degree of tool use. However, there are two levels of support that may impact quality: **Native** and **Default**.

Models with native tool-use support are shown with a hammer badge in the app and generally perform better in tool-use scenarios.

#### Native Tool Use Support

Native tool-use support means that both:

1. The model has a chat template that supports tool use (usually meaning the model has been trained for tool use). This formats the `tools` array into the system prompt and tells the model how to format tool calls.
2. LM Studio supports that model's tool-use format. This is required for LM Studio to properly input chat history into the chat template and parse the tool calls the model outputs into the `chat.completion` object.

Models that currently have native tool-use support (subject to change):

- **Qwen:** `lmstudio-community/Qwen2.5-7B-Instruct-GGUF` (4.68 GB), `mlx-community/Qwen2.5-7B-Instruct-4bit` (4.30 GB)
- **Llama-3.1, Llama-3.2:** `lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF` (4.92 GB), `mlx-community/Meta-Llama-3.1-8B-Instruct-8bit` (8.54 GB)
- **Mistral:** `bartowski/Ministral-8B-Instruct-2410-GGUF` (4.67 GB), `mlx-community/Ministral-8B-Instruct-2410-4bit` (4.67 GB)

#### Default Tool Use Support

Default tool-use support means either:

1. The model does not have a chat template that supports tool use.
2. LM Studio does not currently support that model's tool-use format.

Under the hood, default tool use works by giving models a custom system prompt and a default tool call format to use, converting `tool` role messages to the `user` role, and converting `assistant` role `tool_calls` into the default tool call format. Results will vary by model.

You can see the default format by running `lms log stream` in your terminal, then sending a chat completion request with `tools` to a model that doesn't have native tool-use support.

### Example using `curl`

```bash
curl http://localhost:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lmstudio-community/qwen2.5-7b-instruct",
    "messages": [{"role": "user", "content": "What dell products do you have under $50 in electronics?"}],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "search_products",
          "description": "Search the product catalog by various criteria.",
          "parameters": {
            "type": "object",
            "properties": {
              "query": {
                "type": "string",
                "description": "Search terms or product name"
              },
              "category": {
                "type": "string",
                "description": "Product category to filter by",
                "enum": ["electronics", "clothing", "home", "outdoor"]
              },
              "max_price": {
                "type": "number",
                "description": "Maximum price in dollars"
              }
            },
            "required": ["query"],
            "additionalProperties": false
          }
        }
      }
    ]
  }'
```

All parameters recognized by `/v1/chat/completions` will be honored, and the array of available tools should be provided in the `tools` field. If the model decides the user message is best fulfilled with a tool call, an array of tool call request objects will be provided in `choices[0].message.tool_calls`. The `finish_reason` field of the top-level response object will be populated with `"tool_calls"`.

Example response:

```json
{
  "id": "chatcmpl-gb1t1uqzefudice8ntxd9i",
  "object": "chat.completion",
  "created": 1730913210,
  "model": "lmstudio-community/qwen2.5-7b-instruct",
  "choices": [
    {
      "index": 0,
      "logprobs": null,
      "finish_reason": "tool_calls",
      "message": {
        "role": "assistant",
        "tool_calls": [
          {
            "id": "365174485",
            "type": "function",
            "function": {
              "name": "search_products",
              "arguments": "{\"query\":\"dell\",\"category\":\"electronics\",\"max_price\":50}"
            }
          }
        ]
      }
    }
  ],
  "usage": {
    "prompt_tokens": 263,
    "completion_tokens": 34,
    "total_tokens": 297
  },
  "system_fingerprint": "lmstudio-community/qwen2.5-7b-instruct"
}
```

The `tool_calls` field will need to be parsed to call actual functions/APIs.

### Single-Turn Python Example

A simple single-turn example enabling a model to call a function called `say_hello`:

```python
from openai import OpenAI

# Connect to LM Studio
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

# Define a simple function
def say_hello(name: str) -> str:
    print(f"Hello, {name}!")

# Tell the AI about our function
tools = [
    {
        "type": "function",
        "function": {
            "name": "say_hello",
            "description": "Says hello to someone",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The person's name"
                    }
                },
                "required": ["name"]
            }
        }
    }
]

# Ask the AI to use our function
response = client.chat.completions.create(
    model="lmstudio-community/qwen2.5-7b-instruct",
    messages=[{"role": "user", "content": "Can you say hello to Bob the Builder?"}],
    tools=tools
)

# Get the name the AI wants to use a tool to say hello to
tool_call = response.choices[0].message.tool_calls[0]
name = eval(tool_call.function.arguments)["name"]

# Actually call the say_hello function
say_hello(name)  # Prints: Hello, Bob the Builder!
```

### Multi-Turn Python Example

This example enables the model to call a `get_delivery_date` function and hand the result back to the model so it can fulfill the user's request in plain text:

```python
from datetime import datetime, timedelta
import json
import random
from openai import OpenAI

client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
model = "lmstudio-community/qwen2.5-7b-instruct"


def get_delivery_date(order_id: str) -> datetime:
    # Generate a random delivery date between today and 14 days from now
    today = datetime.now()
    random_days = random.randint(1, 14)
    delivery_date = today + timedelta(days=random_days)
    print(
        f"\nget_delivery_date function returns delivery date:\n\n{delivery_date}",
        flush=True,
    )
    return delivery_date


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_delivery_date",
            "description": "Get the delivery date for a customer's order.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "The customer's order ID.",
                    },
                },
                "required": ["order_id"],
                "additionalProperties": False,
            },
        },
    }
]

messages = [
    {
        "role": "system",
        "content": "You are a helpful customer support assistant. Use the supplied tools to assist the user.",
    },
    {
        "role": "user",
        "content": "Give me the delivery date and time for order number 1017",
    },
]

response = client.chat.completions.create(
    model=model,
    messages=messages,
    tools=tools,
)

print("\nModel response requesting tool call:\n", flush=True)
print(response, flush=True)

# Extract the arguments for get_delivery_date
tool_call = response.choices[0].message.tool_calls[0]
arguments = json.loads(tool_call.function.arguments)
order_id = arguments.get("order_id")

# Call the get_delivery_date function with the extracted order_id
delivery_date = get_delivery_date(order_id)

assistant_tool_call_request_message = {
    "role": "assistant",
    "tool_calls": [
        {
            "id": response.choices[0].message.tool_calls[0].id,
            "type": response.choices[0].message.tool_calls[0].type,
            "function": response.choices[0].message.tool_calls[0].function,
        }
    ],
}

# Create a message containing the result of the function call
function_call_result_message = {
    "role": "tool",
    "content": json.dumps(
        {
            "order_id": order_id,
            "delivery_date": delivery_date.strftime("%Y-%m-%d %H:%M:%S"),
        }
    ),
    "tool_call_id": response.choices[0].message.tool_calls[0].id,
}

# Prepare the chat completion call payload
completion_messages_payload = [
    messages[0],
    messages[1],
    assistant_tool_call_request_message,
    function_call_result_message,
]

# Send the tool call result back to the model
response = client.chat.completions.create(
    model=model,
    messages=completion_messages_payload,
)

print("\nFinal model response with knowledge of the tool call result:\n", flush=True)
print(response.choices[0].message.content, flush=True)
```

### Advanced Agent Example

Building on the principles above, we can combine LM Studio models with locally defined functions to create an "agent" that can open safe URLs in the default browser, check the current time, and analyze directories.

```python
import json
from urllib.parse import urlparse
import webbrowser
from datetime import datetime
import os
from openai import OpenAI

client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
model = "lmstudio-community/qwen2.5-7b-instruct"


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return bool(result.netloc)
    except Exception:
        return False


def open_safe_url(url: str) -> dict:
    SAFE_DOMAINS = {
        "lmstudio.ai",
        "huggingface.co",
        "github.com",
        "google.com",
        "wikipedia.org",
        "weather.com",
        "stackoverflow.com",
        "python.org",
        "docs.python.org",
    }

    try:
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url

        if not is_valid_url(url):
            return {"status": "error", "message": f"Invalid URL format: {url}"}

        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        base_domain = ".".join(domain.split(".")[-2:])

        if base_domain in SAFE_DOMAINS:
            webbrowser.open(url)
            return {"status": "success", "message": f"Opened {url} in browser"}
        else:
            return {
                "status": "error",
                "message": f"Domain {domain} not in allowed list",
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_current_time() -> dict:
    """Get the current system time with timezone information"""
    try:
        current_time = datetime.now()
        timezone = datetime.now().astimezone().tzinfo
        formatted_time = current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        return {
            "status": "success",
            "time": formatted_time,
            "timezone": str(timezone),
            "timestamp": current_time.timestamp(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def analyze_directory(path: str = ".") -> dict:
    """Count and categorize files in a directory"""
    try:
        stats = {
            "total_files": 0,
            "total_dirs": 0,
            "file_types": {},
            "total_size_bytes": 0,
        }

        for entry in os.scandir(path):
            if entry.is_file():
                stats["total_files"] += 1
                ext = os.path.splitext(entry.name)[1].lower() or "no_extension"
                stats["file_types"][ext] = stats["file_types"].get(ext, 0) + 1
                stats["total_size_bytes"] += entry.stat().st_size
            elif entry.is_dir():
                stats["total_dirs"] += 1
                for root, _, files in os.walk(entry.path):
                    for file in files:
                        try:
                            stats["total_size_bytes"] += os.path.getsize(os.path.join(root, file))
                        except (OSError, FileNotFoundError):
                            continue

        return {"status": "success", "stats": stats, "path": os.path.abspath(path)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


tools = [
    {
        "type": "function",
        "function": {
            "name": "open_safe_url",
            "description": "Open a URL in the browser if it's deemed safe",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to open"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current system time with timezone information",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_directory",
            "description": "Analyze the contents of a directory, counting files and folders",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "The directory path to analyze. Defaults to current directory.",
                    },
                },
                "required": [],
            },
        },
    },
]


def process_tool_calls(response, messages):
    """Process multiple tool calls and return the final response and updated messages"""
    tool_calls = response.choices[0].message.tool_calls

    assistant_tool_call_message = {
        "role": "assistant",
        "tool_calls": [
            {
                "id": tool_call.id,
                "type": tool_call.type,
                "function": tool_call.function,
            }
            for tool_call in tool_calls
        ],
    }

    messages.append(assistant_tool_call_message)

    tool_results = []
    for tool_call in tool_calls:
        arguments = (
            json.loads(tool_call.function.arguments)
            if tool_call.function.arguments.strip()
            else {}
        )

        if tool_call.function.name == "open_safe_url":
            result = open_safe_url(arguments["url"])
        elif tool_call.function.name == "get_current_time":
            result = get_current_time()
        elif tool_call.function.name == "analyze_directory":
            path = arguments.get("path", ".")
            result = analyze_directory(path)
        else:
            continue

        tool_result_message = {
            "role": "tool",
            "content": json.dumps(result),
            "tool_call_id": tool_call.id,
        }
        tool_results.append(tool_result_message)
        messages.append(tool_result_message)

    final_response = client.chat.completions.create(
        model=model,
        messages=messages,
    )

    return final_response


def chat():
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that can open safe web links, tell the current time, and analyze directory contents.",
        }
    ]

    print("Assistant: Hello! What would you like me to do?")
    print("(Type 'quit' to exit)")

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() == "quit":
            print("Assistant: Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
            )

            if response.choices[0].message.tool_calls:
                final_response = process_tool_calls(response, messages)
                print("\nAssistant:", final_response.choices[0].message.content)
                messages.append(
                    {
                        "role": "assistant",
                        "content": final_response.choices[0].message.content,
                    }
                )
            else:
                print("\nAssistant:", response.choices[0].message.content)
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.choices[0].message.content,
                    }
                )

        except Exception as e:
            print(f"\nAn error occurred: {str(e)}")
            exit(1)


if __name__ == "__main__":
    chat()
```

### Streaming Tool Calls

When streaming through `/v1/chat/completions` with `stream=true`, tool calls are sent in chunks. Function names and arguments are sent in pieces via `chunk.choices[0].delta.tool_calls.function.name` and `chunk.choices[0].delta.tool_calls.function.arguments`.

For example, to call `get_current_weather(location="San Francisco")`, the streamed `ChoiceDeltaToolCall` in each chunk will look like:

```python
ChoiceDeltaToolCall(index=0, id='814890118', function=ChoiceDeltaToolCallFunction(arguments='', name='get_current_weather'), type='function')
ChoiceDeltaToolCall(index=0, id=None, function=ChoiceDeltaToolCallFunction(arguments='{"', name=None), type=None)
ChoiceDeltaToolCall(index=0, id=None, function=ChoiceDeltaToolCallFunction(arguments='location', name=None), type=None)
ChoiceDeltaToolCall(index=0, id=None, function=ChoiceDeltaToolCallFunction(arguments='":"', name=None), type=None)
ChoiceDeltaToolCall(index=0, id=None, function=ChoiceDeltaToolCallFunction(arguments='San Francisco', name=None), type=None)
ChoiceDeltaToolCall(index=0, id=None, function=ChoiceDeltaToolCallFunction(arguments='"}', name=None), type=None)
```

These chunks must be accumulated throughout the stream to form the complete function signature for execution.

Example of a simple tool-enhanced streaming chatbot:

```python
from openai import OpenAI
import time

client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")
MODEL = "lmstudio-community/qwen2.5-7b-instruct"

TIME_TOOL = {
    "type": "function",
    "function": {
        "name": "get_current_time",
        "description": "Get the current time, only if asked",
        "parameters": {"type": "object", "properties": {}},
    },
}


def get_current_time():
    return {"time": time.strftime("%H:%M:%S")}


def process_stream(stream, add_assistant_label=True):
    """Handle streaming responses from the API"""
    collected_text = ""
    tool_calls = []
    first_chunk = True

    for chunk in stream:
        delta = chunk.choices[0].delta

        if delta.content:
            if first_chunk:
                print()
                if add_assistant_label:
                    print("Assistant:", end=" ", flush=True)
                first_chunk = False
            print(delta.content, end="", flush=True)
            collected_text += delta.content

        elif delta.tool_calls:
            for tc in delta.tool_calls:
                if len(tool_calls) <= tc.index:
                    tool_calls.append({
                        "id": "", "type": "function",
                        "function": {"name": "", "arguments": ""}
                    })
                tool_calls[tc.index] = {
                    "id": (tool_calls[tc.index]["id"] + (tc.id or "")),
                    "type": "function",
                    "function": {
                        "name": (tool_calls[tc.index]["function"]["name"] + (tc.function.name or "")),
                        "arguments": (tool_calls[tc.index]["function"]["arguments"] + (tc.function.arguments or ""))
                    }
                }
    return collected_text, tool_calls


def chat_loop():
    messages = []
    print("Assistant: Hi! I can tell the current time. (Type 'quit' to exit)")

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == "quit":
            break

        messages.append({"role": "user", "content": user_input})

        response_text, tool_calls = process_stream(
            client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=[TIME_TOOL],
                stream=True,
                temperature=0.2
            )
        )

        if not tool_calls:
            print()

        text_in_first_response = len(response_text) > 0
        if text_in_first_response:
            messages.append({"role": "assistant", "content": response_text})

        if tool_calls:
            tool_name = tool_calls[0]["function"]["name"]
            print()
            if not text_in_first_response:
                print("Assistant:", end=" ", flush=True)
            print(f"**Calling Tool: {tool_name}**")
            messages.append({"role": "assistant", "tool_calls": tool_calls})

            for tool_call in tool_calls:
                if tool_call["function"]["name"] == "get_current_time":
                    result = get_current_time()
                    messages.append({
                        "role": "tool",
                        "content": str(result),
                        "tool_call_id": tool_call["id"]
                    })

            final_response, _ = process_stream(
                client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    stream=True
                ),
                add_assistant_label=False
            )

            if final_response:
                print()
                messages.append({"role": "assistant", "content": final_response})


if __name__ == "__main__":
    chat_loop()
```

---

## Community

Chat with other LM Studio users, discuss LLMs, hardware, and more on the LM Studio Discord server.