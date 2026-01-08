#!/usr/bin/env python3
"""
Remove ALL emojis from the codebase.
Replaces emojis with text equivalents in all Python and JavaScript/TypeScript files.
"""
import os
import re
from pathlib import Path

# Emoji replacement map
EMOJI_REPLACEMENTS = {
    # Success/Completion
    "✅": "[SUCCESS]",
    "✓": "[OK]",

    # Errors/Failures
    "❌": "[ERROR]",
    "⛔": "[BLOCKED]",

    # Warnings
    "⚠️": "[WARNING]",
    "⚠": "[WARNING]",

    # Info/Status
    "ℹ️": "[INFO]",
    "ℹ": "[INFO]",
    "📝": "[NOTE]",
    "💡": "[TIP]",

    # Actions/Process
    "🔍": "[SEARCH]",
    "🔎": "[SEARCH]",
    "🚀": "[START]",
    "⏸️": "[PAUSE]",
    "⏸": "[PAUSE]",
    "⏹️": "[STOP]",
    "⏹": "[STOP]",
    "🔄": "[REFRESH]",
    "♻️": "[RECYCLE]",
    "🔧": "[FIX]",
    "⚙️": "[CONFIG]",
    "⚙": "[CONFIG]",

    # Data/Analytics
    "📊": "[STATS]",
    "📈": "[TREND]",
    "📉": "[DECLINE]",
    "📋": "[LIST]",
    "📄": "[FILE]",
    "📦": "[PACKAGE]",
    "🗂️": "[FOLDER]",
    "🗂": "[FOLDER]",

    # Communication
    "✉️": "[EMAIL]",
    "✉": "[EMAIL]",
    "📧": "[EMAIL]",
    "💬": "[CHAT]",
    "🗨️": "[MESSAGE]",
    "🗨": "[MESSAGE]",

    # Success/Achievement
    "🎯": "[TARGET]",
    "🏆": "[TOP]",
    "🥇": "[FIRST]",
    "🥈": "[SECOND]",
    "🥉": "[THIRD]",
    "⭐": "[STAR]",
    "🌟": "[FEATURED]",

    # Money/Business
    "💰": "[PRICE]",
    "💵": "[MONEY]",
    "💳": "[PAYMENT]",
    "🛒": "[CART]",
    "🛍️": "[SHOP]",
    "🛍": "[SHOP]",

    # Emoji marketing/social
    "🔥": "[HOT]",
    "✨": "[NEW]",
    "💫": "[SPECIAL]",
    "🎁": "[GIFT]",
    "🎉": "[LAUNCH]",
    "🎊": "[PROMO]",

    # Tech/Development
    "🖥️": "[DESKTOP]",
    "🖥": "[DESKTOP]",
    "💻": "[COMPUTER]",
    "📱": "[MOBILE]",
    "🔌": "[PLUGIN]",
    "🔋": "[BATTERY]",
    "⚡": "[FAST]",
    "🌐": "[WEB]",
    "🔗": "[LINK]",

    # Time
    "⏰": "[ALARM]",
    "⏱️": "[TIMER]",
    "⏱": "[TIMER]",
    "⏲️": "[CLOCK]",
    "⏲": "[CLOCK]",
    "🕐": "[TIME]",

    # Status indicators
    "👍": "[GOOD]",
    "👎": "[BAD]",
    "👇": "[BELOW]",
    "👆": "[ABOVE]",
    "👉": "[NEXT]",
    "👈": "[PREV]",
    "🆕": "[NEW]",
    "🆙": "[UP]",
    "🆗": "[OK]",

    # Misc
    "🎭": "[DEMO]",
    "🧪": "[TEST]",
    "🔒": "[LOCKED]",
    "🔓": "[UNLOCKED]",
    "🔐": "[SECURE]",
    "🚫": "[BLOCKED]",
    "❗": "[ALERT]",
    "❓": "[QUESTION]",
    "🙌": "[SUCCESS]",
    "👏": "[APPLAUSE]",
    "🚚": "[SHIPPING]",
    "📍": "[LOCATION]",
    "🏠": "[HOME]",
    "🤖": "[AI]",
    "🧠": "[BRAIN]",
    "💯": "[PERFECT]",
    "❤️": "[LOVE]",
    "❤": "[LOVE]",
}

def remove_emojis_from_file(file_path: Path) -> tuple[bool, int]:
    """
    Remove emojis from a single file.
    Returns (changed, count) where changed=True if file was modified, count=number of replacements.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content
        replacement_count = 0

        # Replace each emoji with its text equivalent
        for emoji, replacement in EMOJI_REPLACEMENTS.items():
            if emoji in content:
                count = content.count(emoji)
                content = content.replace(emoji, replacement)
                replacement_count += count

        # Also remove any remaining emoji characters using regex (fallback)
        # This catches any emojis not in our replacement map
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F700-\U0001F77F"  # alchemical symbols
            "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0001F251"
            "]+",
            flags=re.UNICODE
        )

        # Count and remove remaining emojis
        remaining_emojis = emoji_pattern.findall(content)
        if remaining_emojis:
            replacement_count += len(remaining_emojis)
            content = emoji_pattern.sub('', content)

        # Write back if changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, replacement_count

        return False, 0

    except Exception as e:
        print(f"[ERROR] Failed to process {file_path}: {e}")
        return False, 0

def main():
    # Define paths to process
    base_path = Path("/Users/stephenponce/Documents/Ospra OS/Bots/Ospra OS")

    # Directories to process
    directories_to_process = [
        base_path / "ospra_os",
        base_path / "frontend" / "src",
        base_path / "scripts",
        base_path / "tests",
        base_path / "migrations",
    ]

    # Also process root Python files
    root_files = [
        base_path / "main.py",
    ]

    # File extensions to process
    python_extensions = {'.py'}
    js_extensions = {'.js', '.jsx', '.ts', '.tsx'}
    all_extensions = python_extensions | js_extensions

    total_files = 0
    total_changed = 0
    total_replacements = 0

    print("[START] Removing ALL emojis from codebase...")
    print()

    # Process directories
    for directory in directories_to_process:
        if not directory.exists():
            continue

        print(f"[SEARCH] Processing directory: {directory.name}")

        for file_path in directory.rglob('*'):
            if not file_path.is_file():
                continue

            if file_path.suffix not in all_extensions:
                continue

            # Skip node_modules, .vite, etc.
            if any(skip in file_path.parts for skip in ['node_modules', '.vite', 'dist', '__pycache__', '.git']):
                continue

            total_files += 1
            changed, count = remove_emojis_from_file(file_path)

            if changed:
                total_changed += 1
                total_replacements += count
                relative_path = file_path.relative_to(base_path)
                print(f"  [OK] {relative_path} - Removed {count} emojis")

    # Process root files
    for file_path in root_files:
        if not file_path.exists():
            continue

        total_files += 1
        changed, count = remove_emojis_from_file(file_path)

        if changed:
            total_changed += 1
            total_replacements += count
            print(f"  [OK] {file_path.name} - Removed {count} emojis")

    print()
    print("=" * 60)
    print(f"[SUCCESS] Emoji removal complete!")
    print(f"  Files scanned: {total_files}")
    print(f"  Files modified: {total_changed}")
    print(f"  Total replacements: {total_replacements}")
    print("=" * 60)

if __name__ == "__main__":
    main()
