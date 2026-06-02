import base64
import gzip

from echem_core.io.chi_parser import parse_chi_file
from echem_core.io.corrtest_parser import parse_corrtest_file
from echem_core.model import Technique


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
