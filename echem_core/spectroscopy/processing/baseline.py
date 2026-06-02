"""
光谱基线校正函数模块。

提供多种常用的基线校正算法，包括：
- 多项式基线拟合 (polynomial_baseline)
- 非对称最小二乘 (als_baseline)
- 自适应重加权惩罚最小二乘 (arpls_baseline)
- 橡皮筋基线校正 (rubberband_baseline)
"""

from typing import Tuple

import numpy as np
from numpy.polynomial import polynomial as Poly
from scipy import sparse
from scipy.sparse.linalg import spsolve
from scipy.spatial import ConvexHull


def polynomial_baseline(
    x: np.ndarray,
    y: np.ndarray,
    poly_order: int = 3,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    多项式基线拟合校正。

    使用指定阶数的多项式对光谱数据进行拟合，将拟合结果作为基线，
    从原始数据中减去基线得到校正后的光谱。

    Parameters
    ----------
    x : np.ndarray
        一维数组，表示光谱的横坐标（如波数、波长等）。
    y : np.ndarray
        一维数组，表示光谱的纵坐标（如吸光度、强度等）。
    poly_order : int, optional
        多项式阶数，默认为 3。

    Returns
    -------
    baseline : np.ndarray
        拟合得到的基线值，形状与 y 相同。
    corrected_y : np.ndarray
        基线校正后的光谱数据 (y - baseline)。

    Examples
    --------
    >>> import numpy as np
    >>> x = np.linspace(0, 10, 100)
    >>> y = np.sin(x) + 0.01 * x**2
    >>> baseline, corrected = polynomial_baseline(x, y, poly_order=2)
    """
    coeffs = Poly.polyfit(x, y, deg=poly_order)
    baseline = Poly.polyval(x, coeffs)
    corrected_y = y - baseline
    return baseline, corrected_y


def als_baseline(
    y: np.ndarray,
    lam: float = 1e5,
    p: float = 0.01,
    max_iter: int = 10,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    非对称最小二乘 (Asymmetric Least Squares, ALS) 基线校正。

    实现 Eilers & Boelens (2005) 提出的 ALS 算法，通过迭代加权惩罚
    最小二乘法，对光谱数据的基线进行估计。对信号的峰区域赋予较小的
    权重，对基线区域赋予较大的权重，从而自适应地提取基线。

    Parameters
    ----------
    y : np.ndarray
        一维数组，表示光谱的纵坐标（如吸光度、强度等）。
    lam : float, optional
        平滑参数（惩罚项权重），值越大基线越平滑。推荐范围 1e2 ~ 1e9，
        默认为 1e5。
    p : float, optional
        非对称权重参数，取值范围 (0, 1)。p 越接近 0，对正残差（峰区域）
        的惩罚越轻，基线越贴近信号底部。默认为 0.01。
    max_iter : int, optional
        最大迭代次数，默认为 10。

    Returns
    -------
    baseline : np.ndarray
        估计得到的基线值，形状与 y 相同。
    corrected_y : np.ndarray
        基线校正后的光谱数据 (y - baseline)。

    References
    ----------
    Eilers, P. H. C., & Boelens, H. F. M. (2005). Baseline correction
    with asymmetric least squares smoothing. Leiden University Medical
    Centre Report, 1(1), 5.

    Examples
    --------
    >>> import numpy as np
    >>> y = np.array([1.0, 2.0, 3.0, 10.0, 3.0, 2.0, 1.0])
    >>> baseline, corrected = als_baseline(y, lam=1e5, p=0.01)
    """
    L = len(y)
    # 构建二阶差分矩阵 D
    D = sparse.diags(
        [1, -2, 1], [0, 1, 2], shape=(L - 2, L), format="csc", dtype=np.float64
    )
    w = np.ones(L, dtype=np.float64)

    for _ in range(max_iter):
        W = sparse.diags(w, 0, shape=(L, L), format="csc", dtype=np.float64)
        Z = W + lam * (D.T @ D)
        baseline = spsolve(Z, w * y)
        # 更新权重：正残差（峰区域）赋予权重 p，负残差（基线下方）赋予权重 1-p
        residual = y - baseline
        w_new = np.where(residual > 0, p, 1.0 - p)
        # 检查收敛（权重变化很小则停止）
        if np.linalg.norm(w_new - w) / np.linalg.norm(w) < 1e-6:
            w = w_new
            break
        w = w_new

    corrected_y = y - baseline
    return baseline, corrected_y


def arpls_baseline(
    y: np.ndarray,
    lam: float = 1e5,
    max_iter: int = 50,
    tol: float = 1e-6,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    自适应重加权惩罚最小二乘 (Adaptively Reweighted Penalized Least Squares, arPLS) 基线校正。

    实现 Zhang 等人 (2010) 提出的 arPLS 算法，是 ALS 的改进版本。
    与 ALS 使用固定的非对称权重不同，arPLS 根据残差的正态分布统计特性
    自适应地更新权重，不需要手动设定 p 参数。

    Parameters
    ----------
    y : np.ndarray
        一维数组，表示光谱的纵坐标（如吸光度、强度等）。
    lam : float, optional
        平滑参数（惩罚项权重），值越大基线越平滑。推荐范围 1e2 ~ 1e9，
        默认为 1e5。
    max_iter : int, optional
        最大迭代次数，默认为 50。
    tol : float, optional
        收敛容差，当权重变化相对范数小于该值时停止迭代，默认为 1e-6。

    Returns
    -------
    baseline : np.ndarray
        估计得到的基线值，形状与 y 相同。
    corrected_y : np.ndarray
        基线校正后的光谱数据 (y - baseline)。

    References
    ----------
    Zhang, Z. M., Chen, S., & Liang, Y. Z. (2010). Baseline correction
    using adaptive iteratively reweighted penalized least squares.
    Analyst, 135(5), 1138-1146.

    Examples
    --------
    >>> import numpy as np
    >>> y = np.array([1.0, 2.0, 3.0, 10.0, 3.0, 2.0, 1.0])
    >>> baseline, corrected = arpls_baseline(y, lam=1e5)
    """
    L = len(y)
    D = sparse.diags(
        [1, -2, 1], [0, 1, 2], shape=(L - 2, L), format="csc", dtype=np.float64
    )
    w = np.ones(L, dtype=np.float64)

    for _ in range(max_iter):
        W = sparse.diags(w, 0, shape=(L, L), format="csc", dtype=np.float64)
        Z = W + lam * (D.T @ D)
        baseline = spsolve(Z, w * y)
        residual = y - baseline

        # 仅对负残差（基线下方）部分进行统计建模
        neg_residual = residual[residual < 0]
        if len(neg_residual) == 0:
            break

        mean_neg = np.mean(neg_residual)
        std_neg = np.std(neg_residual, ddof=1)

        # 自适应权重更新（逻辑斯蒂函数形式）
        # 残差越大（越正，峰区域），权重越接近 0
        # 残差接近或小于均值，权重接近 1
        eta = -2.0 * (residual - mean_neg) / (std_neg + 1e-12)
        w_new = 1.0 / (1.0 + np.exp(eta))

        # 收敛检查
        if np.linalg.norm(w_new - w) / np.linalg.norm(w) < tol:
            w = w_new
            break
        w = w_new

    corrected_y = y - baseline
    return baseline, corrected_y


def rubberband_baseline(
    x: np.ndarray,
    y: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    橡皮筋（凸包）基线校正。

    通过计算光谱数据下凸包络（lower convex hull）来估计基线。
    该方法模拟在光谱下方拉一根"橡皮筋"，仅接触光谱的最低点，
    适用于基线随横坐标单调变化或弯曲的情况。

    算法步骤：
    1. 找到所有数据点的凸包（Convex Hull）。
    2. 从凸包顶点中筛选出下凸包络（从最左点到最右点沿逆时针方向）。
    3. 对下凸包络进行线性插值，得到完整的基线。
    4. 从原始数据中减去基线。

    Parameters
    ----------
    x : np.ndarray
        一维数组，表示光谱的横坐标（如波数、波长等）。需要单调递增。
    y : np.ndarray
        一维数组，表示光谱的纵坐标（如吸光度、强度等）。

    Returns
    -------
    baseline : np.ndarray
        插值得到的凸包基线值，形状与 y 相同。
    corrected_y : np.ndarray
        基线校正后的光谱数据 (y - baseline)。

    Raises
    ------
    ValueError
        当 x 或 y 的长度小于 3 时，无法计算凸包。

    Examples
    --------
    >>> import numpy as np
    >>> x = np.linspace(0, 10, 100)
    >>> y = np.sin(x) + 0.5 * np.exp(-x)
    >>> baseline, corrected = rubberband_baseline(x, y)
    """
    if len(x) < 3 or len(y) < 3:
        raise ValueError("数据点数量必须大于等于 3 才能计算凸包。")

    # 构建点集并计算凸包
    points = np.column_stack((x, y))
    hull = ConvexHull(points)
    hull_vertices = hull.vertices  # 凸包顶点索引

    # 按横坐标排序顶点
    sorted_idx = hull_vertices[np.argsort(x[hull_vertices])]

    # 找到最左和最右的顶点索引（在凸包顶点集合中）
    x_min = np.min(x)
    x_max = np.max(x)

    # 筛选从最左点到最右点的下半部分凸包顶点
    left_idx = np.argmin(x[sorted_idx])
    right_idx = np.argmax(x[sorted_idx])

    if left_idx < right_idx:
        lower_vertices = sorted_idx[left_idx : right_idx + 1]
    else:
        lower_vertices = np.concatenate(
            [sorted_idx[left_idx:], sorted_idx[: right_idx + 1]]
        )

    # 确保至少有两个顶点用于插值
    lower_vertices = np.unique(lower_vertices)
    if len(lower_vertices) < 2:
        # 如果下半部分顶点不足，直接返回原始数据
        baseline = np.zeros_like(y)
        corrected_y = y.copy()
        return baseline, corrected_y

    # 提取下凸包顶点坐标
    hull_x = x[lower_vertices]
    hull_y = y[lower_vertices]

    # 按横坐标排序（保证插值单调）
    sort_order = np.argsort(hull_x)
    hull_x = hull_x[sort_order]
    hull_y = hull_y[sort_order]

    # 线性插值得到连续基线
    baseline = np.interp(x, hull_x, hull_y)
    corrected_y = y - baseline

    return baseline, corrected_y


__all__ = [
    "polynomial_baseline",
    "als_baseline",
    "arpls_baseline",
    "rubberband_baseline",
]
