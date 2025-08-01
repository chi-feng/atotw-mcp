# ATOTW MCP Server

Gives Claude access to 500+ anaesthesia tutorials from WFSA's Anaesthesia Tutorial of the Week (ATOTW) program.

## Quick Start

### Prerequisites
- Python 3.8+
- OpenAI API key
- Claude Desktop app

### Installation

1. Install uv (if you don't have it):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone and setup:
```bash
git clone https://github.com/yourusername/atotw-mcp
cd atotw-mcp
uv sync
echo "OPENAI_API_KEY=sk-..." > .env
```

3. Initial sync (downloads tutorials, ~30 min first time):
```bash
uv run sync.py
```

### Add to Claude Desktop

Edit Claude Desktop config:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "atotw": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/absolute/path/to/atotw-mcp",
        "mcp_server.py"
      ]
    }
  }
}
```

Restart Claude Desktop.

## Usage

Ask Claude medical questions:
- "What are the considerations for spinal anaesthesia in children?"
- "Search for tutorials about difficult airway management"
- "Find tutorial 550 about SGLT-2 inhibitors"
- "Check for new tutorials" (runs sync via MCP)

## Maintenance

Weekly sync (via Claude or command line):
```bash
uv run sync.py
```

## Features

- **Smart Search**: Uses embeddings to find relevant tutorials even with different terminology
- **Full Text Access**: Retrieves complete tutorial content for detailed answers
- **Auto-sync**: Can check for new tutorials through Claude
- **English Only**: Automatically filters to English-language content only

## File Structure

```
atotw-mcp/
├── mcp_server.py    # MCP server
├── sync.py          # Sync script
├── .env             # Your OpenAI key (create this)
├── pdfs/            # Downloaded tutorials
├── texts/           # Extracted text
├── embeddings/      # Search index
└── tt.json          # Tutorial metadata
```

## Troubleshooting

**"No tutorials found"**: Run `uv run sync.py` to download content.

**Search not working**: Check `.env` has valid OpenAI API key.

**Claude can't see the server**: Restart Claude Desktop after config changes.

## Credits

Tutorial content © World Federation of Societies of Anaesthesiologists (WFSA)