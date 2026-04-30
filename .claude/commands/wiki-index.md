Manage wiki/index.md entries (add, remove, update).

Usage: /wiki-index

Subcommands:
- `python tools/wiki_index.py add --section <section> --name <name> --path <path> --description <desc>`
- `python tools/wiki_index.py remove --path <path>`
- `python tools/wiki_index.py update --path <path> --description <desc>`

The agent must NEVER edit wiki/index.md directly — always use this tool.
