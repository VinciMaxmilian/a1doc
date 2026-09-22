import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import and_, desc, false, or_
from sqlalchemy.orm import Session, joinedload

import config
import models
import schemas
from auth import get_current_user, is_admin
from database import get_db
from indoc.permissions.constants import Permission
from indoc.permissions.deps import get_permissions
from indoc.permissions.service import PermissionService
from indoc.permissions.service import documento as rec_documento
from indoc.permissions.service import projeto as rec_projeto
from utils import (
    doc_rev_dir,
    ensure_within,
    extension_allowed,
    safe_filename,
    unique_path,
)

logger = logging.getLogger("indoc.documentos")

router = APIRouter(prefix="/documentos", tags=["documentos"])


# ────────────────────────── autorização ──────────────────────────
#
# A decisão de acesso é da ACL (PermissionService). O que sobra aqui é a
# restrição de WORKFLOW — `Atividade.role_requerido`, que diz qual papel detém
# a atividade em que o documento está parado. São coisas diferentes: a ACL
# responde "pode aprovar documentos deste projeto?", o role_requerido responde
# "a bola está com você agora?".
#
# A FASE 11 (responsáveis e matriz de distribuição) substitui o role_requerido
# por regras de responsável de verdade; até lá as duas checagens convivem e
# AMBAS precisam passar.


def _detem_atividade(user: models.User, doc: models.Documento) -> bool:
    if is_admin(user):
        return True
    ativ = doc.atividade_atual
    if ativ is None or ativ.role_requerido is None:
        return True
    return user.role == ativ.role_requerido


def _exigir(condicao: bool, msg: str) -> None:
    if not condicao:
        raise HTTPException(403, msg)


# ────────────────────────── serialização ──────────────────────────

def _detalhe(doc: models.Documento, db: Session) -> schemas.DocumentoDetalheOut:
    """Monta o detalhe do documento. `valores_campos` combina a definição do
    formulário (todos os campos do tipo) com os valores já preenchidos."""
    campos = db.query(models.CampoFormulario).filter(
        models.CampoFormulario.tipo_documento_id == doc.tipo_documento_id
    ).order_by(models.CampoFormulario.ordem).all()
    valores_map = {v.campo_id: v.valor for v in doc.valores_campos}

    out = schemas.DocumentoDetalheOut.model_validate(doc)
    out.valores_campos = [
        schemas.ValorCampoOut(
            campo_id=c.id, campo_nome=c.nome, campo_tipo=c.tipo,
            opcoes=c.opcoes, valor=valores_map.get(c.id),
        )
        for c in campos
    ]
    return out


def _load(doc_id: int, db: Session) -> Optional[models.Documento]:
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


def _load_ou_404(doc_id: int, db: Session) -> models.Documento:
    doc = _load(doc_id, db)
    if not doc:
        raise HTTPException(404, "Documento não encontrado")
    return doc


# ────────────────────────── endpoints ──────────────────────────

@router.get("", response_model=schemas.PaginaDocumentosOut)
def listar(
    nome: str = None,
    id: int = None,
    ambiente_id: int = None,
    area_id: int = None,
    projeto_id: int = None,
    tipo_documento_id: int = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(config.DEFAULT_PAGE_SIZE, ge=1, le=config.MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    perms: PermissionService = Depends(get_permissions),
):
    q = db.query(models.Documento).options(
        joinedload(models.Documento.responsavel),
        joinedload(models.Documento.atividade_atual).joinedload(models.Atividade.fluxo),
    )
    q = _somente_legiveis(q, perms)
    if id:                 q = q.filter(models.Documento.id == id)
    if nome:               q = q.filter(models.Documento.nome.ilike(f"%{nome}%"))
    if ambiente_id:        q = q.filter(models.Documento.ambiente_id == ambiente_id)
    if area_id:            q = q.filter(models.Documento.area_id == area_id)
    if projeto_id:         q = q.filter(models.Documento.projeto_id == projeto_id)
    if tipo_documento_id:  q = q.filter(models.Documento.tipo_documento_id == tipo_documento_id)

    total = q.count()
    docs = q.order_by(desc(models.Documento.created_at)).offset(skip).limit(limit).all()
    return {"total": total, "skip": skip, "limit": limit, "itens": docs}


def _somente_legiveis(q, perms: PermissionService):
    """Restringe a query ao que o usuário pode ler.

    Sem isto a ACL protegeria `GET /documentos/{id}` enquanto a listagem
    continuaria devolvendo a base inteira — a falha D1 do roadmap.

    Regra: vale o projeto, salvo regra no próprio documento, que sobrescreve
    nos dois sentidos (um allow no documento entra mesmo com o projeto
    fechado; um deny sai mesmo com o projeto aberto).
    """
    projetos = perms.projetos_legiveis()
    if projetos is None:  # admin: sem restrição
        return q

    concedidos, negados = perms.documentos_com_regra_propria()

    condicao = models.Documento.projeto_id.in_(projetos) if projetos else false()
    if negados:
        condicao = and_(condicao, ~models.Documento.id.in_(negados))
    if concedidos:
        condicao = or_(condicao, models.Documento.id.in_(concedidos))
    return q.filter(condicao)


def _validar_hierarquia(db: Session, ambiente_id: int, area_id: int,
                        projeto_id: int, tipo_documento_id: int) -> None:
    """Garante que projeto→área→ambiente são consistentes entre si."""
    projeto = db.query(models.Projeto).filter(models.Projeto.id == projeto_id).first()
    if not projeto:
        raise HTTPException(400, "Projeto não encontrado")
    area = db.query(models.Area).filter(models.Area.id == area_id).first()
    if not area or projeto.area_id != area.id:
        raise HTTPException(400, "Projeto não pertence à área informada")
    if area.ambiente_id != ambiente_id:
        raise HTTPException(400, "Área não pertence ao ambiente informado")
    if not db.query(models.TipoDocumento).filter(
        models.TipoDocumento.id == tipo_documento_id
    ).first():
        raise HTTPException(400, "Tipo de documento não encontrado")


@router.post("/upload", response_model=schemas.UploadAceitoOut, status_code=202)
async def upload(
    nome: str = Form(..., min_length=1, max_length=500),
    ambiente_id: int = Form(...),
    area_id: int = Form(...),
    projeto_id: int = Form(...),
    tipo_documento_id: int = Form(...),
    arquivos: list[UploadFile] = File(...),
    observacao: str = Form(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
    perms: PermissionService = Depends(get_permissions),
):
    _validar_hierarquia(db, ambiente_id, area_id, projeto_id, tipo_documento_id)
    # Checado no PROJETO de destino: quem pode criar num projeto não pode,
    # por isso, criar em qualquer outro.
    perms.exigir(Permission.CREATE, rec_projeto(projeto_id))

    job_id = str(uuid.uuid4())
    tmp_dir = config.UPLOAD_DIR / "tmp" / job_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    arquivos_info = []
    try:
        for arquivo in arquivos:
            filename = safe_filename(arquivo.filename or "")
            if not extension_allowed(filename):
                raise HTTPException(400, f"Extensão não permitida: '{filename}'")
            # unique_path evita que dois arquivos de mesmo nome no mesmo envio
            # se sobrescrevam na área temporária.
            tmp_path = unique_path(tmp_dir, filename)
            await _gravar_em_disco(arquivo, tmp_path)
            arquivos_info.append({"filename": tmp_path.name, "tmp_path": str(tmp_path)})
    except Exception:
        shutil.rmtree(str(tmp_dir), ignore_errors=True)
        raise

    db.add(models.UploadJob(id=job_id, status="pendente"))
    db.commit()

    from tasks import processar_upload
    processar_upload.delay(
        job_id=job_id,
        metadata={
            "nome": nome.strip(),
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


async def _gravar_em_disco(arquivo: UploadFile, destino: Path) -> int:
    """Escreve o upload em chunks, respeitando MAX_UPLOAD_BYTES.

    Em caso de erro remove o arquivo parcial antes de propagar.
    """
    size = 0
    try:
        with open(destino, "wb") as f:
            while True:
                chunk = await arquivo.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        413,
                        f"'{destino.name}' excede o limite de "
                        f"{config.MAX_UPLOAD_BYTES // (1024 * 1024)}MB",
                    )
                f.write(chunk)
    except Exception:
        destino.unlink(missing_ok=True)
        raise
    return size


@router.get("/jobs/{job_id}", response_model=schemas.JobOut)
def status_job(job_id: str, db: Session = Depends(get_db), _=Depends(get_current_user)):
    job = db.query(models.UploadJob).filter(models.UploadJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job não encontrado")
    return job


@router.get("/arquivos/{arquivo_id}/download")
def baixar_arquivo(arquivo_id: int, db: Session = Depends(get_db),
                   perms: PermissionService = Depends(get_permissions)):
    """Download autorizado. Os arquivos não são servidos como estáticos
    públicos — o caminho no disco nunca é exposto ao cliente."""
    arq = db.query(models.DocumentoArquivo).filter(
        models.DocumentoArquivo.id == arquivo_id
    ).first()
    if not arq:
        raise HTTPException(404, "Arquivo não encontrado")

    # A permissão é do DOCUMENTO: o arquivo é só a representação física dele.
    perms.exigir(Permission.DOWNLOAD, rec_documento(arq.documento_id))

    try:
        # arquivo_path vem do banco, mas validamos mesmo assim: registro
        # antigo/corrompido não pode virar leitura arbitrária de disco.
        caminho = ensure_within(config.UPLOAD_DIR, config.UPLOAD_DIR / arq.arquivo_path)
    except ValueError:
        logger.error("arquivo_path fora de UPLOAD_DIR (id=%s): %r", arq.id, arq.arquivo_path)
        raise HTTPException(404, "Arquivo não encontrado") from None

    if not caminho.is_file():
        raise HTTPException(404, "Arquivo não encontrado no armazenamento")

    return FileResponse(caminho, filename=arq.arquivo_nome,
                        media_type="application/octet-stream")


@router.post("/{doc_id}/upload-revisao", response_model=schemas.DocumentoDetalheOut)
async def upload_revisao(
    doc_id: int,
    arquivo: UploadFile = File(...),
    observacao: str = Form(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
    perms: PermissionService = Depends(get_permissions),
):
    doc = _load_ou_404(doc_id, db)
    perms.exigir(Permission.REVISE, rec_documento(doc_id))
    # Além da ACL, a restrição de workflow: o responsável sempre pode revisar
    # o próprio documento; os demais só se detiverem a atividade atual.
    _exigir(doc.responsavel_id == user.id or _detem_atividade(user, doc),
            "Sem permissão para enviar revisão deste documento")

    filename = safe_filename(arquivo.filename or "")
    if not extension_allowed(filename):
        raise HTTPException(400, f"Extensão não permitida: '{filename}'")

    file_dir = doc_rev_dir(
        config.UPLOAD_DIR,
        doc.ambiente.nome, doc.area.nome, doc.projeto.nome,
        doc.nome, str(doc.revisao_indice + 1),
    )
    final_path = unique_path(file_dir, filename)
    await _gravar_em_disco(arquivo, final_path)
    rel_path = str(final_path.relative_to(config.UPLOAD_DIR)).replace("\\", "/")

    db.add(models.DocumentoArquivo(
        documento_id=doc.id, arquivo_nome=final_path.name,
        arquivo_path=rel_path,
        revisao_indice=doc.revisao_indice, uploaded_by_id=user.id,
        atividade_id=doc.atividade_atual_id,
        observacao=observacao or None,
    ))
    db.commit()
    return _detalhe(_load_ou_404(doc_id, db), db)


@router.get("/{doc_id}", response_model=schemas.DocumentoDetalheOut)
def detalhe(doc_id: int, db: Session = Depends(get_db),
            perms: PermissionService = Depends(get_permissions)):
    perms.exigir(Permission.READ, rec_documento(doc_id))
    return _detalhe(_load_ou_404(doc_id, db), db)


@router.put("/{doc_id}/campos", response_model=schemas.OkOut)
def atualizar_campos(doc_id: int, data: schemas.CamposUpdate,
                     db: Session = Depends(get_db),
                     perms: PermissionService = Depends(get_permissions)):
    perms.exigir(Permission.MANAGE_METADATA, rec_documento(doc_id))
    doc = db.query(models.Documento).filter(models.Documento.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Documento não encontrado")

    # Só aceita campos que pertencem ao tipo de documento — impede gravar
    # valores órfãos, ligados a formulário de outro tipo.
    validos = {
        c.id for c in db.query(models.CampoFormulario.id).filter(
            models.CampoFormulario.tipo_documento_id == doc.tipo_documento_id
        ).all()
    }
    invalidos = {i.campo_id for i in data.valores} - validos
    if invalidos:
        raise HTTPException(
            400, f"Campos não pertencem ao tipo do documento: {sorted(invalidos)}"
        )

    existentes = {
        v.campo_id: v for v in db.query(models.ValorCampo).filter(
            models.ValorCampo.documento_id == doc_id
        ).all()
    }
    for item in data.valores:
        if item.campo_id in existentes:
            existentes[item.campo_id].valor = item.valor
        else:
            db.add(models.ValorCampo(
                documento_id=doc_id, campo_id=item.campo_id, valor=item.valor
            ))
    db.commit()
    return {"ok": True}


@router.post("/{doc_id}/transitar", response_model=schemas.DocumentoDetalheOut)
def transitar(doc_id: int, req: schemas.TransicaoRequest,
              db: Session = Depends(get_db), user: models.User = Depends(get_current_user),
              perms: PermissionService = Depends(get_permissions)):
    doc = _load_ou_404(doc_id, db)
    if not doc.atividade_atual_id:
        raise HTTPException(400, "Documento sem atividade atual")
    # Aprovar e reprovar são permissões distintas: dá para deixar alguém
    # devolver um documento sem poder liberá-lo.
    exigida = Permission.APPROVE if req.acao == "aprovado" else Permission.REJECT
    perms.exigir(exigida, rec_documento(doc_id))
    _exigir(_detem_atividade(user, doc), "Sem permissão para transitar este documento")

    trans = db.query(models.ConfigTransicao).filter(
        models.ConfigTransicao.atividade_origem_id == doc.atividade_atual_id,
        models.ConfigTransicao.acao == req.acao,
    ).first()
    if not trans:
        raise HTTPException(400, f"Sem transição configurada para '{req.acao}'")

    db.add(models.HistoricoWorkflow(
        documento_id=doc.id, atividade_origem_id=doc.atividade_atual_id,
        atividade_destino_id=trans.atividade_destino_id,
        acao=req.acao, user_id=user.id, observacao=req.observacao,
    ))
    if trans.gera_nova_revisao:
        doc.revisao_indice += 1
    doc.atividade_atual_id = trans.atividade_destino_id
    db.commit()
    return _detalhe(_load_ou_404(doc_id, db), db)
