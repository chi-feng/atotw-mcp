import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests
from pypdf import PdfReader
import chromadb
from openai import OpenAI
from dotenv import load_dotenv
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Global variables for initialized components
client = None
chroma_client = None
collection = None

def initialize_components():
    """Initialize OpenAI and ChromaDB components."""
    global client, chroma_client, collection
    
    # Setup directories if needed
    Path("pdfs").mkdir(exist_ok=True)
    Path("texts").mkdir(exist_ok=True)
    Path("backups").mkdir(exist_ok=True)
    Path("embeddings").mkdir(exist_ok=True)
    
    # Initialize OpenAI client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if not client.api_key:
        raise ValueError("OPENAI_API_KEY not found in .env file")
    
    # Initialize ChromaDB
    chroma_client = chromadb.PersistentClient(path="embeddings")
    collection = chroma_client.get_or_create_collection(
        name="atotw_tutorials",
        metadata={"hnsw:space": "cosine"}
    )

def sync_tutorials(quick_check=False):
    """
    Sync ATOTW tutorials.
    
    Args:
        quick_check: If True, only check for new tutorials without downloading
        
    Returns:
        dict: Summary of sync operation
    """
    result = {
        "new_tutorials": 0,
        "downloaded_pdfs": 0,
        "extracted_texts": 0,
        "created_embeddings": 0,
        "cleaned_pdfs": 0,
        "cleaned_texts": 0,
        "cleaned_embeddings": 0,
        "errors": []
    }
    
    try:
        # Initialize components if not already done
        if collection is None:
            initialize_components()
        # Fetch new data
        print("📡 Fetching latest tutorials...")
        response = requests.post(
            "https://resources.wfsahq.org/tt-ajax.php",
            data={"action": "get_tutorials"},
            headers={
                "User-Agent": "ATOTW-Sync/1.0",
                "Referer": "https://resources.wfsahq.org/anaesthesia-tutorial-of-the-week/"
            }
        )
        response.raise_for_status()
        all_data = response.json()
        
        # Filter for English tutorials only
        new_data = [t for t in all_data if "english" in t.get("langs", [])]
        print(f"📋 Found {len(all_data)} total tutorials, {len(new_data)} in English")
                
        # Compare with existing
        if os.path.exists("tt.json"):
            with open("tt.json") as f:
                old_data = json.load(f)
            
            # Filter old data for English only for fair comparison
            old_english_data = [t for t in old_data if "english" in t.get("langs", [])]
            old_ids = {t["id"] for t in old_english_data}
            new_ids = {t["id"] for t in new_data}
            added = new_ids - old_ids
            
            if added:
                result["new_tutorials"] = len(added)
                print(f"✨ Found {len(added)} new tutorials!")
                # Backup old file
                backup_name = f"backups/tt_{datetime.now().strftime('%Y-%m-%d')}.json"
                with open(backup_name, "w") as f:
                    json.dump(old_data, f)
                print(f"📦 Backed up to {backup_name}")
            else:
                print("✅ No new tutorials found")
        else:
            print("🆕 First run - all tutorials are new")
            added = {t["id"] for t in new_data}
            result["new_tutorials"] = len(added)
        
        # Save new data
        with open("tt.json", "w") as f:
            json.dump(new_data, f, indent=2)
        
        if quick_check:
            return result
        
        # Process PDFs and text
        print(f"📥 Processing {len(new_data)} tutorials...")
        
        # Count how many need processing
        to_download = []
        to_extract = []
        to_embed = []
        
        for tutorial in new_data:
            pdf_url = tutorial.get("pdf", "")
            if pdf_url:
                filename = pdf_url.split("/")[-1]
                pdf_path = f"pdfs/{filename}"
                text_path = f"texts/{filename.replace('.pdf', '.txt')}"
                
                if not os.path.exists(pdf_path):
                    to_download.append(tutorial)
                elif not os.path.exists(text_path):
                    to_extract.append(tutorial)
                
                existing = collection.get(ids=[tutorial["id"]])
                if not existing["ids"] and tutorial.get("abstract"):
                    to_embed.append(tutorial)
        
        # Download PDFs with progress bar
        if to_download:
            print(f"📥 Downloading {len(to_download)} PDFs...")
            with tqdm(total=len(to_download), desc="Downloading PDFs", unit="file") as pbar:
                for tutorial in to_download:
                    pdf_url = tutorial.get("pdf", "")
                    if not pdf_url:
                        pbar.update(1)
                        continue
                    
                    filename = pdf_url.split("/")[-1]
                    pdf_path = f"pdfs/{filename}"
                    
                    try:
                        pbar.set_postfix_str(f"{filename[:30]}...")
                        pdf_response = requests.get(pdf_url, timeout=30)
                        pdf_response.raise_for_status()
                        
                        with open(pdf_path, "wb") as f:
                            f.write(pdf_response.content)
                        
                        result["downloaded_pdfs"] += 1
                        pbar.update(1)
                        
                        # Rate limit with countdown
                        if result["downloaded_pdfs"] < len(to_download):
                            for i in range(2, 0, -1):
                                pbar.set_postfix_str(f"Rate limit: {i}s")
                                time.sleep(1)
                    except Exception as e:
                        result["errors"].append(f"Download error {filename}: {str(e)}")
                        pbar.set_postfix_str(f"Failed: {filename[:20]}")
                        pbar.update(1)
        
        # Extract text from PDFs
        if to_extract:
            print(f"📄 Extracting text from {len(to_extract)} PDFs...")
            for tutorial in tqdm(to_extract, desc="Extracting text", unit="PDF"):
                pdf_url = tutorial.get("pdf", "")
                if not pdf_url:
                    continue
                    
                filename = pdf_url.split("/")[-1]
                pdf_path = f"pdfs/{filename}"
                text_path = f"texts/{filename.replace('.pdf', '.txt')}"
                
                if os.path.exists(pdf_path):
                    try:
                        reader = PdfReader(pdf_path)
                        text = ""
                        for page in reader.pages:
                            text += page.extract_text() + "\n"
                        
                        with open(text_path, "w", encoding="utf-8") as f:
                            f.write(text)
                        
                        result["extracted_texts"] += 1
                    except Exception as e:
                        result["errors"].append(f"Extract error {filename}: {str(e)}")
        
        # Generate embeddings
        if to_embed:
            print(f"🧠 Generating embeddings for {len(to_embed)} tutorials...")
            for tutorial in tqdm(to_embed, desc="Embedding", unit="tutorial"):
                abstract = tutorial.get("abstract", "")
                if not abstract:
                    continue
                    
                try:
                    embedding_response = client.embeddings.create(
                        model="text-embedding-3-large",
                        input=abstract
                    )
                    embedding = embedding_response.data[0].embedding
                    
                    pdf_url = tutorial.get("pdf", "")
                    filename = pdf_url.split("/")[-1] if pdf_url else ""
                    
                    # Store in ChromaDB
                    collection.add(
                        embeddings=[embedding],
                        documents=[abstract],
                        metadatas=[{
                            "title": tutorial["title"],
                            "number": tutorial["number"],
                            "date": tutorial["publish_date"],
                            "pdf": filename,
                            "category": next((t["name"] for t in tutorial.get("terms", []) 
                                            if t["tax"] == "atotw-primary-category"), "Unknown")
                        }],
                        ids=[tutorial["id"]]
                    )
                    result["created_embeddings"] += 1
                except Exception as e:
                    result["errors"].append(f"Embedding error {tutorial['title']}: {str(e)}")
        
        print("📊 Summary:")
        print(f"  - {result['downloaded_pdfs']} PDFs downloaded")
        print(f"  - {result['extracted_texts']} texts extracted")
        print(f"  - {result['created_embeddings']} embeddings created")
        print(f"  - {len(result['errors'])} failures")
        
        # Generate Markdown index
        print("📝 Generating index.md...")
        categories = {}
        for tutorial in new_data:
            # Get primary category
            for term in tutorial.get("terms", []):
                if term["tax"] == "atotw-primary-category":
                    cat = term["name"]
                    if cat not in categories:
                        categories[cat] = []
                    categories[cat].append(tutorial)
                    break
        
        # Write index
        with open("index.md", "w") as f:
            f.write(f"# ATOTW Index\n\n")
            f.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d')}\n")
            f.write(f"Total tutorials: {len(new_data)}\n\n")
            
            # By category
            f.write("## Tutorials by Category\n\n")
            for cat in sorted(categories.keys()):
                f.write(f"### {cat}\n\n")
                for t in sorted(categories[cat], key=lambda x: x["publish_date_unix"], reverse=True):
                    # Extract tags
                    tags = [term["slug"] for term in t.get("terms", []) if term["tax"] == "post_tag"]
                    tag_str = " ".join(f"#{tag}" for tag in tags[:5])  # Limit to 5 tags
                    
                    # Extract PDF filename
                    pdf_filename = t.get("pdf", "").split("/")[-1] if t.get("pdf") else ""
                    
                    f.write(f"- [[Tutorial {t['number']} - {t['title']}]] - {t['publish_date']}\n")
                    if t.get("abstract"):
                        f.write(f"  - {t['abstract'][:150]}...\n")
                    if pdf_filename:
                        f.write(f"  - [PDF](pdfs/{pdf_filename})")
                    if t.get("quiz_link"):
                        f.write(f" | [Quiz]({t['quiz_link']})")
                    f.write("\n")
                    if tag_str:
                        f.write(f"  - Tags: {tag_str}\n")
                    f.write("\n")
        
        print("✅ Done!\n")
        
    except Exception as e:
        result["errors"].append(f"Fatal error: {str(e)}")
        print(f"❌ Fatal error: {e}")
    
    return result


def main():
    """Entry point for the script."""
    print("🔄 ATOTW Sync starting...\n")
    
    # Setup directories
    Path("pdfs").mkdir(exist_ok=True)
    Path("texts").mkdir(exist_ok=True)
    Path("backups").mkdir(exist_ok=True)
    Path("embeddings").mkdir(exist_ok=True)
    
    try:
        initialize_components()
    except ValueError as e:
        print(f"❌ Error: {e}")
        print("Please create a .env file with: OPENAI_API_KEY=your-key-here")
        exit(1)
    
    result = sync_tutorials()
    
    if result["errors"]:
        print(f"⚠️  {len(result['errors'])} errors occurred during sync")
        for error in result["errors"][:5]:  # Show first 5 errors
            print(f"  - {error}")
    
    print("📋 Ready for MCP server!")
    print("Run 'uv run mcp_server.py' to start the MCP server")


if __name__ == "__main__":
    main()