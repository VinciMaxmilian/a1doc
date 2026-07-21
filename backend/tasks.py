import logging
import os
import shutil
import uuid
from pathlib import Path

import config
import models
from celery_app import celery_app
from database import SessionLocal
from utils import doc_rev_dir, unique_path

logger = logging.getLogger("indoc.tasks")

# Ação usada quando um documento existente recebe novo upload.
# O reenvio equivale a submeter de novo para aprovação.
ACAO_REENVIO = "aprovado"


def _mover(origem: Path, destino: Path) -> None:
    """Move o arquivo temporário para o destino final.

    Ambos ficam sob UPLOAD_DIR (mesmo filesystem), então os.replace é um
    rename barato. shutil.move é o fallback para volumes distintos.
    """
    try:
        os.replace(origem, destino)
    except OSError:
        shutil.move(str(origem), str(destino))


def _atividade_inicial(db) -> int | None:
    """Primeira atividade do Fluxo 0 — o estado inicial de todo documento novo."""
    fluxo_zero = db.query(models.Fluxo).filter(models.Fluxo.numero == 0).first()
    if not fluxo_zero or not fluxo_zero.atividades:
        raise RuntimeError(
            "Fluxo inicial ausente: crie o Fluxo 0 com ao menos uma atividade "
            "antes de enviar documentos."
        )
    return fluxo_zero.atividades[0].id


def _destino_reenvio(db, origem_id: int) -> tuple[int, bool]:
    """Para onde vai um documento reenviado, a partir da atividade `origem_id`.

    Usa exclusivamente a transição configurada para ACAO_REENVIO. Se não
    houver, o documento permanece onde está — antes havia um fallback de
    "próxima atividade por ID" que dependia da ordem de criação no banco e
    quebrava se as atividades fossem recriadas.

    Retorna (atividade_destino_id, gera_nova_revisao).
    """
    trans = db.query(models.ConfigTransicao).filter(
        models.ConfigTransicao.atividade_origem_id == origem_id,
        models.ConfigTransicao.acao == ACAO_REENVIO,
    ).first()
    if not trans:
        logger.warning(
            "Sem transição '%s' configurada a partir da atividade %s; "
            "documento permanece na atividade atual.", ACAO_REENVIO, origem_id
        )
        return origem_id, False
    return trans.atividade_destino_id, bool(trans.gera_nova_revisao)


@celery_app.task(bind=True, name="processar_upload")
def processar_upload(self, job_id: str, metadata: dict, arquivos_tmp: list):
    db = SessionLocal()
    try:
        job = db.query(models.UploadJob).filter(models.UploadJob.id == job_id).first()
        if not job:
            logger.error("Job %s não encontrado", job_id)
            return
        job.status = "processando"
        db.commit()

        # ── Upsert: mesmo nome + projeto = mesmo documento ──
        doc = db.query(models.Documento).filter(
            models.Documento.nome == metadata["nome"],
            models.Documento.projeto_id == metadata["projeto_id"],
        ).first()

        if doc is None:
            ativ_id = _atividade_inicial(db)
            old_ativ_id = None
            doc = models.Documento(
                codigo=f"DOC-{uuid.uuid4().hex[:8].upper()}",
                nome=metadata["nome"],
                ambiente_id=metadata["ambiente_id"],
                area_id=metadata["area_id"],
                projeto_id=metadata["projeto_id"],
                tipo_documento_id=metadata["tipo_documento_id"],
                responsavel_id=metadata["responsavel_id"],
                atividade_atual_id=ativ_id,
                revisao_indice=0,
            )
            db.add(doc)
            db.flush()
            acao_historico = "upload_inicial"
        else:
            old_ativ_id = doc.atividade_atual_id
            ativ_id = old_ativ_id
            if old_ativ_id:
                ativ_id, nova_revisao = _destino_reenvio(db, old_ativ_id)
                if nova_revisao:
                    doc.revisao_indice += 1
                doc.atividade_atual_id = ativ_id
            acao_historico = "reenvio"

        # ── Nomes para montar o caminho hierárquico ──
        amb = db.query(models.Ambiente).filter(models.Ambiente.id == doc.ambiente_id).first()
        area = db.query(models.Area).filter(models.Area.id == doc.area_id).first()
        proj = db.query(models.Projeto).filter(models.Projeto.id == doc.projeto_id).first()
        if not (amb and area and proj):
            raise RuntimeError("Hierarquia do documento incompleta (ambiente/área/projeto)")

        file_dir = doc_rev_dir(
            config.UPLOAD_DIR,
            amb.nome, area.nome, proj.nome,
            doc.nome, str(doc.revisao_indice + 1),
        )

        for arq_info in arquivos_tmp:
            tmp_path = Path(arq_info["tmp_path"])
            if not tmp_path.is_file():
                logger.error("Arquivo temporário ausente: %s", tmp_path)
                continue
            final_path = unique_path(file_dir, arq_info["filename"])
            _mover(tmp_path, final_path)
            rel_path = str(final_path.relative_to(config.UPLOAD_DIR)).replace("\\", "/")

            db.add(models.DocumentoArquivo(
                documento_id=doc.id,
                arquivo_nome=final_path.name,
                arquivo_path=rel_path,
                revisao_indice=doc.revisao_indice,
                uploaded_by_id=metadata["responsavel_id"],
                atividade_id=ativ_id,
                observacao=metadata.get("observacao"),
            ))

        # ── Histórico ──
        if ativ_id:
            db.add(models.HistoricoWorkflow(
                documento_id=doc.id,
                atividade_origem_id=old_ativ_id,
                atividade_destino_id=ativ_id,
                acao=acao_historico,
                user_id=metadata["responsavel_id"],
                observacao=metadata.get("observacao"),
            ))

        job.status = "concluido"
        job.documento_id = doc.id
        db.commit()
        logger.info("Job %s concluído (documento %s)", job_id, doc.id)

    except Exception as exc:
        logger.exception("Erro ao processar upload job %s", job_id)
        db.rollback()
        try:
            j = db.query(models.UploadJob).filter(models.UploadJob.id == job_id).first()
            if j:
                j.status = "erro"
                j.erro_msg = str(exc)[:500]
                db.commit()
        except Exception:
            logger.exception("Falha ao registrar erro do job %s", job_id)
        raise
    finally:
        # Limpa a área temporária em qualquer desfecho.
        shutil.rmtree(str(config.UPLOAD_DIR / "tmp" / job_id), ignore_errors=True)
        db.close()
