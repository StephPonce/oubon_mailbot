"""
Audit all API routes in the application.
Generates a report of endpoints, their locations, and potential issues.
"""

import ast
import os
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class RouteInfo:
    """Information about an API route."""
    method: str
    path: str
    function_name: str
    file_path: str
    line_number: int
    has_auth: bool = False
    has_validation: bool = False
    response_model: str = None
    tags: List[str] = field(default_factory=list)


class RouteAuditor(ast.NodeVisitor):
    """AST visitor to extract route information."""

    HTTP_METHODS = {'get', 'post', 'put', 'patch', 'delete', 'options', 'head'}

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.routes: List[RouteInfo] = []
        self.current_function = None

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Visit function definitions to find routes."""

        # Check decorators for route definitions
        for decorator in node.decorator_list:
            route_info = self._extract_route_from_decorator(decorator, node)
            if route_info:
                self.routes.append(route_info)

        self.generic_visit(node)

    def _extract_route_from_decorator(self, decorator, func_node):
        """Extract route info from decorator."""

        if not isinstance(decorator, ast.Call):
            return None

        # Check if it's a route decorator (@router.get, @app.post, etc.)
        if isinstance(decorator.func, ast.Attribute):
            method = decorator.func.attr.lower()

            if method in self.HTTP_METHODS:
                # Extract path
                path = ""
                if decorator.args and isinstance(decorator.args[0], ast.Constant):
                    path = decorator.args[0].value

                # Extract kwargs
                response_model = None
                tags = []

                for keyword in decorator.keywords:
                    if keyword.arg == "response_model":
                        if isinstance(keyword.value, ast.Name):
                            response_model = keyword.value.id
                    elif keyword.arg == "tags":
                        if isinstance(keyword.value, ast.List):
                            for elt in keyword.value.elts:
                                if isinstance(elt, ast.Constant):
                                    tags.append(elt.value)

                # Check for auth and validation
                has_auth = self._has_auth_dependency(func_node)
                has_validation = self._has_validation(func_node)

                return RouteInfo(
                    method=method.upper(),
                    path=path,
                    function_name=func_node.name,
                    file_path=self.file_path,
                    line_number=decorator.lineno,
                    has_auth=has_auth,
                    has_validation=has_validation,
                    response_model=response_model,
                    tags=tags
                )

        return None

    def _has_auth_dependency(self, node: ast.FunctionDef) -> bool:
        """Check if function has authentication dependency."""
        for arg in node.args.args:
            if arg.annotation:
                annotation_str = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else str(arg.annotation)
                if any(auth in annotation_str for auth in ['current_user', 'get_current_user', 'CurrentUser']):
                    return True
        return False

    def _has_validation(self, node: ast.FunctionDef) -> bool:
        """Check if function has request validation."""
        for arg in node.args.args:
            if arg.annotation:
                annotation_str = ast.unparse(arg.annotation) if hasattr(ast, 'unparse') else str(arg.annotation)
                if any(v in annotation_str for v in ['Request', 'Body', 'Query', 'Path', 'BaseModel']):
                    return True
        return False


def audit_routes(project_root: str = ".") -> Dict[str, List[RouteInfo]]:
    """Audit all routes in the project."""

    routes_by_file: Dict[str, List[RouteInfo]] = defaultdict(list)

    # Find all Python files in api/ directories
    api_patterns = ["**/api/**/*.py", "**/routes/**/*.py"]

    for pattern in api_patterns:
        for file_path in Path(project_root).glob(pattern):
            if "__pycache__" in str(file_path) or "/__init__.py" in str(file_path):
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    source = f.read()

                tree = ast.parse(source)
                auditor = RouteAuditor(str(file_path))
                auditor.visit(tree)

                if auditor.routes:
                    routes_by_file[str(file_path)] = auditor.routes

            except Exception as e:
                print(f"⚠️  Error parsing {file_path}: {e}")

    return routes_by_file


def generate_report(routes_by_file: Dict[str, List[RouteInfo]]) -> str:
    """Generate audit report."""

    report = ["# API Routes Audit Report\n"]
    report.append(f"Generated: {__import__('datetime').datetime.now().isoformat()}\n\n")

    # Summary
    total_routes = sum(len(routes) for routes in routes_by_file.values())
    total_files = len(routes_by_file)

    report.append("## Summary\n")
    report.append(f"- **Total Routes:** {total_routes}\n")
    report.append(f"- **Files with Routes:** {total_files}\n\n")

    # Routes by file
    report.append("## Routes by File\n\n")

    for file_path, routes in sorted(routes_by_file.items()):
        rel_path = file_path.replace(os.getcwd() + "/", "")
        report.append(f"### {rel_path}\n\n")
        report.append("| Method | Path | Function | Auth | Validation | Response Model |\n")
        report.append("|--------|------|----------|------|------------|----------------|\n")

        for route in sorted(routes, key=lambda r: (r.path, r.method)):
            auth = "✅" if route.has_auth else "❌"
            valid = "✅" if route.has_validation else "❌"
            model = route.response_model or "-"
            report.append(f"| {route.method} | `{route.path}` | {route.function_name} | {auth} | {valid} | {model} |\n")

        report.append("\n")

    # Issues
    report.append("## Potential Issues\n\n")

    # Check for routes without auth
    unauthed = []
    for file_path, routes in routes_by_file.items():
        for route in routes:
            if not route.has_auth and route.method not in ['GET', 'OPTIONS', 'HEAD']:
                rel_path = file_path.replace(os.getcwd() + "/", "")
                unauthed.append(f"- {route.method} `{route.path}` in {rel_path}")

    if unauthed:
        report.append("### Routes Without Authentication (non-GET)\n\n")
        report.extend(unauthed[:20])
        if len(unauthed) > 20:
            report.append(f"\n... and {len(unauthed) - 20} more\n")
        report.append("\n\n")
    else:
        report.append("### Routes Without Authentication\n\n")
        report.append("✅ All non-GET routes have authentication!\n\n")

    # Check for routes without response model
    no_model = []
    for file_path, routes in routes_by_file.items():
        for route in routes:
            if not route.response_model and route.method in ['GET', 'POST']:
                rel_path = file_path.replace(os.getcwd() + "/", "")
                no_model.append(f"- {route.method} `{route.path}` in {rel_path}")

    if no_model:
        report.append("### Routes Without Response Model\n\n")
        report.extend(no_model[:20])
        if len(no_model) > 20:
            report.append(f"\n... and {len(no_model) - 20} more\n")
        report.append("\n")

    # Check for duplicate paths
    all_paths = defaultdict(list)
    for file_path, routes in routes_by_file.items():
        for route in routes:
            key = f"{route.method} {route.path}"
            all_paths[key].append(file_path)

    duplicates = [(path, files) for path, files in all_paths.items() if len(files) > 1]
    if duplicates:
        report.append("### Duplicate Routes\n\n")
        for path, files in duplicates:
            report.append(f"- **{path}** defined in:\n")
            for f in files:
                rel_path = f.replace(os.getcwd() + "/", "")
                report.append(f"  - {rel_path}\n")
        report.append("\n")
    else:
        report.append("### Duplicate Routes\n\n")
        report.append("✅ No duplicate routes found!\n\n")

    return "".join(report)


if __name__ == "__main__":
    print("🔍 Auditing API routes...\n")

    routes = audit_routes("ospra_os")

    if not routes:
        print("⚠️  No routes found! Make sure you're running from the project root.")
        exit(1)

    report = generate_report(routes)

    # Create docs directory if it doesn't exist
    os.makedirs("docs", exist_ok=True)

    # Save report
    report_path = "docs/routes_audit.md"
    with open(report_path, "w") as f:
        f.write(report)

    print(report)
    print(f"\n✅ Report saved to {report_path}")
