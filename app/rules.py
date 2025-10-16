import json
import re
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel


class Rule(BaseModel):
    apply_label: str
    match: List[str]
    name: Optional[str] = None
    auto_reply: bool = False
    auto_reply_template: Optional[str] = None


def _load_rules() -> List[Rule]:
    paths = [Path("data/rules.json"), Path("rules.json")]
    for path in paths:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                records = raw.get("rules") if isinstance(raw, dict) else raw
                rules: List[Rule] = []
                for entry in records or []:
                    data = dict(entry)
                    match_terms = data.get("match") or data.get("keywords") or data.get("if_any") or []
                    if isinstance(match_terms, str):
                        match_terms = [match_terms]
                    rule = Rule(
                        match=list(match_terms),
                        apply_label=data.get("apply_label"),
                        name=data.get("name"),
                        auto_reply=data.get("auto_reply", False),
                        auto_reply_template=data.get("auto_reply_template"),
                    )
                    rules.append(rule)
                if rules:
                    return rules
            except Exception as e:
                print(f"Rules load error: {e}—fallback to defaults")
    return [
        Rule(
            match=[
                "order",
                "package",
                "delivery",
                "tracking",
                "shipment",
                "arrived",
                "missing",
                "unreceived",
                "not received",
                "not arrived",
            ],
            apply_label="Orders",
            auto_reply=True,
            auto_reply_template="order_missing",
        ),
        Rule(
            match=["help", "issue", "support", "problem"],
            apply_label="Support",
            auto_reply=True,
            auto_reply_template="support_default",
        ),
    ]


def _match_label(body: str, subject: str, rules: List[Rule]) -> Optional[Rule]:
    text = f"{subject.lower()} {body.lower()}"
    for rule in rules:
        for word in rule.match:
            if re.search(rf"\b{re.escape(word.lower())}\b", text):
                return rule
    return None


_RULE_CACHE: List[Rule] = _load_rules()


def match_label_for_message(subject: str, body: str) -> Optional[str]:
    rule = _match_label(body or "", subject or "", _RULE_CACHE)
    return rule.apply_label if rule else None
