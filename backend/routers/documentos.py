from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from database import get_db
from auth import get_current_user, require_admin
import models, schemas, os, uuid, shutil
from pathlib import Path
from typing import List
from utils import doc_rev_dir, safe_filename, extension_allowed, unique_path

router = APIRouter(prefix="/documentos", tags=["documentos"])
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./uploads"))


def _rev(idx: int) -> str:
    return str(idx + 1)


def _ativ(a):
    if not a:
        return None
    return {"id": a.id, "nome": a.nome, "fluxo_id": a.fluxo_id,
            "fluxo": {"id": a.fluxo.id, "numero": a.fluxo.numero, "nome": a.fluxo.nome}}


def _doc_base(doc):
    return {
        "id": doc.id, "codigo": doc.codigo, "nome": doc.nome,
        "ambiente_id": doc.ambiente_id, "area_id": doc.area_id,
        "projeto_id": doc.projeto_id, "tipo_documento_id": doc.tipo_documento_id,
        "responsavel": {"id": doc.responsavel.id, "username": doc.responsavel.username},
        "atividade_atual": _ativ(doc.atividade_atual),
        "revisao_indice": doc.revisao_indice,
        "revisao_label": _rev(doc.revisao_indice),
        "created_at": doc.created_at.isoformat(),
    }


def _doc_detalhe(doc, db: Session):
    campos = db.query(models.CampoFormulario).filter(
        models.CampoFormulario.tipo_documento_id == doc.tipo_documento_id
    ).order_by(models.CampoFormulario.ordem).all()
    valores_map = {v.campo_id: v.valor for v in doc.valores_campos}

    d = _doc_base(doc)
    d["arquivos"] = [
        {"id": a.id, "arquivo_nome": a.arquivo_nome, "arquivo_path": a.arquivo_path,
         "revisao_indice": a.revisao_indice, "revisao_label": _rev(a.revisao_indice),
         "observacao": a.observacao,
         "atividade": {"id": a.atividade.id, "nome": a.atividade.nome} if a.atividade else None,
         "uploaded_by": {"id": a.uploaded_by.id, "username": a.uploaded_by.username},
         "created_at": a.created_at.isoformat()}
        for a in doc.arquivos
    ]
    d["historico"] = [
        {"id": h.id,
         "atividade_origem": {"id": h.atividade_origem.id, "nome": h.atividade_origem.nome,
                              "fluxo_id": h.atividade_origem.fluxo_id} if h.atividade_origem else None,
         "atividade_destino": {"id": h.atividade_destino.id, "nome": h.atividade_destino.nome,
                               "fluxo_id": h.atividade_destino.fluxo_id},
         "acao": h.acao, "observacao": h.observacao,
         "user": {"id": h.user.id, "username": h.user.username},
         "created_at": h.created_at.isoformat()}
        for h in doc.historico
    ]
    d["valores_campos"] = [
        {"campo_id": c.id, "campo_nome": c.nome, "campo_tipo": c.tipo,
         "opcoes": c.opcoes, "valor": valores_map.get(c.id)}
        for c in campos
    ]
    return d


def _load(doc_id: int, db: Session):
    return db.query(models.Documento).options(
        joinedload(models.Documento.responsavel),
        joinedload(models.Documento.atividade_atual).joinedload(models.Atividade.fluxo),
        joinedload(models.Documento.arquivos).joinedload(models.DocumentoArquivo.uploaded_by),
        joinedload(models.Documento.arquivos).joinedload(models.DocumentoArquivo.atividade),
        joinedload(models.Documento.historico).joinedload(models.HistoricoWorkflow.user),
        joinedload(models.Documento.historico).joinedload(models.HistoricoWorkflow.atividade_origem),
        joinedload(models.Documento.historico).joinedload(models.HistoricoWorkflow.atividade_destino),
        joinedload(models.Documento.valores_campos).joinedload(models.ValorCampo.campo),
    ).filter(models.Documento.id == doc_id).first()


@router.get("")
def listar(
    nome: str = None,
    id: int = None,
    ambiente_id: int = None,
    area_id: int = None,
    projeto_id: int = None,
    tipo_documento_id: int = None,
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(models.Documento).options(
        joinedload(models.Documento.responsavel),
        joinedload(models.Documento.atividade_atual).joinedload(models.Atividade.fluxo),
    )
    if id:                 q = q.filter(models.Documento.id == id)
    if nome:               q = q.filter(models.Documento.nome.ilike(f"%{nome}%"))
    if ambiente_id:        q = q.filter(models.Documento.ambiente_id == ambiente_id)
    if area_id:            q = q.filter(models.Documento.area_id == area_id)
    if projeto_id:         q = q.filter(models.Documento.projeto_id == projeto_id)
    if tipo_documento_id:  q = q.filter(models.Documento.tipo_documento_id == tipo_documento_id)

    total = q.count()
    docs = q.order_by(desc(models.Documento.created_at)).offset(skip).limit(limit).all()
    return {"total": total, "skip": skip, "limit": limit, "itens": [_doc_base(d) for d in docs]}


@router.post("/upload")
async def upload(
    nome: str = Form(...),
    ambiente_id: int = Form(...),
    area_id: int = Form(...),
    projeto_id: int = Form(...),
    tipo_documento_id: int = Form(...),
    arquivos: List[UploadFile] = File(...),
    observacao: str = Form(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    MAX_SIZE = 100 * 1024 * 1024  # 100 MB
    job_id = str(uuid.uuid4())
    tmp_dir = UPLOAD_DIR / "tmp" / job_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    arquivos_info = []
    try:
        for arquivo in arquivos:
            filename = safe_filename(arquivo.filename)
            if not extension_allowed(filename):
                shutil.rmtree(str(tmp_dir), ignore_errors=True)
                raise HTTPException(400, f"Extensão não permitida: '{filename}'")
            tmp_path = tmp_dir / filename
            size = 0
            with open(tmp_path, "wb") as f:
                while True:
                    chunk = await arquivo.read(1024 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_SIZE:
                        shutil.rmtree(str(tmp_dir), ignore_errors=True)
                        raise HTTPException(413, f"'{arquivo.filename}' excede o limite de 100MB")
                    f.write(chunk)
            arquivos_info.append({"filename": filename, "tmp_path": str(tmp_path)})
    except HTTPException:
        raise
    except Exception as exc:
        shutil.rmtree(str(tmp_dir), ignore_errors=True)
        raise HTTPException(500, f"Erro ao receber arquivos: {exc}")

    job = models.UploadJob(id=job_id, status="pendente")
    db.add(job)
    db.commit()

    from tasks import processar_upload
    processar_upload.delay(
        job_id=job_id,
        metadata={
            "nome": nome,
            "ambiente_id": ambiente_id,
            "area_id": area_id,
            "projeto_id": projeto_id,
            "tipo_documento_id": tipo_documento_id,
            "responsavel_id": user.id,
            "observacao": observacao or None,
        },
        arquivos_tmp=arquivos_info,
    )

    return {"job_id": job_id, "status": "pendente", "total_arquivos": len(arquivos_info)}


@router.get("/jobs/{job_id}")
def status_job(job_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    job = db.query(models.UploadJob).filter(models.UploadJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job não encontrado")
    return {
        "job_id": job.id,
        "status": job.status,
        "documento_id": job.documento_id,
        "erro_msg": job.erro_msg,
        "created_at": job.created_at.isoformat(),
    }


@router.post("/{doc_id}/upload-revisao")
async def upload_revisao(
    doc_id: int,
    arquivo: UploadFile = File(...),
    observacao: str = Form(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    doc = db.query(models.Documento).filter(models.Documento.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Documento não encontrado")

    filename = safe_filename(arquivo.filename)
    if not extension_allowed(filename):
        raise HTTPException(400, f"Extensão não permitida: '{filename}'")

    file_dir = doc_rev_dir(
        UPLOAD_DIR,
        doc.ambiente.nome, doc.area.nome, doc.projeto.nome,
        doc.nome, _rev(doc.revisao_indice),
    )
    MAX_SIZE = 100 * 1024 * 1024  # 100 MB
    final_path = unique_path(file_dir, filename)
    size = 0
    with open(final_path, "wb") as f:
        while True:
            chunk = await arquivo.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_SIZE:
                f.close()
                final_path.unlink(missing_ok=True)
                raise HTTPException(413, f"'{filename}' excede o limite de 100MB")
            f.write(chunk)
    rel_path = str(final_path.relative_to(UPLOAD_DIR)).replace("\\", "/")

    db.add(models.DocumentoArquivo(
        documento_id=doc.id, arquivo_nome=filename,
        arquivo_path=rel_path,
        revisao_indice=doc.revisao_indice, uploaded_by_id=user.id,
        atividade_id=doc.atividade_atual_id,
        observacao=observacao or None,
    ))
    db.commit()
    return _doc_detalhe(_load(doc_id, db), db)


@router.get("/{doc_id}")
def detalhe(doc_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    doc = _load(doc_id, db)
    if not doc: raise HTTPException(404, "Documento não encontrado")
    return _doc_detalhe(doc, db)


@router.put("/{doc_id}/campos")
def atualizar_campos(doc_id: int, data: schemas.CamposUpdate,
                     db: Session = Depends(get_db), _=Depends(require_admin)):
    if not db.query(models.Documento).filter(models.Documento.id == doc_id).first():
        raise HTTPException(404, "Documento não encontrado")
    for item in data.valores:
        existente = db.query(models.ValorCampo).filter(
            models.ValorCampo.documento_id == doc_id,
            models.ValorCampo.campo_id == item.campo_id
        ).first()
        if existente:
            existente.valor = item.valor
        else:
            db.add(models.ValorCampo(documento_id=doc_id, campo_id=item.campo_id, valor=item.valor))
    db.commit()
    return {"ok": True}


@router.post("/{doc_id}/transitar")
def transitar(doc_id: int, req: schemas.TransicaoRequest,
              db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    doc = _load(doc_id, db)
    if not doc: raise HTTPException(404, "Documento não encontrado")
    if not doc.atividade_atual_id:
        raise HTTPException(400, "Documento sem atividade atual")

    trans = db.query(models.ConfigTransicao).filter(
        models.ConfigTransicao.atividade_origem_id == doc.atividade_atual_id,
        models.ConfigTransicao.acao == req.acao
    ).first()
    if not trans:
        raise HTTPException(400, f"Sem transição configurada para '{req.acao}'")

    db.add(models.HistoricoWorkflow(
        documento_id=doc.id, atividade_origem_id=doc.atividade_atual_id,
        atividade_destino_id=trans.atividade_destino_id,
        acao=req.acao, user_id=user.id, observacao=req.observacao,
    ))

    doc_db = db.query(models.Documento).filter(models.Documento.id == doc_id).first()
    if trans.gera_nova_revisao:
        doc_db.revisao_indice += 1
    doc_db.atividade_atual_id = trans.atividade_destino_id
    db.commit()
    return _doc_detalhe(_load(doc_id, db), db)
