#!/usr/bin/env python3
"""
check_empty_catches.py
Detects empty catch/except blocks in TypeScript/JavaScript files
More accurate than shell regex for multiline detection
"""

import re
import sys
from pathlib import Path

def has_meaningful_content(content: str) -> bool:
    """Check if catch block has meaningful content (not just comments/whitespace)"""
    # Remove single-line comments
    content = re.sub(r'//.*?$', '', content, flags=re.MULTILINE)
    # Remove multi-line comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove whitespace
    content = content.strip()
    return len(content) > 0

def find_empty_catches(file_path: Path) -> list:
    """Find empty catch blocks in a file"""
    empty_catches = []
    
    try:
        content = file_path.read_text()
    except Exception:
        return empty_catches
    
    # Find all catch blocks with line numbers
    # Pattern: catch(...) { ... }
    pattern = r'catch\s*\([^)]*\)\s*\{([^}]*)\}'
    
    for match in re.finditer(pattern, content):
        catch_body = match.group(1)
        
        if not has_meaningful_content(catch_body):
            # Find line number
            line_num = content[:match.start()].count('\n') + 1
            empty_catches.append((file_path, line_num))
    
    return empty_catches

def main():
    root_dir = Path(__file__).parent.parent
    
    # Search in apps and packages
    search_dirs = [
        root_dir / 'apps',
        root_dir / 'packages'
    ]
    
    all_empty_catches = []
    
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        
        # Find all TypeScript/JavaScript files
        for ext in ['*.ts', '*.tsx', '*.js', '*.jsx']:
            for file_path in search_dir.rglob(ext):
                # Skip build artifacts and dependencies
                path_str = str(file_path)
                if any(excl in path_str for excl in ['node_modules', 'generated', '.next', '.nuxt', '.output', 'dist', 'out', 'coverage']):
                    continue
                
                empty_catches = find_empty_catches(file_path)
                all_empty_catches.extend(empty_catches)
    
    if all_empty_catches:
        print("Found empty catch blocks:")
        for file_path, line_num in all_empty_catches:
            rel_path = file_path.relative_to(root_dir)
            print(f"  {rel_path}:{line_num}")
        sys.exit(1)
    
    sys.exit(0)

if __name__ == '__main__':
    main()
