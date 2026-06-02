import base64
import gzip

import numpy as np

from echem_core.analysis.cv import calc_cdl, detect_scan_rate
from echem_core.io.chi_parser import parse_chi_file
from echem_core.io.corrtest_parser import parse_corrtest_file
from echem_core.model import Measurement, Technique


def _write_csstudio_file(tmp_path, exp_type, metadata_body, rows):
    metadata = f"CORRW ASCII\r\n{exp_type}\r\n{metadata_body}\r\n"
    blob = base64.b64encode(gzip.compress(metadata.encode("utf-8"))).decode("ascii")
    data = "\n".join("\t".join(str(value) for value in row) for row in rows)
    path = tmp_path / f"{exp_type}.txt"
    path.write_text(
        f"CSStudioFile,{exp_type},{blob}\nE(V)\ti(A/cm2)\tT(s)\n{data}\n",
        encoding="utf-8-sig",
    )
    return path


def test_chi_parser_delegates_csstudio_and_extracts_scan_rate(tmp_path):
    path = _write_csstudio_file(
        tmp_path,
        "ID_CV",
        "ExpParmas:ExpType=ID_CV&-&ScanRate=20&-&FileName=ECSA-20.txt\r\n"
        "Scan Rate(mV/s):20,Cycles:10",
        [
            (0.00, -1.0e-4, 0.0),
            (0.05, -0.8e-4, 2.5),
            (0.10, -0.7e-4, 5.0),
            (0.05, -0.9e-4, 7.5),
            (0.00, -1.1e-4, 10.0),
        ],
    )

    measurement = parse_chi_file(str(path))

    assert measurement.technique == Technique.CV
    assert measurement.metadata["scan_rate"] == 0.02
    assert measurement.metadata["scan_rate_mV_s"] == 20
    assert measurement.metadata["_source_format"] == "CorrTest CSStudio"


def test_corrtest_potential_step_is_chronoamperometry(tmp_path):
    path = _write_csstudio_file(
        tmp_path,
        "ID_PotSquareWave",
        "ExpParmas:ExpType=ID_PotSquareWave&-&Initial_E=0.617&-&Time1=180\r\n"
        "Potential:vs Ref.",
        [
            (0.617, 4.7e-2, 0.0),
            (0.617, 4.5e-2, 1.0),
            (0.617, 4.2e-2, 2.0),
            (0.400, 3.5e-2, 3.0),
            (0.400, 3.2e-2, 4.0),
        ],
    )

    assert parse_corrtest_file(str(path)).technique == Technique.CA
    assert parse_chi_file(str(path)).technique == Technique.CA


def test_corrtest_galstatic_is_chronopotentiometry(tmp_path):
    path = _write_csstudio_file(
        tmp_path,
        "ID_GalStatic",
        "ExpParmas:ExpType=ID_GalStatic&-&FileName=恒电流1A.txt\r\n"
        "Current:1 A",
        [
            (1.49420, 0.500231, 0.0),
            (1.47263, 0.500273, 1.0),
            (1.48916, 0.500249, 2.0),
            (1.49509, 0.500252, 3.0),
            (1.50354, 0.500252, 4.0),
            (1.51313, 0.500254, 5.0),
        ],
    )

    assert parse_corrtest_file(str(path)).technique == Technique.CP
    assert parse_chi_file(str(path)).technique == Technique.CP


def test_chi_constant_current_time_series_is_chronopotentiometry(tmp_path):
    path = tmp_path / "galvanostatic.txt"
    path.write_text(
        "Galvanostatic constant current test\n"
        "Potential/V, Current/A, Time/sec\n"
        "1.49420, 0.500231, 0.0\n"
        "1.47263, 0.500273, 1.0\n"
        "1.48916, 0.500249, 2.0\n"
        "1.49509, 0.500252, 3.0\n",
        encoding="utf-8",
    )

    assert parse_chi_file(str(path)).technique == Technique.CP


def test_chi_eis_with_ac_impedance_header_is_detected(tmp_path):
    path = tmp_path / "chi_eis.txt"
    path.write_text(
        "Dec. 9, 2025   01:15:24\r\n"
        "A.C. Impedance\r\n"
        "Instrument Model:  CHI660E\r\n"
        "Quiet Time (sec) = 2\r\n"
        "\r\n"
        "Freq/Hz, Z'/ohm, Z\"/ohm, Z/ohm, Phase/deg\r\n"
        "9.995e+3, 5.589e-2, -1.640e-1, 1.733e-1, -71.2\r\n"
        "1.000e+0, 6.266e-2, -3.834e-3, 6.278e-2, -3.5\r\n",
        encoding="utf-8",
    )

    measurement = parse_chi_file(str(path))

    assert measurement.technique == Technique.EIS
    assert measurement.raw_potential[0] == 9995.0
    assert measurement.raw_current[0] == 0.05589
    assert measurement.raw_time[0] == -0.164
    assert measurement.metadata["frequency"][0] == 9995.0
    assert measurement.metadata["date"].startswith("Dec. 9, 2025")


def test_corrtest_parser_accepts_comma_separated_eis_headers(tmp_path):
    path = tmp_path / "comma_eis.txt"
    path.write_text(
        "A.C. Impedance\n"
        "Freq/Hz, Z'/ohm, Z\"/ohm, Z/ohm, Phase/deg\n"
        "1000, 1.5, -0.2, 1.513, -7.6\n"
        "10, 2.0, -0.4, 2.04, -11.3\n",
        encoding="utf-8",
    )

    measurement = parse_corrtest_file(str(path))

    assert measurement.technique == Technique.EIS
    assert measurement.raw_potential.tolist() == [1000.0, 10.0]
    assert measurement.raw_current.tolist() == [1.5, 2.0]
    assert measurement.raw_time.tolist() == [-0.2, -0.4]


def _cv_for_scan_rate(scan_rate):
    forward_potential = np.linspace(0.0, 1.0, 51)
    reverse_potential = np.linspace(1.0, 0.0, 51)[1:]
    potential = np.concatenate([forward_potential, reverse_potential])
    time = np.concatenate([
        np.linspace(0.0, 1.0 / scan_rate, 51),
        np.linspace(1.0 / scan_rate + 1.0 / (scan_rate * 50), 2.0 / scan_rate, 50),
    ])
    current = np.concatenate([
        np.full(forward_potential.size, scan_rate * 2.0e-3),
        np.full(reverse_potential.size, -scan_rate * 2.0e-3),
    ])
    return Measurement(
        technique=Technique.CV,
        potential=potential,
        current=current,
        time=time,
        metadata={"sample_name": f"cv-{scan_rate:g}.txt"},
    )


def test_cdl_detects_and_sorts_scan_rates_from_cv_time_axis():
    measurements = [_cv_for_scan_rate(0.03), _cv_for_scan_rate(0.01), _cv_for_scan_rate(0.02)]

    assert np.isclose(detect_scan_rate(measurements[0]), 0.03)

    _cdl, _r2, _df_dv, scan_rates = calc_cdl(measurements)

    assert np.allclose(scan_rates, [0.01, 0.02, 0.03])
