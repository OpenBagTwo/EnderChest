"""Generate API docs"""

from pathlib import Path

import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()

for path in Path("enderchest").rglob("*.py"):
    if Path("enderchest") / "test" in path.parents:
        continue
    if path == Path("enderchest") / "__init__.py":
        py_path: tuple[str, ...] = ("enderchest",)
    elif path.name.startswith("_"):
        continue
    else:
        py_path = path.with_suffix("").parts

    doc_file_path = Path("reference") / path.with_suffix(".md")

    with mkdocs_gen_files.open(doc_file_path, "w") as doc_file:
        doc_file.write(f":::{'.'.join(py_path)}\n")

    mkdocs_gen_files.set_edit_path(doc_file_path, path)
    nav[py_path] = doc_file_path.relative_to(Path("reference")).as_posix()

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
