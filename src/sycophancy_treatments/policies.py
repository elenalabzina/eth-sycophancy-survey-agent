from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class TreatmentPolicy:
    condition_id: str
    label: str
    status: str
    version: str
    system_prompt: str
    construct: dict
    shared_constraints: list[str]
    policy_rules: list[str]

    @classmethod
    def from_yaml(cls, path: str | Path) -> "TreatmentPolicy":
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        required = {
            "condition_id",
            "label",
            "status",
            "version",
            "system_prompt",
            "construct",
            "shared_constraints",
            "policy_rules",
        }
        missing = required - set(raw or {})
        if missing:
            raise ValueError(f"Policy config missing fields: {sorted(missing)}")
        return cls(**{key: raw[key] for key in required})


def load_default_policies(config_dir: str | Path = "configs") -> dict[str, TreatmentPolicy]:
    root = Path(config_dir)
    neutral = TreatmentPolicy.from_yaml(root / "neutral.yaml")
    sycophantic = TreatmentPolicy.from_yaml(root / "sycophantic.yaml")
    return {
        "neutral": neutral,
        "sycophantic": sycophantic,
    }
