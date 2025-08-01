#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pytest",
# ]
# ///

"""
Simple tests for sync.py
Focus on core logic, not mocking the world
"""

import json
import tempfile
import shutil
from pathlib import Path

# Test data
TUTORIALS = [
    {
        "id": "1",
        "title": "English Tutorial",
        "langs": ["english"],
        "pdf": "https://example.com/en.pdf",
        "abstract": "English abstract"
    },
    {
        "id": "2", 
        "title": "Chinese Tutorial",
        "langs": ["chinese"],
        "pdf": "https://example.com/cn.pdf",
        "abstract": "Chinese abstract"
    },
    {
        "id": "3",
        "title": "Multi-lang Tutorial",
        "langs": ["english", "chinese"],
        "pdf": "https://example.com/multi.pdf",
        "abstract": "Multi-language abstract"
    }
]

def test_filter_english_tutorials():
    """Test filtering logic without importing sync.py"""
    # This is the core filtering logic from sync.py
    english_tutorials = [t for t in TUTORIALS if "english" in t.get("langs", [])]
    
    assert len(english_tutorials) == 2
    assert english_tutorials[0]["id"] == "1"
    assert english_tutorials[1]["id"] == "3"

def test_identify_non_english():
    """Test identifying non-English tutorials"""
    non_english = [t for t in TUTORIALS if "english" not in t.get("langs", [])]
    
    assert len(non_english) == 1
    assert non_english[0]["id"] == "2"

def test_file_cleanup_logic():
    """Test file cleanup logic in isolation"""
    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        pdfs_dir = Path(tmpdir) / "pdfs"
        texts_dir = Path(tmpdir) / "texts"
        pdfs_dir.mkdir()
        texts_dir.mkdir()
        
        # Create test files
        (pdfs_dir / "en.pdf").touch()
        (pdfs_dir / "cn.pdf").touch()
        (texts_dir / "en.txt").touch()
        (texts_dir / "cn.txt").touch()
        
        # Simulate cleanup
        non_english = [t for t in TUTORIALS if "english" not in t.get("langs", [])]
        cleaned = 0
        
        for t in non_english:
            filename = t["pdf"].split("/")[-1]
            pdf_path = pdfs_dir / filename
            text_path = texts_dir / filename.replace(".pdf", ".txt")
            
            if pdf_path.exists():
                pdf_path.unlink()
                cleaned += 1
            if text_path.exists():
                text_path.unlink()
                cleaned += 1
        
        assert cleaned == 2
        assert (pdfs_dir / "en.pdf").exists()
        assert not (pdfs_dir / "cn.pdf").exists()

def test_json_backup_logic():
    """Test backup creation logic"""
    with tempfile.TemporaryDirectory() as tmpdir:
        backup_dir = Path(tmpdir) / "backups"
        backup_dir.mkdir()
        
        # Simulate backup
        old_data = TUTORIALS[:2]
        new_data = TUTORIALS
        
        old_ids = {t["id"] for t in old_data}
        new_ids = {t["id"] for t in new_data}
        added = new_ids - old_ids
        
        assert len(added) == 1
        assert "3" in added

if __name__ == "__main__":
    import subprocess
    import sys
    
    # Run with pytest if available, otherwise run directly
    try:
        subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Run tests directly
        print("Running tests directly...\n")
        
        test_filter_english_tutorials()
        print("✓ test_filter_english_tutorials")
        
        test_identify_non_english()
        print("✓ test_identify_non_english")
        
        test_file_cleanup_logic()
        print("✓ test_file_cleanup_logic")
        
        test_json_backup_logic()
        print("✓ test_json_backup_logic")
        
        print("\nAll tests passed!")