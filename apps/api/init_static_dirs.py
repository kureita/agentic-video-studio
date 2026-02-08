#!/usr/bin/env python3
"""Initialize static directories for the API server."""

from pathlib import Path

def init_static_dirs():
    """Create all required static directories."""
    dirs = [
        "static/audio",
        "static/images", 
        "static/videos",
    ]
    
    for dir_path in dirs:
        path = Path(dir_path)
        path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created directory: {dir_path}")
    
    print("\n✅ All static directories initialized!")
    print("You can now start the API server.")

if __name__ == "__main__":
    init_static_dirs()
