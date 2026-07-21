import pytest

from utils import (
    ensure_within,
    extension_allowed,
    safe_filename,
    slugify,
    unique_path,
)


class TestSlugify:
    def test_remove_chars_invalidos_e_mantem_espacos(self):
        assert slugify('Proj: "A"/B') == "Proj AB"

    @pytest.mark.parametrize("entrada", ["..", ".", "...", "  ..  ", ""])
    def test_nunca_devolve_componente_que_escapa_do_diretorio(self, entrada):
        """'..' como nome de documento escreveria fora de UPLOAD_DIR."""
        assert slugify(entrada) not in ("", ".", "..")

    @pytest.mark.parametrize("reservado", ["CON", "nul", "COM1", "LPT9"])
    def test_nomes_reservados_do_windows(self, reservado):
        assert slugify(reservado) == "_"

    def test_trunca_em_80(self):
        assert len(slugify("x" * 200)) == 80


class TestSafeFilename:
    @pytest.mark.parametrize("entrada", [
        "../../etc/passwd",
        r"..\..\windows\system32\config",
        "C:/Windows/notepad.exe",
    ])
    def test_descarta_componentes_de_diretorio(self, entrada):
        resultado = safe_filename(entrada)
        assert "/" not in resultado and "\\" not in resultado
        assert not resultado.startswith(".")

    def test_preserva_extensao(self):
        assert safe_filename("relatório final.pdf") == "relatório final.pdf"

    def test_nome_vazio_vira_fallback(self):
        assert safe_filename("") == "arquivo"
        assert safe_filename("...") == "arquivo"


class TestExtensionAllowed:
    @pytest.mark.parametrize("nome,esperado", [
        ("a.pdf", True), ("a.PDF", True), ("a.docx", True),
        ("a.exe", False), ("a.sh", False), ("semextensao", False),
        ("a.pdf.exe", False),
    ])
    def test_lista_branca(self, nome, esperado):
        assert extension_allowed(nome) is esperado


class TestUniquePath:
    def test_reserva_caminhos_distintos_para_o_mesmo_nome(self, tmp_path):
        """Dois arquivos de mesmo nome no mesmo envio não podem colidir."""
        a = unique_path(tmp_path, "doc.pdf")
        b = unique_path(tmp_path, "doc.pdf")
        c = unique_path(tmp_path, "doc.pdf")
        assert {a.name, b.name, c.name} == {"doc.pdf", "doc (1).pdf", "doc (2).pdf"}
        assert all(p.exists() for p in (a, b, c))


class TestEnsureWithin:
    def test_aceita_caminho_interno(self, tmp_path):
        alvo = tmp_path / "a" / "b"
        assert ensure_within(tmp_path, alvo) == alvo.resolve()

    def test_rejeita_escape(self, tmp_path):
        with pytest.raises(ValueError):
            ensure_within(tmp_path / "base", tmp_path / "base" / ".." / ".." / "fora")
