"""
MARKDOWN STRIPPER

Removes all markdown formatting symbols from text.
Ensures AI responses are clean, professional text without formatting symbols.

Used by ClaudeProvider and BriefingEngine to post-process AI outputs.
"""

import re


def strip_markdown(text: str) -> str:
    """
    Remove all markdown formatting symbols from text.

    Removes:
    - Headings (##, ###, etc.)
    - Bold/italic (**text**, *text*, __text__, _text_)
    - Strikethrough (~~text~~)
    - Code blocks (```code```, `code`)
    - Horizontal rules (---, ___, ***)
    - Bullet points (*, -, +)
    - Blockquotes (>)
    - Links ([text](url))
    - Images (![alt](url))

    Preserves:
    - Plain text content
    - Numbers and punctuation
    - Line breaks and structure

    Args:
        text: Text that may contain markdown

    Returns:
        Clean text without markdown symbols
    """
    if not text:
        return text

    # Remove code blocks (``` or ` wrapped)
    text = re.sub(r'```[\s\S]*?```', '', text)  # Multi-line code blocks
    text = re.sub(r'`([^`]+)`', r'\1', text)    # Inline code

    # Remove headings (## Heading -> Heading)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove bold/italic
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)  # Bold + italic
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)      # Bold
    text = re.sub(r'\*(.+?)\*', r'\1', text)          # Italic
    text = re.sub(r'___(.+?)___', r'\1', text)        # Bold + italic
    text = re.sub(r'__(.+?)__', r'\1', text)          # Bold
    text = re.sub(r'_(.+?)_', r'\1', text)            # Italic

    # Remove strikethrough
    text = re.sub(r'~~(.+?)~~', r'\1', text)

    # Remove horizontal rules
    text = re.sub(r'^[\*\-_]{3,}$', '', text, flags=re.MULTILINE)

    # Remove bullet points at start of line
    # Match: "* item", "- item", "+ item" -> "item"
    text = re.sub(r'^[\*\-\+]\s+', '', text, flags=re.MULTILINE)

    # Remove numbered list markers (1. item -> item)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)

    # Remove blockquotes
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

    # Remove links but keep text [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

    # Remove images ![alt](url) -> alt
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)

    # Clean up multiple consecutive blank lines (max 2)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Clean up spaces at start/end of lines
    lines = text.split('\n')
    lines = [line.strip() for line in lines]
    text = '\n'.join(lines)

    return text.strip()


def format_as_plain_list(items: list[str], numbered: bool = True) -> str:
    """
    Format a list of items as plain text without markdown symbols.

    Args:
        items: List of strings
        numbered: If True, use numbers (1, 2, 3). If False, indent only.

    Returns:
        Formatted plain text list
    """
    if not items:
        return ""

    if numbered:
        return '\n'.join(f"{i}. {item}" for i, item in enumerate(items, 1))
    else:
        return '\n'.join(f"   {item}" for item in items)


def format_as_plain_sections(sections: dict[str, str]) -> str:
    """
    Format sections with headers as plain text.

    Args:
        sections: Dict of {section_name: content}

    Returns:
        Formatted plain text with clear section breaks
    """
    if not sections:
        return ""

    result = []
    for title, content in sections.items():
        result.append(f"\n{title.upper()}\n")
        result.append(content)
        result.append("")  # Blank line between sections

    return '\n'.join(result).strip()
