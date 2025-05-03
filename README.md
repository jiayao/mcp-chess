# MCP Chess Server

This MCP let's you play chess against any LLM.

## Installation

To use this chess server, add the following configuration to your MCP config:

```json
{
  "mcpServers": {
    "chess": {
      "command": "uvx",
      "args": [
        "mcp-chess"
      ]
    }
  }
}
```

## Usage

![Chess starting position with black pieces](screenshots/start_black.png)

![A few moves later](screenshots/acc_dragon.png)



