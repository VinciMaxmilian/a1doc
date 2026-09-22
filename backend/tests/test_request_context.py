"""Correlação de requisições (Etapa 0 / pré-requisito da FASE 3 — auditoria)."""
import logging

from indoc.core.logging import JsonFormatter, setup_logging
from indoc.core.middleware import HEADER, RequestIdFilter
from indoc.core.request_context import get_request_id, request_id_valido


def test_resposta_traz_request_id(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert request_id_valido(r.headers[HEADER])


def test_cada_requisicao_recebe_id_proprio(client):
    primeiro = client.get("/health").headers[HEADER]
    segundo = client.get("/health").headers[HEADER]
    assert primeiro != segundo


def test_id_do_cliente_e_reaproveitado(client):
    """Permite correlacionar com um proxy/gateway à frente da API."""
    r = client.get("/health", headers={HEADER: "trace-abc.123"})
    assert r.headers[HEADER] == "trace-abc.123"


def test_id_malformado_do_cliente_e_descartado(client):
    """Nunca ecoar valor arbitrário: seria injeção de header e lixo no log."""
    for hostil in ["x" * 65, "com espaco", "a\nb", "<script>", ""]:
        r = client.get("/health", headers={HEADER: hostil})
        devolvido = r.headers[HEADER]
        assert devolvido != hostil
        assert request_id_valido(devolvido)


def test_fora_de_requisicao_nao_ha_id():
    assert get_request_id() == "-"


def test_filtro_injeta_request_id_no_log():
    registro = logging.LogRecord("t", logging.INFO, __file__, 1, "msg", None, None)
    assert RequestIdFilter().filter(registro) is True
    assert registro.request_id == "-"


def test_formatter_json_serializa_o_evento():
    registro = logging.LogRecord("indoc.t", logging.WARNING, __file__, 7, "oi %s", ("mundo",), None)
    registro.request_id = "abc123"
    registro.documento_id = 42  # contexto extra vai para o JSON

    import json

    evento = json.loads(JsonFormatter().format(registro))
    assert evento["level"] == "WARNING"
    assert evento["logger"] == "indoc.t"
    assert evento["message"] == "oi mundo"
    assert evento["request_id"] == "abc123"
    assert evento["documento_id"] == 42


def test_setup_logging_e_idempotente():
    setup_logging(level="INFO", formato="text")
    setup_logging(level="INFO", formato="text")
    handler = logging.getLogger().handlers[0]
    assert sum(isinstance(f, RequestIdFilter) for f in handler.filters) == 1
