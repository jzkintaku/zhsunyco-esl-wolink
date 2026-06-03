"""Re-export from zhsunyco_esl — all logic lives in the library."""
from zhsunyco_esl.client import ZhsunycoClient
from zhsunyco_esl.models import (
    LabelConfig, DEFAULT_CONFIG, DEVICES, KNOWN_PROFILES,
    WOLINK_SERVICE_UUID, SERVICE_UUIDS,
    KNOWN_MAC_PREFIX, KNOWN_NAME_PREFIX,
)
from zhsunyco_esl.image import (
    _DITHER_INDEX, process_image, process_pil_image, render_preview, quantize_image,
)

DEVICES["175"] = {
    "width": 416,
    "height": 240,
    "mirror": False,
    "rotate_cw": False,
    "row_major": True,
    "color": "BWRY",
    "name": "ESL-37BWRY",
}

__all__ = [
    "ZhsunycoClient",
    "LabelConfig", "DEFAULT_CONFIG",
    "DEVICES", "KNOWN_PROFILES",
    "WOLINK_SERVICE_UUID", "SERVICE_UUIDS",
    "KNOWN_MAC_PREFIX", "KNOWN_NAME_PREFIX",
    "_DITHER_INDEX",
    "process_image", "process_pil_image", "render_preview", "quantize_image",
]
