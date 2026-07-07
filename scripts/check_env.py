#!/usr/bin/env python3
import sys
from pathlib import Path

def main():
    root_dir = Path(__file__).resolve().parent.parent
    env_file = root_dir / ".env"
    example_file = root_dir / ".env.example"

    if not example_file.exists():
        print(f"Error: {example_file} not found.")
        sys.exit(1)
        
    def parse_keys(filepath: Path) -> set:
        if not filepath.exists():
            return set()
        keys = set()
        with filepath.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    keys.add(line.split("=", 1)[0].strip())
        return keys

    example_keys = parse_keys(example_file)
    env_keys = parse_keys(env_file)
    
    if not env_keys:
        print("Warning: .env file not found or empty.")
        sys.exit(0)

    missing = example_keys - env_keys
    stale = env_keys - example_keys

    issues = 0
    if missing:
        print("❌ Missing keys in .env (present in .env.example):")
        for k in sorted(missing):
            print(f"  - {k}")
        issues += 1
        
    if stale:
        print("⚠️  Stale keys in .env (not in .env.example):")
        for k in sorted(stale):
            print(f"  - {k}")
        issues += 1

    if issues == 0:
        print("✅ .env is fully in sync with .env.example")
        sys.exit(0)
    else:
        print("\nPlease update your .env file to match .env.example")
        sys.exit(1)

if __name__ == "__main__":
    main()
