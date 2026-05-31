"""电化学测量数据模型。"""

from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

import numpy as np


class Technique(str, Enum):
    """电化学测试技术枚举。"""

    LSV = "LSV"
    CV = "CV"
    CA = "CA"
    CP = "CP"
    EIS = "EIS"


class Measurement:
    """表示一次电化学测量及其处理结果。

    原始电位、电流和时间数组在实例创建后不可写；处理后的数据通过
    :meth:`copy_with_processed` 生成新实例保存，避免原始数据被意外修改。
    """

    METADATA_FIELDS: Sequence[str] = (
        "sample_name",
        "date",
        "instrument",
        "reference_electrode",
        "electrolyte",
        "pH",
        "rotation_rpm",
        "scan_rate",
        "area_cm2",
        "loading_mg_cm2",
        "temperature",
    )

    def __init__(
        self,
        technique: Technique,
        potential: np.ndarray,
        current: np.ndarray,
        time: Optional[np.ndarray] = None,
        metadata: Optional[dict] = None,
        file_hash: Optional[str] = None,
    ) -> None:
        """初始化测量对象。

        Args:
            technique: 电化学测试技术。
            potential: 原始电位数组。
            current: 原始电流数组。
            time: 原始时间数组；没有时间轴时为 ``None``。
            metadata: 测量元数据，缺失的标准字段会以 ``None`` 补齐。
            file_hash: 原始文件的 SHA-256 哈希值。

        Raises:
            ValueError: 当数组维度不是一维，或长度不一致时抛出。
        """

        self.technique = Technique(technique)
        self._raw_potential = self._as_read_only_array("potential", potential)
        self._raw_current = self._as_read_only_array("current", current)
        self._raw_time = (
            self._as_read_only_array("time", time) if time is not None else None
        )

        self._validate_lengths()

        self.file_hash = file_hash
        self._metadata = self._build_metadata(metadata)
        self._processed_potential: Optional[np.ndarray] = None
        self._processed_current: Optional[np.ndarray] = None
        self._processing_recipe: List[Dict[str, Any]] = []

    @property
    def raw_potential(self) -> np.ndarray:
        """只读原始电位数组。"""

        return self._raw_potential

    @property
    def raw_current(self) -> np.ndarray:
        """只读原始电流数组。"""

        return self._raw_current

    @property
    def raw_time(self) -> Optional[np.ndarray]:
        """只读原始时间数组；未提供时为 ``None``。"""

        return self._raw_time

    @property
    def processed_potential(self) -> Optional[np.ndarray]:
        """处理后的电位数组；尚未处理时为 ``None``。"""

        return self._processed_potential

    @property
    def processed_current(self) -> Optional[np.ndarray]:
        """处理后的电流数组；尚未处理时为 ``None``。"""

        return self._processed_current

    @property
    def metadata(self) -> Dict[str, Any]:
        """测量元数据副本。"""

        return deepcopy(self._metadata)

    @property
    def processing_recipe(self) -> List[Dict[str, Any]]:
        """数据处理步骤列表副本。"""

        return deepcopy(self._processing_recipe)

    def copy_with_processed(
        self,
        potential: np.ndarray,
        current: np.ndarray,
        recipe: Union[Mapping[str, Any], Iterable[Mapping[str, Any]]],
    ) -> "Measurement":
        """返回带有处理结果的新测量对象。

        Args:
            potential: 处理后的电位数组。
            current: 处理后的电流数组。
            recipe: 本次处理步骤，或多个处理步骤组成的可迭代对象。

        Returns:
            新的 :class:`Measurement` 实例，保留原始数据和元数据，并追加处理配方。

        Raises:
            ValueError: 当处理后电位和电流数组长度不一致时抛出。
        """

        processed_potential = self._as_read_only_array("processed_potential", potential)
        processed_current = self._as_read_only_array("processed_current", current)

        if processed_potential.shape != processed_current.shape:
            raise ValueError(
                "processed_potential and processed_current must have the same shape"
            )

        measurement = Measurement(
            technique=self.technique,
            potential=self.raw_potential,
            current=self.raw_current,
            time=self.raw_time,
            metadata=self._metadata,
            file_hash=self.file_hash,
        )
        measurement._processed_potential = processed_potential
        measurement._processed_current = processed_current
        measurement._processing_recipe = [
            *deepcopy(self._processing_recipe),
            *self._normalize_recipe(recipe),
        ]
        return measurement

    def __repr__(self) -> str:
        """返回便于调试的对象表示。"""

        file_hash = (
            f"{self.file_hash[:12]}..." if self.file_hash is not None else None
        )
        return (
            f"{self.__class__.__name__}("
            f"technique={self.technique.value!r}, "
            f"points={self.raw_potential.size}, "
            f"processed={self.processed_potential is not None}, "
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

        if self.raw_potential.shape != self.raw_current.shape:
            raise ValueError("potential and current must have the same shape")
        if (
            self.raw_time is not None
            and self.raw_time.shape != self.raw_potential.shape
        ):
            raise ValueError("time must have the same shape as potential and current")


__all__ = ["Measurement", "Technique"]
