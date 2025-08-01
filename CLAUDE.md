# CLAUDE.md

## Project Overview

ATOTW MCP server provides Claude access to 500+ English anaesthesia tutorials via semantic search and full-text retrieval.

## Key Design Decisions

1. **English-only filtering**: Only tutorials with `"english"` in `langs` array are processed. Non-English content is actively cleaned up during sync.

2. **Rate limiting**: 5-second delay between PDF downloads (hardcoded requirement from WFSA).

3. **Modular sync**: `sync.py` can be imported and called via `sync_tutorials(quick_check=bool)` without side effects.

4. **No caching**: ChromaDB handles persistence. Each search/retrieval is fresh.

## Data Schemas

### tt.json (tutorial metadata)
```json
{
  "id": "33945",
  "title": "Knobology in Regional Anaesthesia", 
  "number": "488",
  "publish_date": "January 10, 2023",
  "publish_date_unix": 1673308800,
  "abstract": "This tutorial covers...",
  "pdf": "https://resources.wfsahq.org/.../atow-488-00.pdf",
  "quiz_link": "https://resources.wfsahq.org/quiz/...",
  "langs": ["english"],
  "terms": [
    {"name": "Basic Sciences", "tax": "atotw-primary-category"},
    {"name": "ultrasound", "slug": "ultrasound", "tax": "post_tag"}
  ]
}
```

### MCP Tools

1. **search_tutorials(query: str, limit: int = 5)**
   - Returns: List of relevant tutorials with metadata
   - Uses: OpenAI embeddings → ChromaDB similarity search

2. **get_tutorial_content(tutorial_id: str)**
   - Returns: Full text from `texts/Tutorial_XXX.txt`
   - Requires: Prior text extraction via sync

3. **sync_tutorials(quick_check: bool = False)**
   - quick_check=True: Only checks for new tutorials
   - quick_check=False: Full sync with downloads
   - Returns: Dict with counts and errors

### Sync Result Schema
```python
{
    "new_tutorials": 0,
    "downloaded_pdfs": 0,
    "extracted_texts": 0,
    "created_embeddings": 0,
    "cleaned_pdfs": 0,      # Non-English removals
    "cleaned_texts": 0,
    "cleaned_embeddings": 0,
    "errors": []            # List of error strings
}
```

## Running & Testing

```bash
# Setup (first time)
uv sync
echo "OPENAI_API_KEY=sk-..." > .env

# Run sync manually
uv run sync.py

# Start MCP server
uv run mcp_server.py

# Run tests
uv run test_sync.py   # Tests filtering, cleanup logic
uv run test_mcp.py    # Tests tool definitions
```

## File Structure

```
pdfs/Tutorial_XXX.pdf     # Original PDFs (English only)
texts/Tutorial_XXX.txt    # Extracted text for retrieval
embeddings/               # ChromaDB vector store
tt.json                   # Tutorial metadata (filtered)
backups/tt_YYYY-MM-DD.json # Backups when changes detected
```

## Error Handling

- PDF download failures: Logged but doesn't stop sync
- Missing OpenAI key: Raises ValueError  
- ChromaDB issues: Caught and reported in sync results
- Non-existent tutorial ID: Returns error message via MCP

## Important Constraints

- Must maintain 5-second delay between PDF downloads
- Only process tutorials with `"english"` in langs array
- Text extraction required before tutorial content can be retrieved
- OpenAI API key required for embeddings (text-embedding-3-large)