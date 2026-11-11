"""Entity master data. Tickers come from this file, never from the model."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).with_name("entities.json")


def squash(text: str) -> str:
    return re.sub(r"\s", "", text)


@dataclass(frozen=True)
class Entity:
    name: str
    aliases: tuple[str, ...]
    type: str
    markets: tuple[str, ...]

    @property
    def surface_forms(self) -> tuple[str, ...]:
        parts = tuple(p for p in self.name.split("/") if "(" not in p)
        return (self.name, *parts, *self.aliases)


class EntityMaster:
    def __init__(self, entities: list[Entity]):
        self.entities = entities
        self._by_form = {squash(form).lower(): e for e in entities for form in e.surface_forms}

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "EntityMaster":
        rows = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            [
                Entity(r["name"], tuple(r["aliases"]), r["type"], tuple(x["market"] for x in r["listings"]))
                for r in rows
            ]
        )

    def resolve(self, raw: str) -> Entity | None:
        return self._by_form.get(squash(raw).lower())

    @staticmethod
    def named_in(forms: tuple[str, ...], text: str) -> bool:
        haystack = squash(text).lower()
        return any(squash(form).lower() in haystack for form in forms)
