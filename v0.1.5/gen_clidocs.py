"""Generate CLI docs"""
import mkdocs_gen_files

from enderchest import cli

root_parser, verb_parsers = cli.generate_parsers()

cli_guide = f"""
# Full Command-Line Interface Documentation

## Summary
```bash
{root_parser.format_help()}```
"""

for verb, parser in verb_parsers.items():
    level = len(f"enderchest {verb}".split())
    cli_guide += f"""
## `enderchest {verb}`
```bash
{parser.format_help()}```
"""

with mkdocs_gen_files.open("cli.md", "w") as cli_docs:
    cli_docs.write(cli_guide)
