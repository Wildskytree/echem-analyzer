"""样品数据模型，管理电化学与光谱测量的统一容器。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional, Union

from echem_core.model.measurement import Measurement
from echem_core.spectroscopy.model.spectrum import Spectrum


class Sample:
    """表示一个样品的所有测量数据。

    汇集同一样品的电化学测量（如 CV、LSV、EIS）和光谱测量
    （如 Raman、XPS、FTIR），并提供摘要指标与合成参数的存储。

    Args:
        sample_id: 样品唯一标识符。
        electrochem: 电化学测量字典，键为测试技术名称，值为
            :class:`~echem_core.model.measurement.Measurement` 对象。
        spectroscopy: 光谱测量字典，键为光谱名称，值为
            :class:`~echem_core.spectroscopy.model.spectrum.Spectrum` 对象。
        summary: 样品摘要指标字典，如 ``{"E1/2": -0.15, "Tafel": 72.3,
            "ID/IG": 1.24}``。
        metadata: 样品元数据字典，如合成参数（前驱体、温度、时间等）。
    """

    def __init__(
        self,
        sample_id: str,
        electrochem: Optional[Dict[str, Measurement]] = None,
        spectroscopy: Optional[Dict[str, Spectrum]] = None,
        summary: Optional[Dict[str, Union[float, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.sample_id = sample_id
        self.electrochem: Dict[str, Measurement] = electrochem or {}
        self.spectroscopy: Dict[str, Spectrum] = spectroscopy or {}
        self.summary: Dict[str, Union[float, str]] = summary or {}
        self.metadata: Dict[str, Any] = metadata or {}

    def add_echem(self, name: str, measurement: Measurement) -> None:
        """添加一条电化学测量到样品。

        Args:
            name: 该测量在样品中的标识键（如 ``"CV_1"``、``"LSV_1"``）。
            measurement: :class:`~echem_core.model.measurement.Measurement`
                实例。

        Raises:
            TypeError: 当 *measurement* 不是 ``Measurement`` 对象时抛出。
        """
        if not isinstance(measurement, Measurement):
            raise TypeError(
                f"expected Measurement object, got {type(measurement).__name__}"
            )
        self.electrochem[name] = measurement

    def add_spectrum(self, name: str, spectrum: Spectrum) -> None:
        """添加一条光谱测量到样品。

        Args:
            name: 该光谱在样品中的标识键（如 ``"Raman_532"``、``"XPS_C1s"``）。
            spectrum: :class:`~echem_core.spectroscopy.model.spectrum.Spectrum`
                实例。

        Raises:
            TypeError: 当 *spectrum* 不是 ``Spectrum`` 对象时抛出。
        """
        if not isinstance(spectrum, Spectrum):
            raise TypeError(
                f"expected Spectrum object, got {type(spectrum).__name__}"
            )
        self.spectroscopy[name] = spectrum

    def to_dict(self) -> Dict[str, Any]:
        """将样品序列化为字典（深度拷贝，安全导出）。

        电化学和光谱对象会被转换为各自对应的字典表示。
        ``Measurement`` 和 ``Spectrum`` 中可能包含的 NumPy 数组会以
        列表形式导出。

        Returns:
            包含样品全部数据的字典。
        """
        return deepcopy(
            {
                "sample_id": self.sample_id,
                "electrochem": {
                    name: {
                        "technique": meas.technique.value,
                        "potential": meas.raw_potential.tolist(),
                        "current": meas.raw_current.tolist(),
                        "time": meas.raw_time.tolist() if meas.raw_time is not None else None,
                        "metadata": meas.metadata,
                        "file_hash": meas.file_hash,
                    }
                    for name, meas in self.electrochem.items()
                },
                "spectroscopy": {
                    name: {
                        "technique": spec.technique.value,
                        "x": spec.raw_x.tolist(),
                        "y": spec.raw_y.tolist(),
                        "x_unit": spec.x_unit,
                        "y_unit": spec.y_unit,
                        "metadata": spec.metadata,
                        "file_hash": spec.file_hash,
                    }
                    for name, spec in self.spectroscopy.items()
                },
                "summary": self.summary,
                "metadata": self.metadata,
            }
        )

    def __repr__(self) -> str:
        """返回便于调试的样品表示。"""
        return (
            f"{self.__class__.__name__}("
            f"sample_id={self.sample_id!r}, "
            f"electrochem={len(self.electrochem)} measurements, "
            f"spectroscopy={len(self.spectroscopy)} spectra, "
            f"summary_keys={list(self.summary.keys())})"
        )


__all__ = ["Sample"]
