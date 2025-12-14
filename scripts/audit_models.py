#!/usr/bin/env python3
"""Audit multi_store_models.py to understand what needs splitting."""

import ast
import sys
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Set, Dict


@dataclass
class ModelInfo:
    name: str
    line_number: int
    bases: List[str]
    relationships: List[str]  # Other models this references
    columns: List[str]
    category: str  # Inferred category


def analyze_models_file(file_path: str) -> List[ModelInfo]:
    """Parse the models file and extract model information."""

    with open(file_path, 'r') as f:
        content = f.read()

    tree = ast.parse(content)
    models = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if it's a SQLAlchemy model (inherits from Base)
            bases = [b.id if isinstance(b, ast.Name) else
                     b.attr if isinstance(b, ast.Attribute) else str(b)
                     for b in node.bases]

            if 'Base' in bases or any('Base' in str(b) for b in bases):
                model = analyze_model_class(node)
                models.append(model)

    return models


def analyze_model_class(node: ast.ClassDef) -> ModelInfo:
    """Analyze a single model class."""

    relationships = []
    columns = []

    for item in node.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    col_name = target.id
                    columns.append(col_name)

                    # Check for ForeignKey or relationship
                    if isinstance(item.value, ast.Call):
                        func_name = ""
                        if isinstance(item.value.func, ast.Name):
                            func_name = item.value.func.id
                        elif isinstance(item.value.func, ast.Attribute):
                            func_name = item.value.func.attr

                        if func_name == "relationship":
                            # Extract related model name
                            if item.value.args:
                                arg = item.value.args[0]
                                if isinstance(arg, ast.Constant):
                                    relationships.append(arg.value)

    # Infer category from model name
    category = infer_category(node.name)

    return ModelInfo(
        name=node.name,
        line_number=node.lineno,
        bases=[b.id if isinstance(b, ast.Name) else str(b) for b in node.bases],
        relationships=relationships,
        columns=columns,
        category=category
    )


def infer_category(model_name: str) -> str:
    """Infer the category/module a model belongs to."""

    name_lower = model_name.lower()

    categories = {
        'user': ['user', 'account', 'profile', 'auth', 'permission', 'role'],
        'product': ['product', 'item', 'inventory', 'sku', 'variant'],
        'store': ['store', 'shop', 'merchant'],
        'order': ['order', 'transaction', 'purchase', 'cart'],
        'action': ['action', 'queue', 'pending', 'autopilot'],
        'ad': ['ad', 'campaign', 'advertising', 'marketing'],
        'email': ['email', 'message', 'notification', 'followup'],
        'analytics': ['analytic', 'metric', 'stat', 'report'],
        'learning': ['learning', 'weight', 'model', 'prediction', 'insight'],
        'testing': ['test', 'experiment', 'abtest', 'variant'],
        'template': ['template', 'strategy', 'marketplace'],
        'subscription': ['subscription', 'plan', 'tier', 'billing'],
        'integration': ['integration', 'connector', 'api', 'webhook'],
        'federated': ['federated', 'aggregate', 'contribution', 'consent'],
        'whitelabel': ['whitelabel', 'partner', 'branding', 'domain'],
        'ar': ['ar', '3d', 'asset', 'experience'],
    }

    for category, keywords in categories.items():
        if any(kw in name_lower for kw in keywords):
            return category

    return 'core'


def generate_report(models: List[ModelInfo]) -> str:
    """Generate a markdown report."""

    # Group by category
    by_category = defaultdict(list)
    for model in models:
        by_category[model.category].append(model)

    report = ["# Model Audit Report\n"]
    report.append(f"Total models: **{len(models)}**\n")

    report.append("## Models by Category\n")

    for category in sorted(by_category.keys()):
        category_models = by_category[category]
        report.append(f"### {category.title()} ({len(category_models)} models)\n")

        for model in sorted(category_models, key=lambda m: m.name):
            report.append(f"- **{model.name}** (line {model.line_number})")
            if model.relationships:
                report.append(f"  - Relationships: {', '.join(model.relationships)}")
        report.append("")

    # Dependency graph
    report.append("## Relationship Dependencies\n")
    report.append("```")
    for model in models:
        if model.relationships:
            report.append(f"{model.name} -> {', '.join(model.relationships)}")
    report.append("```\n")

    # Migration plan
    report.append("## Suggested File Split\n")

    file_mapping = {
        'user': 'user_models.py',
        'product': 'product_models.py',
        'store': 'store_models.py',
        'order': 'order_models.py',
        'action': 'actions_models.py',
        'ad': 'advertising_models.py',
        'email': 'email_models.py',
        'analytics': 'analytics_models.py',
        'learning': 'learning_models.py',
        'testing': 'testing_models.py',
        'template': 'template_models.py',
        'subscription': 'subscription_models.py',
        'integration': 'integration_models.py',
        'federated': 'federated_models.py',
        'whitelabel': 'whitelabel_models.py',
        'ar': 'ar_models.py',
        'core': 'models.py',
    }

    for category in sorted(by_category.keys()):
        target_file = file_mapping.get(category, f'{category}_models.py')
        category_models = by_category[category]
        report.append(f"- **{target_file}**: {', '.join(m.name for m in category_models)}")

    return "\n".join(report)


def main():
    # Find the models file
    possible_paths = [
        "ospra_os/database/multi_store_models.py",
        "database/multi_store_models.py",
        "multi_store_models.py"
    ]

    file_path = None
    for path in possible_paths:
        if Path(path).exists():
            file_path = path
            break

    if not file_path:
        print("Could not find multi_store_models.py")
        sys.exit(1)

    print(f"Analyzing: {file_path}\n")

    models = analyze_models_file(file_path)
    report = generate_report(models)

    print(report)

    # Save report
    with open("model_audit_report.md", "w") as f:
        f.write(report)

    print(f"\nReport saved to model_audit_report.md")


if __name__ == "__main__":
    main()
