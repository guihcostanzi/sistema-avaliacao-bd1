from typing import Optional
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.database import get_db
from app.session_dependencies import get_usuario_autenticado

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
def listar_projetos(
    request: Request,
    passo: int = 0,
    limite: int = 10,
    nome: Optional[str] = None,
    success_message: Optional[str] = None,
    error_message: Optional[str] = None,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    query_base = """
        SELECT p.ID, p.NOME, p.DATA_CADASTRO
        FROM PROJETO p 
        INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
        WHERE up.USUARIO_ID = :usuario_id
    """
    parametros = {"usuario_id": current_user['id']}
    
    if nome:
        query_base += " AND p.NOME ILIKE :nome"
        parametros["nome"] = f"%{nome}%"
    
    query_base += " ORDER BY p.DATA_CADASTRO DESC LIMIT :limite OFFSET :passo"
    parametros["limite"] = limite
    parametros["passo"] = passo
    
    query = text(query_base)
    result = db.execute(query, parametros)
    projetos = result.fetchall()
    
    query_total = text("""
        SELECT COUNT(*) as total 
        FROM PROJETO p 
        INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
        WHERE up.USUARIO_ID = :usuario_id
    """)
    total_projetos = db.execute(query_total, {"usuario_id": current_user['id']}).scalar()
    
    total_paginas = (total_projetos + limite - 1) // limite if total_projetos > 0 else 1
    pagina_atual = (passo // limite) + 1

    contexto = {
        "request": request,
        "projetos": projetos,
        "total_projetos": total_projetos,
        "pagina_atual": pagina_atual,
        "total_paginas": total_paginas,
        "limite": limite,
        "filtro_nome": nome or "",
        "has_previous": passo > 0,
        "has_next": pagina_atual < total_paginas,
        "previous_page": max(1, pagina_atual - 1),
        "next_page": min(total_paginas, pagina_atual + 1),
        "success_message": success_message,
        "error_message": error_message,
        "usuario": current_user
    }
    
    return templates.TemplateResponse("projetos.html", contexto)

@router.post("/criar")
def criar_projeto(
    nome: str = Form(...),
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_checar_nome = text("SELECT ID FROM PROJETO WHERE NOME = :nome")
        if db.execute(query_checar_nome, {"nome": nome}).first():
            return RedirectResponse(
                url="/projetos/?error_message=Já existe um projeto com este nome", 
                status_code=303
            )
        
        query_cadastro = text("INSERT INTO PROJETO (NOME) VALUES (:nome) RETURNING ID")
        result = db.execute(query_cadastro, {"nome": nome})
        projeto_id = result.fetchone()[0]
        
        query_associar = text("INSERT INTO USUARIO_PROJETO (USUARIO_ID, PROJETO_ID) VALUES (:usuario_id, :projeto_id)")
        db.execute(query_associar, {"usuario_id": current_user['id'], "projeto_id": projeto_id})
        db.commit()
        
        return RedirectResponse(
            url="/projetos/?success_message=Projeto criado com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url="/projetos/?error_message=Erro ao criar projeto", 
            status_code=303
        )

@router.post("/editar/{projeto_id}")
def editar_projeto(
    projeto_id: int,
    nome: str = Form(...),
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar = text("""
            SELECT p.ID FROM PROJETO p 
            INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
            WHERE p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar, {"projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return RedirectResponse(
                url="/projetos/?error_message=Projeto não encontrado ou sem permissão", 
                status_code=303
            )
        
        query_checar_nome = text("SELECT ID FROM PROJETO WHERE NOME = :nome AND ID != :projeto_id")
        if db.execute(query_checar_nome, {"nome": nome, "projeto_id": projeto_id}).first():
            return RedirectResponse(
                url="/projetos/?error_message=Já existe um projeto com este nome", 
                status_code=303
            )
        
        query_update = text("UPDATE PROJETO SET NOME = :nome WHERE ID = :projeto_id")
        db.execute(query_update, {"nome": nome, "projeto_id": projeto_id})
        db.commit()
        
        return RedirectResponse(
            url="/projetos/?success_message=Projeto atualizado com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url="/projetos/?error_message=Erro ao atualizar projeto", 
            status_code=303
        )

@router.post("/deletar/{projeto_id}")
def deletar_projeto(
    projeto_id: int,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar = text("""
            SELECT p.ID FROM PROJETO p 
            INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
            WHERE p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar, {"projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return RedirectResponse(
                url="/projetos/?error_message=Projeto não encontrado ou sem permissão", 
                status_code=303
            )
        
        query_delete = text("DELETE FROM PROJETO WHERE ID = :projeto_id")
        db.execute(query_delete, {"projeto_id": projeto_id})
        db.commit()
        
        return RedirectResponse(
            url="/projetos/?success_message=Projeto excluído com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url="/projetos/?error_message=Erro ao excluir projeto", 
            status_code=303
        )