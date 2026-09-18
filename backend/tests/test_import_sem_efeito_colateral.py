# O que é: teste do passo 5 da V1 — `scripts/checar_import.py` importa o pacote inteiro sem I/O.
# Quando ler: quando este teste quebrar — algum módulo passou a fazer rede/banco/env em import.
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "checar_import.py"


def test_script_de_import_passa(tmp_path: Path) -> None:
    resultado = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=tmp_path,
        env={"PATH": os.environ.get("PATH", "")},
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    assert "importados:" in resultado.stdout
