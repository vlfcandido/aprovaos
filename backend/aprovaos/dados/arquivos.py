"""Armazenamento em disco dos PDFs subidos, endereçados pelo SHA-256 do conteúdo.

O que é: `guardar_pdf(uploads_dir, hash, conteudo)`. Quando ler: ao mexer em onde e como o
edital subido fica guardado; a pasta só é criada aqui, na hora de gravar (nada em import).
"""

from pathlib import Path


def guardar_pdf(uploads_dir: Path, hash: str, conteudo: bytes) -> Path:
    """Grava `conteudo` em `uploads_dir/<hash>.pdf`, criando a pasta se preciso.

    Idempotente: se o arquivo já existe (mesmo hash = mesmo conteúdo), não reescreve — subir o
    mesmo PDF duas vezes reaproveita o arquivo (Q3 do plano V2).

    Args:
        uploads_dir: pasta dos uploads (`app.state.uploads_dir`).
        hash: SHA-256 hexadecimal do conteúdo (64 caracteres).
        conteudo: bytes do PDF já validado.

    Returns:
        O caminho absoluto do arquivo gravado (ou já existente).
    """
    uploads_dir.mkdir(parents=True, exist_ok=True)
    caminho = uploads_dir / f"{hash}.pdf"
    if not caminho.exists():
        caminho.write_bytes(conteudo)
    return caminho
