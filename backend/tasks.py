from celery_app import celery_app
from database import SessionLocal
import models, shutil, uuid
from pathlib import Path
import os
from dotenv import load_dotenv
from utils import doc_rev_dir

load_dotenv()
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "C:/A1Doc/files"))


def _rev(idx: int) -> str:
    return str(idx + 1)


@celery_app.task(bind=True, name="processar_upload")
def processar_upload(self, job_id: str, metadata: dict, arquivos_tmp: list):
    db = SessionLocal()
    try:
        job = db.query(models.UploadJob).filter(models.UploadJob.id == job_id).first()
        if not job:
            return
        job.status = "processando"
        db.commit()

        # ── Upsert: mesmo nome + projeto = mesmo documento ──
        existing = db.query(models.Documento).filter(
            models.Documento.nome == metadata["nome"],
            models.Documento.projeto_id == metadata["projeto_id"],
        ).first()

        is_new = existing is None

        # Carrega primeira atividade do Fluxo 0 (estado inicial)
        fluxo_zero = db.query(models.Fluxo).filter(models.Fluxo.numero == 0).first()
        ativ_inicial_id = fluxo_zero.atividades[0].id if fluxo_zero and fluxo_zero.atividades else None

        if is_new:
            codigo = f"DOC-{uuid.uuid4().hex[:8].upper()}"
            doc = models.Documento(
                codigo=codigo,
                nome=metadata["nome"],
                ambiente_id=metadata["ambiente_id"],
                area_id=metadata["area_id"],
                projeto_id=metadata["projeto_id"],
                tipo_documento_id=metadata["tipo_documento_id"],
                responsavel_id=metadata["responsavel_id"],
                atividade_atual_id=ativ_inicial_id,
                revisao_indice=0,
            )
            db.add(doc)
            db.flush()
            old_ativ_id = None
            ativ_id = ativ_inicial_id
            acao_historico = "upload_inicial"
        else:
            doc = existing
            old_ativ_id = doc.atividade_atual_id

            ativ_id = old_ativ_id  # default: fica onde está

            if old_ativ_id:
                # 1. Tenta transição configurada (qualquer ação)
                trans = db.query(models.ConfigTransicao).filter(
                    models.ConfigTransicao.atividade_origem_id == old_ativ_id,
                ).first()

                if trans:
                    if trans.gera_nova_revisao:
                        doc.revisao_indice += 1
                    doc.atividade_atual_id = trans.atividade_destino_id
                    ativ_id = trans.atividade_destino_id
                else:
                    # 2. Fallback: próxima atividade por ID no mesmo fluxo
                    cur = db.query(models.Atividade).filter(models.Atividade.id == old_ativ_id).first()
                    if cur:
                        prox = db.query(models.Atividade).filter(
                            models.Atividade.fluxo_id == cur.fluxo_id,
                            models.Atividade.id > old_ativ_id,
                        ).order_by(models.Atividade.id).first()
                        if prox:
                            doc.atividade_atual_id = prox.id
                            ativ_id = prox.id

            acao_historico = "reenvio"

        # ── Nomes para montar o caminho hierárquico ──
        amb  = db.query(models.Ambiente).filter(models.Ambiente.id == doc.ambiente_id).first()
        area = db.query(models.Area).filter(models.Area.id == doc.area_id).first()
        proj = db.query(models.Projeto).filter(models.Projeto.id == doc.projeto_id).first()

        file_dir = doc_rev_dir(
            UPLOAD_DIR,
            amb.nome, area.nome, proj.nome,
            doc.nome, _rev(doc.revisao_indice),
        )

        for arq_info in arquivos_tmp:
            tmp_path = Path(arq_info["tmp_path"])
            filename  = arq_info["filename"]
            final_path = file_dir / filename
            shutil.move(str(tmp_path), str(final_path))

            rel_path = str(final_path.relative_to(UPLOAD_DIR)).replace("\\", "/")

            db.add(models.DocumentoArquivo(
                documento_id=doc.id,
                arquivo_nome=filename,
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

        # ── Limpa tmp ──
        try:
            shutil.rmtree(str(UPLOAD_DIR / "tmp" / job_id))
        except Exception:
            pass

        job.status = "concluido"
        job.documento_id = doc.id
        db.commit()

    except Exception as exc:
        db.rollback()
        try:
            j = db.query(models.UploadJob).filter(models.UploadJob.id == job_id).first()
            if j:
                j.status = "erro"
                j.erro_msg = str(exc)[:500]
                db.commit()
        except Exception:
            pass
        raise
    finally:
        db.close()
