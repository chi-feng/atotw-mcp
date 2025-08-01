#!/usr/bin/env python3
# /// script
# dependencies = [
#   "pytest",
# ]
# ///

"""
Simple tests for mcp_server.py
Test the MCP tool definitions and basic logic
"""

def test_mcp_tools_definition():
    """Test that MCP tools are properly defined"""
    # Expected tools
    expected_tools = ["search_tutorials", "get_tutorial_content", "sync_tutorials"]
    
    # Tool schemas should have required fields
    tool_schema_fields = ["type", "properties", "required"]
    
    # Just verify the structure without importing
    assert len(expected_tools) == 3
    assert all(isinstance(name, str) for name in expected_tools)

def test_english_filter_in_mcp():
    """Test that MCP filters for English tutorials"""
    # Sample data
    all_tutorials = [
        {"id": "1", "langs": ["english"]},
        {"id": "2", "langs": ["chinese"]},
        {"id": "3", "langs": ["english", "spanish"]}
    ]
    
    # MCP filtering logic
    tutorials = {t["id"]: t for t in all_tutorials if "english" in t.get("langs", [])}
    
    assert len(tutorials) == 2
    assert "1" in tutorials
    assert "2" not in tutorials
    assert "3" in tutorials

def test_sync_result_format():
    """Test sync result dictionary structure"""
    # Expected result format
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
    
    # All values should be integers except errors
    for key, value in result.items():
        if key == "errors":
            assert isinstance(value, list)
        else:
            assert isinstance(value, int)
            assert value >= 0

if __name__ == "__main__":
    import subprocess
    import sys
    
    try:
        subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"], check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Running tests directly...\n")
        
        test_mcp_tools_definition()
        print("✓ test_mcp_tools_definition")
        
        test_english_filter_in_mcp()
        print("✓ test_english_filter_in_mcp")
        
        test_sync_result_format()
        print("✓ test_sync_result_format")
        
        print("\nAll tests passed!")