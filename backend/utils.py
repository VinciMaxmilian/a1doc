import re
from pathlib import Path


def slugify(s: str) -> str:
    """Remove chars inválidos para nome de pasta (Windows-safe). Mantém espaços."""
    s = re.sub(r'[<>:"/\\|?*\n\r\t]', '', s.strip())
    return s[:80]


def doc_rev_dir(upload_dir: Path, amb: str, area: str, proj: str, doc_nome: str, rev_label: str) -> Path:
    """
    Retorna (e cria) o diretório da revisão de um documento:
    {upload_dir}/{Ambiente}/{Area}/{Projeto}/{Documento}/Rev {N}/
    """
    path = (
        upload_dir
        / slugify(amb)
        / slugify(area)
        / slugify(proj)
        / slugify(doc_nome)
        / f"Rev {rev_label}"
    )
    path.mkdir(parents=True, exist_ok=True)
    return path
