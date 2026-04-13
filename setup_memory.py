#!/usr/bin/env python3
"""
NetVault - setup_memory.py
Create/maintain local memory workspace without overwriting existing files.

Run from repository root:
    python setup_memory.py
"""

from __future__ import annotations

import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent

# Canonical path from now on.
CANONICAL_MEMORY_DIR = REPO_ROOT / "memory"

# Backward-compatible fallback for existing folder casing in this repo.
LEGACY_MEMORY_DIR = REPO_ROOT / "Memory"
MEMORY_DIR = LEGACY_MEMORY_DIR if LEGACY_MEMORY_DIR.exists() else CANONICAL_MEMORY_DIR

OUTPUTS_DIR = Path("/mnt/user-data/outputs")


FOLDERS = [
    MEMORY_DIR,
    MEMORY_DIR / "sprints",
    MEMORY_DIR / "sprints" / "v0.1",
    MEMORY_DIR / "sprints" / "v0.2",
    MEMORY_DIR / "sprints" / "v0.5",
    MEMORY_DIR / "roadmap",
    MEMORY_DIR / "history",
]


README_CONTENT = """# NetVault - /memory

Carpeta de memoria local del proyecto.

Este espacio es la referencia central para:
- historial de decisiones
- contexto de sprints
- releases

## Estructura base

```
memory/
├── memory.md
├── releases.md
├── README.md
├── history/
├── roadmap/
└── sprints/
```
"""


FILES_TO_COPY = {
    "memory.md": MEMORY_DIR / "memory.md",
    "releases.md": MEMORY_DIR / "releases.md",
    "v0.2_sprint-1_react_migration.md": MEMORY_DIR / "sprints" / "v0.2" / "sprint-1_react_migration.md",
    "v0.2_sprint-1_prompt_antigravity.md": MEMORY_DIR / "sprints" / "v0.2" / "sprint-1_prompt_antigravity.md",
    "v0.5_sprint0_i18n.md": MEMORY_DIR / "sprints" / "v0.5" / "sprint0_i18n.md",
    "v0.5_sprint1_auth.md": MEMORY_DIR / "sprints" / "v0.5" / "sprint1_auth.md",
    "v0.5_prompts_master.md": MEMORY_DIR / "sprints" / "v0.5" / "prompts_master.md",
}


def ensure_dirs() -> None:
    print("NetVault - creating memory workspace")
    print("=" * 50)
    for folder in FOLDERS:
        folder.mkdir(parents=True, exist_ok=True)
        print(f"  + {folder.relative_to(REPO_ROOT)}/")


def ensure_readme() -> None:
    readme_path = MEMORY_DIR / "README.md"
    if readme_path.exists():
        print(f"  - {readme_path.relative_to(REPO_ROOT)} exists (kept)")
        return

    readme_path.write_text(README_CONTENT, encoding="utf-8")
    print(f"  + {readme_path.relative_to(REPO_ROOT)} created")


def copy_or_create_placeholders() -> None:
    print("\nCopying known memory docs (without overwrite):")
    for src_name, dest in FILES_TO_COPY.items():
        dest.parent.mkdir(parents=True, exist_ok=True)

        if dest.exists():
            print(f"  - {dest.relative_to(REPO_ROOT)} exists (kept)")
            continue

        src = OUTPUTS_DIR / src_name
        if src.exists():
            shutil.copy2(src, dest)
            print(f"  + {dest.relative_to(REPO_ROOT)} copied")
        else:
            dest.write_text(f"# {src_name}\n\n> Pending content import.\n", encoding="utf-8")
            print(f"  ~ {dest.relative_to(REPO_ROOT)} placeholder")


def print_tree(path: Path, level: int = 0) -> None:
    indent = "  " * level
    print(f"{indent}{path.name}/")
    entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    for entry in entries:
        if entry.is_dir():
            print_tree(entry, level + 1)
        else:
            print(f"{'  ' * (level + 1)}{entry.name}")


def main() -> None:
    ensure_dirs()
    ensure_readme()
    copy_or_create_placeholders()

    print("\n" + "=" * 50)
    print(f"Workspace ready: {MEMORY_DIR.relative_to(REPO_ROOT)}/")
    print("\nCurrent memory tree:")
    print_tree(MEMORY_DIR)


if __name__ == "__main__":
    main()
