import os
import re
from pathlib import Path

# Extensões permitidas para upload. Ajuste conforme necessidade do negócio.
ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".png", ".jpg", ".jpeg", ".gif", ".dwg", ".dxf",
    ".zip", ".rar", ".7z",
}


def slugify(s: str) -> str:
    """Remove chars inválidos para nome de pasta (Windows-safe). Mantém espaços."""
    s = re.sub(r'[<>:"/\\|?*\n\r\t]', '', s.strip())
    return s[:80]


def safe_filename(name: str) -> str:
    """Sanitiza nome de arquivo: remove path (anti-traversal) e chars inválidos."""
    # descarta qualquer componente de diretório (../, C:\, etc.)
    name = os.path.basename(name.replace("\\", "/"))
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", name).strip().strip(".")
    return name[:200] or "arquivo"


def extension_allowed(name: str) -> bool:
    return Path(name).suffix.lower() in ALLOWED_EXTENSIONS


def unique_path(directory: Path, filename: str) -> Path:
    """Evita sobrescrever: se existir, acrescenta ' (1)', ' (2)'..."""
    candidate = directory / filename
    if not candidate.exists():
        return candidate
    stem, suffix = Path(filename).stem, Path(filename).suffix
    i = 1
    while True:
        candidate = directory / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


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
