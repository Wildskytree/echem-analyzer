"""Matplotlib font configuration helpers."""

from __future__ import annotations

from typing import Optional

import matplotlib as mpl
from matplotlib import font_manager


CJK_FONT_CANDIDATES = [
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "Noto Sans CJK JP",
    "Source Han Sans SC",
    "Source Han Sans CN",
    "WenQuanYi Zen Hei",
    "PingFang SC",
    "Heiti SC",
    "Arial Unicode MS",
]

_CONFIGURED_FONT: Optional[str] = None


def configure_matplotlib_fonts() -> Optional[str]:
    """Configure Matplotlib to render Chinese labels when a CJK font exists."""
    global _CONFIGURED_FONT

    available = {font.name for font in font_manager.fontManager.ttflist}
    selected = next((name for name in CJK_FONT_CANDIDATES if name in available), None)

    mpl.rcParams["axes.unicode_minus"] = False
    mpl.rcParams["font.family"] = "sans-serif"

    current = list(mpl.rcParams.get("font.sans-serif", []))
    preferred = []
    if selected is not None:
        preferred.append(selected)
    preferred.extend(name for name in CJK_FONT_CANDIDATES if name in available and name != selected)
    preferred.extend(current)
    preferred.extend(["DejaVu Sans", "Arial", "Liberation Sans"])

    deduped = []
    for name in preferred:
        if name and name not in deduped:
            deduped.append(name)
    mpl.rcParams["font.sans-serif"] = deduped

    _CONFIGURED_FONT = selected
    return selected


def configured_cjk_font() -> Optional[str]:
    return _CONFIGURED_FONT


__all__ = ["configure_matplotlib_fonts", "configured_cjk_font", "CJK_FONT_CANDIDATES"]
