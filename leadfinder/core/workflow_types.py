from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class WorkflowContext:
    search_id: str
    request: Dict[str, Any]

    plan: Dict[str, Any] = field(default_factory=dict)
    anchors: list = field(default_factory=list)
    raw_candidates: list = field(default_factory=list)

    scored: list = field(default_factory=list)
    website_enrichments: Dict[str, Any] = field(default_factory=dict)
    results: list = field(default_factory=list)

    budget_usage: Dict[str, Any] = field(default_factory=dict)
    export_paths: Dict[str, str] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
