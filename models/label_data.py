from dataclasses import dataclass


@dataclass
class LabelData:
    values: dict[str, str]  # = field(default_factory=dict)

    def get(self, key: str) -> str:
        return self.values[key]
