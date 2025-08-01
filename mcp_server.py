#!/usr/bin/env python3
# /// script
# dependencies = [
#   "mcp",
#   "chromadb",
#   "openai",
#   "python-dotenv",
#   "requests",
#   "pypdf",
#   "tqdm",
# ]
# ///

import json
import os
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

import chromadb
from openai import OpenAI
from dotenv import load_dotenv
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Import sync functionality
import sync

# Load environment variables
load_dotenv()

# Initialize components
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
chroma_client = chromadb.PersistentClient(path="embeddings")
collection = chroma_client.get_collection("atotw_tutorials")

# Load tutorial metadata (English only)
with open("tt.json") as f:
    all_tutorials = json.load(f)
    tutorials = {t["id"]: t for t in all_tutorials if "english" in t.get("langs", [])}

# Create MCP server
server = Server("atotw-mcp")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="search_tutorials",
            description="Search ATOTW (Anaesthesia Tutorial of the Week) tutorials using semantic similarity. Returns tutorial metadata including title, abstract, category, and link to original WFSA page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'spinal anaesthesia in children', 'regional blocks')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results to return (default: 5, max: 10)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10
                    }
                },
                "required": ["query"]
            }
        ),
        types.Tool(
            name="get_tutorial_content",
            description="Retrieve the complete text content and metadata of a specific ATOTW tutorial. Returns full text, abstract, links, and publication details.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tutorial_id": {
                        "type": "string",
                        "description": "Tutorial ID (e.g., '33945')"
                    }
                },
                "required": ["tutorial_id"]
            }
        ),
        types.Tool(
            name="sync_tutorials",
            description="Synchronize the ATOTW tutorial database. Checks WFSA for new tutorials, downloads PDFs, extracts text, and creates embeddings for search. Only processes English-language tutorials. Respects 5-second rate limit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "quick_check": {
                        "type": "boolean",
                        "description": "If true, only check for new tutorials without downloading PDFs (default: false)",
                        "default": False
                    }
                },
                "required": []
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str,
    arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution."""
    global tutorials  # Declare global at function level
    
    if name == "search_tutorials":
        query = arguments.get("query", "")
        limit = min(arguments.get("limit", 5), 10)
        
        try:
            # Generate embedding for query
            embedding_response = client.embeddings.create(
                model="text-embedding-3-large",
                input=query
            )
            query_embedding = embedding_response.data[0].embedding
            
            # Search ChromaDB
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit
            )
            
            # Format results
            output = f"🔍 Search results for: '{query}'\n\n"
            
            if results["ids"][0]:
                for i, (id, metadata, distance) in enumerate(zip(
                    results["ids"][0], 
                    results["metadatas"][0],
                    results["distances"][0]
                )):
                    tutorial = tutorials.get(id, {})
                    output += f"{i+1}. **Tutorial {metadata['number']}: {metadata['title']}**\n"
                    output += f"   - Date: {metadata['date']}\n"
                    output += f"   - Category: {metadata['category']}\n"
                    output += f"   - Relevance: {100 - int(distance * 50):.0f}%\n"
                    output += f"   - Abstract: {tutorial.get('abstract', 'N/A')[:200]}...\n"
                    output += f"   - Tutorial ID: {id}\n"
                    output += f"   - Original page: {tutorial.get('link', 'N/A')}\n"
                    output += f"   - PDF: {tutorial.get('pdf', 'N/A')}\n"
                    output += f"   - Quiz: {tutorial.get('quiz_link', 'N/A')}\n\n"
            else:
                output += "No tutorials found matching your query."
            
            return [types.TextContent(type="text", text=output)]
            
        except Exception as e:
            return [types.TextContent(
                type="text", 
                text=f"❌ Error searching tutorials: {str(e)}"
            )]
    
    elif name == "get_tutorial_content":
        tutorial_id = arguments.get("tutorial_id", "")
        
        try:
            # Get tutorial metadata
            tutorial = tutorials.get(tutorial_id)
            if not tutorial:
                return [types.TextContent(
                    type="text",
                    text=f"❌ Tutorial ID {tutorial_id} not found"
                )]
            
            # Get PDF filename
            pdf_filename = tutorial.get("pdf", "").split("/")[-1]
            if not pdf_filename:
                return [types.TextContent(
                    type="text",
                    text=f"❌ No PDF available for tutorial {tutorial_id}"
                )]
            
            # Read extracted text
            text_path = Path("texts") / pdf_filename.replace(".pdf", ".txt")
            if not text_path.exists():
                return [types.TextContent(
                    type="text",
                    text=f"❌ Text not extracted for tutorial {tutorial_id}. Run sync.py first."
                )]
            
            with open(text_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Format output with all metadata
            output = f"📄 **Tutorial {tutorial['number']}: {tutorial['title']}**\n\n"
            output += f"**Metadata:**\n"
            output += f"- Published: {tutorial['publish_date']}\n"
            output += f"- Category: {next((t['name'] for t in tutorial.get('terms', []) if t['tax'] == 'atotw-primary-category'), 'Unknown')}\n"
            output += f"- Original page: {tutorial.get('link', 'N/A')}\n"
            output += f"- PDF download: {tutorial.get('pdf', 'N/A')}\n"
            output += f"- Quiz: {tutorial.get('quiz_link', 'N/A')}\n"
            
            # Get all tags
            tags = [t['name'] for t in tutorial.get('terms', []) if t['tax'] == 'post_tag']
            if tags:
                output += f"- Tags: {', '.join(tags[:10])}\n"
            
            output += f"\n**Abstract:**\n{tutorial.get('abstract', 'N/A')}\n\n"
            output += f"**Full Text:**\n{content[:10000]}..."  # Limit to 10k chars
            
            if len(content) > 10000:
                output += f"\n\n[Truncated - full text is {len(content)} characters]"
            
            return [types.TextContent(type="text", text=output)]
            
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error retrieving tutorial content: {str(e)}"
            )]
    
    elif name == "sync_tutorials":
        quick_check = arguments.get("quick_check", False)
        
        try:
            # Initialize sync components if needed
            if sync.collection is None:
                sync.initialize_components()
            
            # Run sync in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor,
                    sync.sync_tutorials,
                    quick_check
                )
            
            # Format results
            output = "🔄 **ATOTW Sync Results**\n\n"
            
            if quick_check:
                output += "📋 Quick check completed:\n"
            else:
                output += "📥 Full sync completed:\n"
            
            output += f"- New tutorials: {result['new_tutorials']}\n"
            
            if not quick_check:
                output += f"- PDFs downloaded: {result['downloaded_pdfs']}\n"
                output += f"- Texts extracted: {result['extracted_texts']}\n"
                output += f"- Embeddings created: {result['created_embeddings']}\n"
            
            if result['cleaned_pdfs'] > 0 or result['cleaned_texts'] > 0:
                output += "\n🧹 Cleanup:\n"
                output += f"- Non-English PDFs removed: {result['cleaned_pdfs']}\n"
                output += f"- Non-English texts removed: {result['cleaned_texts']}\n"
                output += f"- Non-English embeddings removed: {result['cleaned_embeddings']}\n"
            
            if result['errors']:
                output += f"\n⚠️  {len(result['errors'])} errors occurred:\n"
                for error in result['errors'][:5]:
                    output += f"- {error}\n"
                if len(result['errors']) > 5:
                    output += f"... and {len(result['errors']) - 5} more\n"
            
            # Reload tutorials after sync
            with open("tt.json") as f:
                all_tutorials = json.load(f)
                tutorials = {t["id"]: t for t in all_tutorials if "english" in t.get("langs", [])}
            
            output += f"\n✅ Total English tutorials in database: {len(tutorials)}"
            
            return [types.TextContent(type="text", text=output)]
            
        except Exception as e:
            return [types.TextContent(
                type="text",
                text=f"❌ Error during sync: {str(e)}"
            )]
    
    else:
        return [types.TextContent(
            type="text",
            text=f"❌ Unknown tool: {name}"
        )]

async def main():
    """Run the MCP server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="atotw-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                )
            )
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())