from dataclasses import dataclass

from .label_data import LabelData
from .label_template import LabelTemplate


@dataclass
class PrintRequest:
    label: LabelTemplate
    data: LabelData
    copies: int = 1
    printer: str = ""
