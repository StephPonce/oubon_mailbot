#!/usr/bin/env python3
"""
Focused Import Audit Script for Ospra OS Project Code Only
Scans only the project directories (ospra_os/, app/, scripts/) excluding .venv
"""

import os
import ast
import sys
from pathlib import Path
from typing import List, Dict, Set
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class ImportIssue:
    file_path: str
    line_number: int
    import_statement: str
    issue_type: str  # 'missing_module', 'missing_attribute', 'circular'
    details: str


class ProjectImportAuditor:
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.issues: List[ImportIssue] = []
        self.all_modules: Set[str] = set()
        self.import_graph: Dict[str, Set[str]] = defaultdict(set)

        # Only scan these directories
        self.scan_dirs = ['ospra_os', 'app', 'scripts']

    def scan_project(self) -> List[ImportIssue]:
        """Scan only project Python files."""
        print(f"Scanning project directories: {', '.join(self.scan_dirs)}")

        # First pass: collect all existing modules
        self._collect_modules()
        print(f"Found {len(self.all_modules)} project modules")

        # Second pass: check all imports
        self._check_imports()

        # Third pass: detect circular imports
        self._detect_circular_imports()

        return self.issues

    def _collect_modules(self):
        """Collect all Python module paths in project directories."""
        for scan_dir in self.scan_dirs:
            scan_path = self.root_dir / scan_dir
            if not scan_path.exists():
                continue

            for py_file in scan_path.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue

                # Convert file path to module path
                rel_path = py_file.relative_to(self.root_dir)
                module_path = str(rel_path).replace("/", ".").replace("\\", ".").rstrip(".py")

                if module_path.endswith(".__init__"):
                    module_path = module_path[:-9]  # Remove .__init__

                self.all_modules.add(module_path)

    def _check_imports(self):
        """Check all imports in project files."""
        for scan_dir in self.scan_dirs:
            scan_path = self.root_dir / scan_dir
            if not scan_path.exists():
                continue

            for py_file in scan_path.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue

                self._check_file_imports(py_file)

    def _check_file_imports(self, file_path: Path):
        """Check imports in a single file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Could not read {file_path}: {e}")
            return

        try:
            tree = ast.parse(content, filename=str(file_path))
        except SyntaxError as e:
            self.issues.append(ImportIssue(
                file_path=str(file_path),
                line_number=e.lineno or 0,
                import_statement="",
                issue_type="syntax_error",
                details=str(e)
            ))
            return

        rel_path = file_path.relative_to(self.root_dir)
        current_module = str(rel_path).replace("/", ".").replace("\\", ".").rstrip(".py")

        if current_module.endswith(".__init__"):
            current_module = current_module[:-9]

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._check_import(
                        file_path, node.lineno,
                        f"import {alias.name}",
                        alias.name,
                        current_module
                    )

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""

                # Handle relative imports
                if node.level > 0:
                    parts = current_module.split(".")
                    if node.level <= len(parts):
                        base = ".".join(parts[:-node.level]) if node.level < len(parts) else ""
                        full_module = f"{base}.{module}" if base and module else base or module
                    else:
                        full_module = module
                else:
                    full_module = module

                names = [alias.name for alias in node.names]
                import_str = f"from {module} import {', '.join(names)}"

                self._check_import(
                    file_path, node.lineno,
                    import_str, full_module,
                    current_module, names
                )

    def _check_import(
        self,
        file_path: Path,
        line_number: int,
        import_statement: str,
        module_name: str,
        current_module: str,
        attributes: List[str] = None
    ):
        """Check if an import is valid."""
        # Add to import graph
        self.import_graph[current_module].add(module_name)

        # Skip standard library and third-party modules
        if self._is_external_module(module_name):
            return

        # Check if module exists in our project
        if not self._module_exists(module_name):
            self.issues.append(ImportIssue(
                file_path=str(file_path),
                line_number=line_number,
                import_statement=import_statement,
                issue_type="missing_module",
                details=f"Module '{module_name}' not found in project"
            ))

    def _is_external_module(self, module_name: str) -> bool:
        """Check if a module is external (stdlib or third-party)."""
        # Common external packages used in the project
        external_prefixes = [
            "fastapi", "sqlalchemy", "pydantic", "celery", "redis",
            "httpx", "aiohttp", "requests", "anthropic", "openai",
            "google", "boto3", "stripe", "jwt", "passlib", "bcrypt",
            "email", "datetime", "typing", "os", "sys", "json", "re",
            "logging", "asyncio", "pathlib", "collections", "dataclasses",
            "uuid", "hashlib", "base64", "urllib", "contextlib", "functools",
            "itertools", "abc", "enum", "copy", "time", "random", "math",
            "apscheduler", "schedule", "dateutil", "pytz", "dotenv",
            "starlette", "uvicorn", "gunicorn", "alembic", "pytest",
            "numpy", "pandas", "sklearn", "scipy", "PIL", "cv2",
            "tenacity", "backoff", "ratelimit", "cachetools",
            "selenium", "playwright", "beautifulsoup4", "lxml", "html5lib",
            "dns", "dnspython", "cryptography", "secrets", "string",
            "concurrent", "multiprocessing", "subprocess", "tempfile",
            "io", "csv", "xml", "html", "mimetypes", "shutil", "glob",
            "praw", "prawcore", "tweepy", "tiktoken", "diskcache",
            "click", "typer", "rich", "tqdm", "requests_oauthlib",
            "oauthlib", "python", "aiocron", "asyncpg", "aiosqlite",
            "billiard", "kombu", "vine", "amqp", "pyotp", "qrcode",
        ]

        first_part = module_name.split(".")[0] if module_name else ""
        return first_part in external_prefixes or first_part.startswith("_")

    def _module_exists(self, module_name: str) -> bool:
        """Check if a module exists in our project."""
        if not module_name:
            return True

        # Check exact match
        if module_name in self.all_modules:
            return True

        # Check if it's a submodule of an existing package
        for existing in self.all_modules:
            if module_name.startswith(existing + "."):
                return True
            if existing.startswith(module_name + "."):
                return True

        return False

    def _detect_circular_imports(self):
        """Detect circular import dependencies."""
        visited = set()
        rec_stack = set()
        circular_found = set()

        def dfs(module: str, path: List[str]) -> bool:
            visited.add(module)
            rec_stack.add(module)

            for imported in self.import_graph.get(module, []):
                if self._is_external_module(imported):
                    continue

                if imported not in visited:
                    if dfs(imported, path + [imported]):
                        return True
                elif imported in rec_stack:
                    # Found circular import
                    cycle_key = tuple(sorted([imported] + path))
                    if cycle_key not in circular_found:
                        circular_found.add(cycle_key)

                        cycle_start = path.index(imported) if imported in path else 0
                        cycle = path[cycle_start:] + [imported]

                        self.issues.append(ImportIssue(
                            file_path="Multiple files",
                            line_number=0,
                            import_statement=" -> ".join(cycle),
                            issue_type="circular_import",
                            details=f"Circular import detected: {' -> '.join(cycle)}"
                        ))
                    return True

            rec_stack.remove(module)
            return False

        for module in self.import_graph:
            if module not in visited:
                dfs(module, [module])

    def generate_report(self) -> str:
        """Generate a markdown report of all issues."""
        if not self.issues:
            return "# Project Import Audit Report\n\n✅ No import issues found in project code!"

        report = ["# Project Import Audit Report\n"]
        report.append(f"Found **{len(self.issues)}** issues in project code\n")

        # Group by issue type
        by_type = defaultdict(list)
        for issue in self.issues:
            by_type[issue.issue_type].append(issue)

        for issue_type, issues in sorted(by_type.items()):
            report.append(f"\n## {issue_type.replace('_', ' ').title()} ({len(issues)})\n")

            for issue in issues:
                report.append(f"- **{issue.file_path}:{issue.line_number}**")
                report.append(f"  - `{issue.import_statement}`")
                report.append(f"  - {issue.details}\n")

        return "\n".join(report)


def main():
    # Determine project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    auditor = ProjectImportAuditor(project_root)
    issues = auditor.scan_project()

    # Generate report
    report = auditor.generate_report()
    print("\n" + report)

    # Save report
    report_path = project_root / "project_import_audit.md"
    with open(report_path, "w") as f:
        f.write(report)
    print(f"\n✅ Report saved to: {report_path}")

    # Return exit code based on issues
    if issues:
        print(f"\n❌ Found {len(issues)} import issues in project code")
        sys.exit(1)
    else:
        print("\n✅ No import issues found in project code")
        sys.exit(0)


if __name__ == "__main__":
    main()
