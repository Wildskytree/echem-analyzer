"""光谱数据模型。"""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

import numpy as np


class SpectrumTechnique(str, Enum):
    """光谱测试技术枚举。"""

    RAMAN = "Raman"
    XPS = "XPS"
    UV_VIS = "UV-vis"
    FTIR = "FTIR"
    NMR = "NMR"
    MS = "MS"
    PL = "PL"
    XRD = "XRD"


class Spectrum:
    """表示一次光谱测量及其处理结果。

    原始 x/y 数组在实例创建后不可写；处理后的数据通过
    :meth:`copy_with_processed` 生成新实例保存，避免原始数据被意外修改。
    """

    METADATA_FIELDS: Sequence[str] = (
        "sample_name",
        "date",
        "instrument",
        "excitation_wavelength",
        "laser_power_mW",
        "acquisition_time_s",
        "accumulations",
        "temperature",
        "comments",
    )

    def __init__(
        self,
        technique: Union[SpectrumTechnique, str],
        x: np.ndarray,
        y: np.ndarray,
        x_unit: str = "",
        y_unit: str = "",
        metadata: Optional[dict] = None,
        file_hash: Optional[str] = None,
    ) -> None:
        """初始化光谱对象。

        Args:
            technique: 光谱测试技术（如 'Raman'、'XPS'、'UV-vis' 等）。
            x: 原始 x 轴数据（如波数、结合能、波长等）。
            y: 原始 y 轴数据（如强度、吸光度、计数等）。
            x_unit: x 轴物理单位（如 'cm⁻¹'、'eV'、'nm'）。
            y_unit: y 轴物理单位（如 'a.u.'、'counts'、'Abs'）。
            metadata: 光谱元数据，缺失的标准字段会以 ``None`` 补齐。
            file_hash: 原始文件的 SHA-256 哈希值。

        Raises:
            ValueError: 当数组维度不是一维，或长度不一致时抛出。
        """

        self.technique = SpectrumTechnique(technique)
        self._raw_x = self._as_read_only_array("x", x)
        self._raw_y = self._as_read_only_array("y", y)
        self.x_unit = x_unit
        self.y_unit = y_unit
        self.file_hash = file_hash

        self._validate_lengths()

        self._metadata = self._build_metadata(metadata)
        self._processed_x: Optional[np.ndarray] = None
        self._processed_y: Optional[np.ndarray] = None
        self._processing_recipe: List[Dict[str, Any]] = []

    @property
    def raw_x(self) -> np.ndarray:
        """只读原始 x 轴数据。"""

        return self._raw_x

    @property
    def raw_y(self) -> np.ndarray:
        """只读原始 y 轴数据。"""

        return self._raw_y

    @property
    def processed_x(self) -> Optional[np.ndarray]:
        """处理后的 x 轴数据；尚未处理时为 ``None``。"""

        return self._processed_x

    @property
    def processed_y(self) -> Optional[np.ndarray]:
        """处理后的 y 轴数据；尚未处理时为 ``None``。"""

        return self._processed_y

    @property
    def metadata(self) -> Dict[str, Any]:
        """光谱元数据副本。"""

        return deepcopy(self._metadata)

    @property
    def processing_recipe(self) -> List[Dict[str, Any]]:
        """数据处理步骤列表副本。"""

        return deepcopy(self._processing_recipe)

    def copy_with_processed(
        self,
        x: np.ndarray,
        y: np.ndarray,
        recipe: Union[Mapping[str, Any], Iterable[Mapping[str, Any]]],
    ) -> "Spectrum":
        """返回带有处理结果的新光谱对象。

        Args:
            x: 处理后的 x 轴数据。
            y: 处理后的 y 轴数据。
            recipe: 本次处理步骤，或多个处理步骤组成的可迭代对象。

        Returns:
            新的 :class:`Spectrum` 实例，保留原始数据和元数据，并追加处理配方。

        Raises:
            ValueError: 当处理后 x 和 y 数组长度不一致时抛出。
        """

        processed_x = self._as_read_only_array("processed_x", x)
        processed_y = self._as_read_only_array("processed_y", y)

        if processed_x.shape != processed_y.shape:
            raise ValueError(
                "processed_x and processed_y must have the same shape"
            )

        spectrum = Spectrum(
            technique=self.technique,
            x=self.raw_x,
            y=self.raw_y,
            x_unit=self.x_unit,
            y_unit=self.y_unit,
            metadata=self._metadata,
            file_hash=self.file_hash,
        )
        spectrum._processed_x = processed_x
        spectrum._processed_y = processed_y
        spectrum._processing_recipe = [
            *deepcopy(self._processing_recipe),
            *self._normalize_recipe(recipe),
        ]
        return spectrum

    def __repr__(self) -> str:
        """返回便于调试的对象表示。"""

        file_hash = (
            f"{self.file_hash[:12]}..." if self.file_hash is not None else None
        )
        return (
            f"{self.__class__.__name__}("
            f"technique={self.technique.value!r}, "
            f"points={self.raw_x.size}, "
            f"processed={self.processed_x is not None}, "
            f"file_hash={file_hash!r})"
        )

    @classmethod
    def _as_read_only_array(cls, name: str, values: np.ndarray) -> np.ndarray:
        """将输入转换为只读一维浮点数组。"""

        array = np.asarray(values, dtype=float).copy()
        if array.ndim != 1:
            raise ValueError(f"{name} must be a one-dimensional array")
        array.setflags(write=False)
        return array

    @classmethod
    def _build_metadata(cls, metadata: Optional[dict]) -> Dict[str, Any]:
        """构建包含标准字段的元数据字典。"""

        result: Dict[str, Any] = {field: None for field in cls.METADATA_FIELDS}
        if metadata:
            result.update(deepcopy(metadata))
        return result

    @staticmethod
    def _normalize_recipe(
        recipe: Union[Mapping[str, Any], Iterable[Mapping[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """标准化处理步骤输入。"""

        if isinstance(recipe, Mapping):
            recipes = [recipe]
        else:
            recipes = list(recipe)

        normalized: List[Dict[str, Any]] = []
        for step in recipes:
            if not isinstance(step, Mapping):
                raise TypeError("recipe entries must be mappings")
            step_name = step.get("step")
            if not isinstance(step_name, str) or not step_name:
                raise ValueError("recipe entries must include a non-empty 'step'")

            params = step.get("params", {})
            if params is None:
                params = {}
            if not isinstance(params, Mapping):
                raise TypeError("recipe entry 'params' must be a mapping")

            normalized.append({"step": step_name, "params": deepcopy(dict(params))})
        return normalized

    def _validate_lengths(self) -> None:
        """校验原始数据数组长度。"""

        if self.raw_x.shape != self.raw_y.shape:
            raise ValueError("x and y must have the same shape")


__all__ = ["Spectrum", "SpectrumTechnique"]
