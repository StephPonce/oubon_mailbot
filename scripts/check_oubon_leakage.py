"""Guard: tenant-facing modules must stay brand-neutral (Pass 4b, commit a01830a).

Flags "Oubon" appearing in *runtime string literals* of the checked modules —
the strings that could leak into another tenant's emails or AI output.
Docstrings, comments, and DEFAULT_* constant assignments are allowed: Oubon is
the documented single-tenant default, not a hardcode.

Exit 1 with a listing if any violation is found; exit 0 otherwise.
"""

import ast
import sys

CHECKED = [
    "ospra_os/email_automation/policies.py",
    "ospra_os/ai/multi_provider_client.py",
    "ospra_os/email_automation/smart_reply.py",
    "ospra_os/email_automation/email_processor.py",
]


def docstring_nodes(tree):
    """Constant-string expression statements that are docstrings."""
    nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                nodes.add(body[0].value)
    return nodes


def default_assignment_strings(tree):
    """String constants assigned to DEFAULT_* names or DEFAULT_* keyword defaults."""
    allowed = set()
    for node in ast.walk(tree):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        if targets and any(isinstance(t, ast.Name) and t.id.startswith("DEFAULT_") for t in targets):
            for c in ast.walk(node.value):
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    allowed.add(c)
        if isinstance(node, ast.arguments):
            for default in list(node.defaults) + [d for d in node.kw_defaults if d]:
                for c in ast.walk(default):
                    if isinstance(c, ast.Constant) and isinstance(c.value, str):
                        allowed.add(c)
    return allowed


def main() -> int:
    violations = []
    for path in CHECKED:
        try:
            source = open(path).read()
        except FileNotFoundError:
            continue
        tree = ast.parse(source, filename=path)
        allowed = docstring_nodes(tree) | default_assignment_strings(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and "oubon" in node.value.lower() and node not in allowed:
                violations.append(f"{path}:{node.lineno}: {node.value[:80]!r}")
    if violations:
        print("Hardcoded 'Oubon' found in runtime strings (must go through tenancy/brand.py):")
        print("\n".join(violations))
        return 1
    print("OK: no Oubon leakage in runtime strings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
