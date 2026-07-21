import os
import re
from pathlib import Path

# Extensões permitidas para upload. Ajuste conforme necessidade do negócio.
ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".png", ".jpg", ".jpeg", ".gif", ".dwg", ".dxf",
    ".zip", ".rar", ".7z",
}

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Nomes reservados no Windows — um diretório com esses nomes é inutilizável.
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def _sanitize_component(s: str, fallback: str, maxlen: int) -> str:
    """Base comum de slugify/safe_filename: remove chars inválidos e nomes perigosos."""
    s = _INVALID_CHARS.sub("", s).strip()
    # '.' e '..' escapariam da árvore de uploads; pontos finais quebram no Windows.
    s = s.rstrip(". ")
    if not s or set(s) == {"."} or s.upper() in _RESERVED_NAMES:
        return fallback
    return s[:maxlen].rstrip(". ") or fallback


def slugify(s: str) -> str:
    """Sanitiza um componente de caminho (nome de pasta). Mantém espaços.

    Garante que o resultado nunca seja '', '.', '..' ou nome reservado do
    Windows — qualquer um deles permitiria escrever fora de UPLOAD_DIR.
    """
    return _sanitize_component(s, fallback="_", maxlen=80)


def safe_filename(name: str) -> str:
    """Sanitiza nome de arquivo: remove path (anti-traversal) e chars inválidos."""
    # descarta qualquer componente de diretório (../, C:\, etc.)
    name = os.path.basename(name.replace("\\", "/"))
    name = _INVALID_CHARS.sub("_", name).strip()
    stem, dot, suffix = name.rpartition(".")
    # Só trata como extensão se sobrar nome e sufixo de verdade ("..." não conta).
    if dot and stem.strip(". ") and suffix.strip():
        stem = _sanitize_component(stem, fallback="arquivo", maxlen=180)
        return f"{stem}.{suffix[:20]}"
    return _sanitize_component(name, fallback="arquivo", maxlen=200)


def extension_allowed(name: str) -> bool:
    return Path(name).suffix.lower() in ALLOWED_EXTENSIONS


def unique_path(directory: Path, filename: str) -> Path:
    """Reserva um caminho livre no diretório, criando o arquivo vazio (atômico).

    Cria o arquivo com O_EXCL para que duas chamadas concorrentes nunca
    devolvam o mesmo caminho. Se existir, acrescenta ' (1)', ' (2)'...
    """
    stem, suffix = Path(filename).stem, Path(filename).suffix
    i = 0
    while True:
        candidate = directory / (filename if i == 0 else f"{stem} ({i}){suffix}")
        try:
            fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            i += 1
            continue
        os.close(fd)
        return candidate


def ensure_within(base: Path, target: Path) -> Path:
    """Valida que `target` está dentro de `base`. Levanta ValueError se escapar."""
    base_r, target_r = base.resolve(), target.resolve()
    if base_r != target_r and base_r not in target_r.parents:
        raise ValueError(f"caminho fora do diretório permitido: {target}")
    return target_r


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
        / f"Rev {slugify(rev_label)}"
    )
    ensure_within(upload_dir, path)
    path.mkdir(parents=True, exist_ok=True)
    return path
