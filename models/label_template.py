from dataclasses import dataclass


@dataclass(frozen=True)
class LabelTemplate:
    name: str
    template: str
    fields: tuple[str, ...]
    description: str = ""
