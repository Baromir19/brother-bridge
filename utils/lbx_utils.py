import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


class LbxUtils:
    NS = {
        "pt": "http://schemas.brother.info/ptouch/2007/lbx/main",
    }

    @staticmethod
    def extract_fields(path: Path) -> list[str]:
        with zipfile.ZipFile(path) as zf:
            xml_content = zf.read("label.xml")

        root = ET.fromstring(xml_content)

        fields: list[str] = []

        for node in root.findall(".//pt:expanded", LbxUtils.NS):
            object_name = node.get("objectName")
            if object_name is not None:
                fields.append(object_name)

        return list(dict.fromkeys(fields))
