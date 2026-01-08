#!/usr/bin/env python3
"""Automatically split multi_store_models.py into modular files."""

import re
from pathlib import Path
from typing import Dict, List


# Model categorization from audit report
MODEL_CATEGORIES = {
    'user_models.py': ['User', 'UserProductRecommendation', 'UserSettings', 'UserEmailAccount'],
    'store_models.py': ['Store', 'CrossStoreLearning'],
    'product_models.py': ['Product', 'ProductDeployment', 'ProductSaturation', 'ProductVelocity',
                          'ProductSnapshot', 'ProductIntelligence', 'ABTestVariant'],
    'actions_models.py': ['AutoPilotLog'],
    'advertising_models.py': ['AdCampaign'],
    'email_models.py': ['Email', 'EmailAutomationRule', 'EmailTemplate', 'EmailLabel', 'EmailFollowup'],
    'testing_models.py': ['ABTest', 'ABTestEvent', 'ABTestAssignment'],
    'core_models.py': ['AIUsage', 'RankingHistory', 'Niche', 'NicheSnapshot'],
}

# Additional models that might be needed (like Action, etc.)
ADDITIONAL_MODELS = {
    'actions_models.py': ['Action'],  # Add Action class if it exists
}


def extract_model_class(content: str, model_name: str) -> str:
    """Extract a model class definition from the file content."""
    # Pattern to match class definition and all its content until next class or end
    pattern = rf'^class {model_name}\(Base\):.*?(?=^class |\Z)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)

    if match:
        return match.group(0).rstrip()
    return ""


def read_models_file() -> str:
    """Read the multi_store_models.py file."""
    file_path = Path("ospra_os/database/multi_store_models.py")
    with open(file_path, 'r') as f:
        return f.read()


def create_model_file(filename: str, models: List[str], original_content: str):
    """Create a model file with the specified models."""
    # File header
    header = f'''"""
{filename.replace('_', ' ').replace('.py', '').title()} for OspraOS
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text,
    ForeignKey, Index, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import (
    Base,
    SubscriptionTier, Platform, StoreStatus, ProductStatus, DeploymentStatus,
    AIProvider, TaskType, TriggerType, ActionType, LifecycleStage,
    EntryTiming, RiskLevel
)


'''

    # Extract model classes
    model_defs = []
    for model_name in models:
        model_def = extract_model_class(original_content, model_name)
        if model_def:
            model_defs.append(model_def)
        else:
            print(f"[WARNING]  Warning: Could not find model {model_name}")

    if not model_defs:
        print(f"[ERROR] No models found for {filename}")
        return

    # Combine header and models
    content = header + "\n\n".join(model_defs) + "\n"

    # Write file
    output_path = Path(f"ospra_os/database/{filename}")
    with open(output_path, 'w') as f:
        f.write(content)

    print(f"[SUCCESS] Created {filename} with {len(model_defs)} models: {', '.join(models[:3])}{'...' if len(models) > 3 else ''}")


def extract_helper_functions(original_content: str) -> str:
    """Extract helper functions like get_session, get_followup_session."""
    # Look for function definitions at the end of the file
    pattern = r'^def (get_\w+)\(.*?\):.*?(?=^def |\Z)'
    matches = re.findall(pattern, original_content, re.MULTILINE | re.DOTALL)

    helper_code = []
    for match in re.finditer(pattern, original_content, re.MULTILINE | re.DOTALL):
        helper_code.append(match.group(0).rstrip())

    return "\n\n".join(helper_code) if helper_code else ""


def main():
    print("=" * 70)
    print("SPLITTING multi_store_models.py INTO MODULAR FILES")
    print("=" * 70)
    print()

    # Read original file
    print(" Reading ospra_os/database/multi_store_models.py...")
    original_content = read_models_file()
    print(f"   File size: {len(original_content)} characters")
    print()

    # Create each model file
    print("[NOTE] Creating modular model files...")
    print()

    for filename, models in MODEL_CATEGORIES.items():
        # Add any additional models for this file
        if filename in ADDITIONAL_MODELS:
            models = models + ADDITIONAL_MODELS[filename]

        create_model_file(filename, models, original_content)

    print()
    print("=" * 70)
    print("[NEW] Model files created successfully!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Review generated files in ospra_os/database/")
    print("  2. Create __init__.py to export all models")
    print("  3. Update imports throughout codebase")
    print("  4. Test import and SQLAlchemy registration")
    print()


if __name__ == "__main__":
    main()
