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
    
# Seção de entidades

@router.get("/{projeto_id}/entidades", response_class=HTMLResponse)
def listar_entidades(
    projeto_id: int,
    request: Request,
    passo: int = 0,
    limite: int = 10,
    nome: Optional[str] = None,
    success_message: Optional[str] = None,
    error_message: Optional[str] = None,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    query_verificar_projeto = text("""
        SELECT p.ID, p.NOME FROM PROJETO p 
        INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
        WHERE p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
    """)
    projeto = db.execute(query_verificar_projeto, {"projeto_id": projeto_id, "usuario_id": current_user['id']}).first()
    
    if not projeto:
        return RedirectResponse(url="/projetos/?error_message=Projeto não encontrado", status_code=303)
    
    query_base = "SELECT ID, NOME, DATA_CADASTRO FROM ESTR_ENTIDADE WHERE PROJETO_ID = :projeto_id"
    parametros = {"projeto_id": projeto_id}
    
    if nome:
        query_base += " AND NOME ILIKE :nome"
        parametros["nome"] = f"%{nome}%"
    
    query_base += " ORDER BY DATA_CADASTRO DESC LIMIT :limite OFFSET :passo"
    parametros["limite"] = limite
    parametros["passo"] = passo
    
    query = text(query_base)
    result = db.execute(query, parametros)
    entidades = result.fetchall()
    
    query_total = text("SELECT COUNT(*) as total FROM ESTR_ENTIDADE WHERE PROJETO_ID = :projeto_id")
    total_entidades = db.execute(query_total, {"projeto_id": projeto_id}).scalar()
    
    total_paginas = (total_entidades + limite - 1) // limite if total_entidades > 0 else 1
    pagina_atual = (passo // limite) + 1

    contexto = {
        "request": request,
        "projeto": projeto,
        "entidades": entidades,
        "total_entidades": total_entidades,
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
    
    return templates.TemplateResponse("entidades.html", contexto)

@router.post("/{projeto_id}/entidades/criar")
def criar_entidade(
    projeto_id: int,
    nome: str = Form(...),
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar_projeto = text("""
            SELECT p.ID FROM PROJETO p 
            INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
            WHERE p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar_projeto, {"projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return RedirectResponse(url="/projetos/?error_message=Projeto não encontrado", status_code=303)
        
        query_checar_nome = text("SELECT ID FROM ESTR_ENTIDADE WHERE NOME = :nome AND PROJETO_ID = :projeto_id")
        if db.execute(query_checar_nome, {"nome": nome, "projeto_id": projeto_id}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/entidades?error_message=Já existe uma entidade com este nome", 
                status_code=303
            )
        
        query_cadastro = text("INSERT INTO ESTR_ENTIDADE (PROJETO_ID, NOME) VALUES (:projeto_id, :nome)")
        db.execute(query_cadastro, {"projeto_id": projeto_id, "nome": nome})
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades?success_message=Entidade criada com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades?error_message=Erro ao criar entidade", 
            status_code=303
        )

@router.post("/{projeto_id}/entidades/editar/{entidade_id}")
def editar_entidade(
    projeto_id: int,
    entidade_id: int,
    nome: str = Form(...),
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar = text("""
            SELECT ee.ID FROM ESTR_ENTIDADE ee
            INNER JOIN PROJETO p ON ee.PROJETO_ID = p.ID
            INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
            WHERE ee.ID = :entidade_id AND p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar, {"entidade_id": entidade_id, "projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/entidades?error_message=Entidade não encontrada", 
                status_code=303
            )
        
        query_checar_nome = text("SELECT ID FROM ESTR_ENTIDADE WHERE NOME = :nome AND PROJETO_ID = :projeto_id AND ID != :entidade_id")
        if db.execute(query_checar_nome, {"nome": nome, "projeto_id": projeto_id, "entidade_id": entidade_id}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/entidades?error_message=Já existe uma entidade com este nome", 
                status_code=303
            )
        
        query_update = text("UPDATE ESTR_ENTIDADE SET NOME = :nome WHERE ID = :entidade_id")
        db.execute(query_update, {"nome": nome, "entidade_id": entidade_id})
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades?success_message=Entidade atualizada com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades?error_message=Erro ao atualizar entidade", 
            status_code=303
        )

@router.post("/{projeto_id}/entidades/deletar/{entidade_id}")
def deletar_entidade(
    projeto_id: int,
    entidade_id: int,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar = text("""
            SELECT ee.ID FROM ESTR_ENTIDADE ee
            INNER JOIN PROJETO p ON ee.PROJETO_ID = p.ID
            INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
            WHERE ee.ID = :entidade_id AND p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar, {"entidade_id": entidade_id, "projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/entidades?error_message=Entidade não encontrada", 
                status_code=303
            )
        
        query_delete = text("DELETE FROM ESTR_ENTIDADE WHERE ID = :entidade_id")
        db.execute(query_delete, {"entidade_id": entidade_id})
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades?success_message=Entidade excluída com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades?error_message=Erro ao excluir entidade", 
            status_code=303
        )
    
# Seção de atributos

@router.get("/{projeto_id}/entidades/{entidade_id}/atributos", response_class=HTMLResponse)
def listar_atributos(
    projeto_id: int,
    entidade_id: int,
    request: Request,
    passo: int = 0,
    limite: int = 10,
    nome: Optional[str] = None,
    tipo: Optional[str] = None,
    success_message: Optional[str] = None,
    error_message: Optional[str] = None,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    query_verificar = text("""
        SELECT p.ID, p.NOME as projeto_nome, ee.ID as entidade_id, ee.NOME as entidade_nome
        FROM PROJETO p 
        INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
        INNER JOIN ESTR_ENTIDADE ee ON p.ID = ee.PROJETO_ID
        WHERE p.ID = :projeto_id AND ee.ID = :entidade_id AND up.USUARIO_ID = :usuario_id
    """)
    resultado = db.execute(query_verificar, {"projeto_id": projeto_id, "entidade_id": entidade_id, "usuario_id": current_user['id']}).first()
    
    if not resultado:
        return RedirectResponse(url="/projetos/?error_message=Projeto ou entidade não encontrada", status_code=303)
    
    projeto = {"id": resultado.id, "nome": resultado.projeto_nome}
    entidade = {"id": resultado.entidade_id, "nome": resultado.entidade_nome}
    
    query_base = """
        SELECT ID_SEQ, NOME_ATRIBUTO, TIPO, LABEL, EXIBICAO, EDITAVEL, OBRIGATORIO
        FROM ESTR_ATRIBUTOS 
        WHERE ESTR_ENTIDADE_ID = :entidade_id
    """
    parametros = {"entidade_id": entidade_id}
    
    if nome:
        query_base += " AND NOME_ATRIBUTO ILIKE :nome"
        parametros["nome"] = f"%{nome}%"
    
    if tipo:
        query_base += " AND TIPO = :tipo"
        parametros["tipo"] = tipo
    
    query_base += " ORDER BY ID_SEQ LIMIT :limite OFFSET :passo"
    parametros["limite"] = limite
    parametros["passo"] = passo
    
    query = text(query_base)
    result = db.execute(query, parametros)
    atributos = result.fetchall()
    
    query_total = text("SELECT COUNT(*) as total FROM ESTR_ATRIBUTOS WHERE ESTR_ENTIDADE_ID = :entidade_id")
    total_atributos = db.execute(query_total, {"entidade_id": entidade_id}).scalar()
    
    total_paginas = (total_atributos + limite - 1) // limite if total_atributos > 0 else 1
    pagina_atual = (passo // limite) + 1

    contexto = {
        "request": request,
        "projeto": projeto,
        "entidade": entidade,
        "atributos": atributos,
        "total_atributos": total_atributos,
        "pagina_atual": pagina_atual,
        "total_paginas": total_paginas,
        "limite": limite,
        "filtro_nome": nome or "",
        "filtro_tipo": tipo or "",
        "has_previous": passo > 0,
        "has_next": pagina_atual < total_paginas,
        "previous_page": max(1, pagina_atual - 1),
        "next_page": min(total_paginas, pagina_atual + 1),
        "success_message": success_message,
        "error_message": error_message,
        "usuario": current_user
    }
    
    return templates.TemplateResponse("atributos.html", contexto)

@router.post("/{projeto_id}/entidades/{entidade_id}/atributos/criar")
def criar_atributo(
    projeto_id: int,
    entidade_id: int,
    nome_atributo: str = Form(...),
    tipo: str = Form(...),
    label: Optional[str] = Form(None),
    exibicao: Optional[str] = Form(None),
    editavel: Optional[str] = Form(None),
    obrigatorio: Optional[str] = Form(None),
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar = text("""
            SELECT ee.ID FROM ESTR_ENTIDADE ee
            INNER JOIN PROJETO p ON ee.PROJETO_ID = p.ID
            INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
            WHERE ee.ID = :entidade_id AND p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar, {"entidade_id": entidade_id, "projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return RedirectResponse(url="/projetos/?error_message=Entidade não encontrada", status_code=303)
        
        query_checar_nome = text("SELECT ID_SEQ FROM ESTR_ATRIBUTOS WHERE NOME_ATRIBUTO = :nome AND ESTR_ENTIDADE_ID = :entidade_id")
        if db.execute(query_checar_nome, {"nome": nome_atributo, "entidade_id": entidade_id}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/entidades/{entidade_id}/atributos?error_message=Já existe um atributo com este nome", 
                status_code=303
            )
        
        # Se este atributo será de exibição, verificar se já existe outro
        if exibicao == "true":
            query_checar_exibicao = text("SELECT ID_SEQ FROM ESTR_ATRIBUTOS WHERE EXIBICAO = true AND ESTR_ENTIDADE_ID = :entidade_id")
            if db.execute(query_checar_exibicao, {"entidade_id": entidade_id}).first():
                return RedirectResponse(
                    url=f"/projetos/{projeto_id}/entidades/{entidade_id}/atributos?error_message=Já existe um atributo de exibição para esta entidade", 
                    status_code=303
                )
        
        query_max_seq = text("SELECT COALESCE(MAX(ID_SEQ), 0) + 1 as next_seq FROM ESTR_ATRIBUTOS WHERE ESTR_ENTIDADE_ID = :entidade_id")
        next_seq = db.execute(query_max_seq, {"entidade_id": entidade_id}).scalar()
        
        query_cadastro = text("""
            INSERT INTO ESTR_ATRIBUTOS (ID_SEQ, ESTR_ENTIDADE_ID, NOME_ATRIBUTO, TIPO, LABEL, EXIBICAO, EDITAVEL, OBRIGATORIO)
            VALUES (:id_seq, :entidade_id, :nome_atributo, :tipo, :label, :exibicao, :editavel, :obrigatorio)
        """)
        db.execute(query_cadastro, {
            "id_seq": next_seq,
            "entidade_id": entidade_id,
            "nome_atributo": nome_atributo,
            "tipo": tipo,
            "label": label if label else None,
            "exibicao": exibicao == "true",
            "editavel": editavel == "true",
            "obrigatorio": obrigatorio == "true"
        })
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades/{entidade_id}/atributos?success_message=Atributo criado com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades/{entidade_id}/atributos?error_message=Erro ao criar atributo", 
            status_code=303
        )

@router.post("/{projeto_id}/entidades/{entidade_id}/atributos/editar/{atributo_id}")
def editar_atributo(
    projeto_id: int,
    entidade_id: int,
    atributo_id: int,
    nome_atributo: str = Form(...),
    tipo: str = Form(...),
    label: Optional[str] = Form(None),
    exibicao: Optional[str] = Form(None),
    editavel: Optional[str] = Form(None),
    obrigatorio: Optional[str] = Form(None),
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar = text("""
            SELECT ea.ID_SEQ FROM ESTR_ATRIBUTOS ea
            INNER JOIN ESTR_ENTIDADE ee ON ea.ESTR_ENTIDADE_ID = ee.ID
            INNER JOIN PROJETO p ON ee.PROJETO_ID = p.ID
            INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
            WHERE ea.ID_SEQ = :atributo_id AND ea.ESTR_ENTIDADE_ID = :entidade_id 
            AND ee.ID = :entidade_id AND p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar, {"atributo_id": atributo_id, "entidade_id": entidade_id, "projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/entidades/{entidade_id}/atributos?error_message=Atributo não encontrado", 
                status_code=303
            )
        
        query_checar_nome = text("""
            SELECT ID_SEQ FROM ESTR_ATRIBUTOS 
            WHERE NOME_ATRIBUTO = :nome AND ESTR_ENTIDADE_ID = :entidade_id AND ID_SEQ != :atributo_id
        """)
        if db.execute(query_checar_nome, {"nome": nome_atributo, "entidade_id": entidade_id, "atributo_id": atributo_id}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/entidades/{entidade_id}/atributos?error_message=Já existe um atributo com este nome", 
                status_code=303
            )
        
        # Se este atributo será de exibição, verificar se já existe outro (exceto ele mesmo)
        if exibicao == "true":
            query_checar_exibicao = text("""
                SELECT ID_SEQ FROM ESTR_ATRIBUTOS 
                WHERE EXIBICAO = true AND ESTR_ENTIDADE_ID = :entidade_id AND ID_SEQ != :atributo_id
            """)
            if db.execute(query_checar_exibicao, {"entidade_id": entidade_id, "atributo_id": atributo_id}).first():
                return RedirectResponse(
                    url=f"/projetos/{projeto_id}/entidades/{entidade_id}/atributos?error_message=Já existe um atributo de exibição para esta entidade", 
                    status_code=303
                )
        
        query_update = text("""
            UPDATE ESTR_ATRIBUTOS 
            SET NOME_ATRIBUTO = :nome_atributo, TIPO = :tipo, LABEL = :label, 
                EXIBICAO = :exibicao, EDITAVEL = :editavel, OBRIGATORIO = :obrigatorio
            WHERE ID_SEQ = :atributo_id AND ESTR_ENTIDADE_ID = :entidade_id
        """)
        db.execute(query_update, {
            "nome_atributo": nome_atributo,
            "tipo": tipo,
            "label": label if label else None,
            "exibicao": exibicao == "true",
            "editavel": editavel == "true",
            "obrigatorio": obrigatorio == "true",
            "atributo_id": atributo_id,
            "entidade_id": entidade_id
        })
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades/{entidade_id}/atributos?success_message=Atributo atualizado com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades/{entidade_id}/atributos?error_message=Erro ao atualizar atributo", 
            status_code=303
        )

@router.post("/{projeto_id}/entidades/{entidade_id}/atributos/deletar/{atributo_id}")
def deletar_atributo(
    projeto_id: int,
    entidade_id: int,
    atributo_id: int,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar = text("""
            SELECT ea.ID_SEQ FROM ESTR_ATRIBUTOS ea
            INNER JOIN ESTR_ENTIDADE ee ON ea.ESTR_ENTIDADE_ID = ee.ID
            INNER JOIN PROJETO p ON ee.PROJETO_ID = p.ID
            INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
            WHERE ea.ID_SEQ = :atributo_id AND ea.ESTR_ENTIDADE_ID = :entidade_id 
            AND ee.ID = :entidade_id AND p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar, {"atributo_id": atributo_id, "entidade_id": entidade_id, "projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/entidades/{entidade_id}/atributos?error_message=Atributo não encontrado", 
                status_code=303
            )
        
        query_delete = text("DELETE FROM ESTR_ATRIBUTOS WHERE ID_SEQ = :atributo_id AND ESTR_ENTIDADE_ID = :entidade_id")
        db.execute(query_delete, {"atributo_id": atributo_id, "entidade_id": entidade_id})
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades/{entidade_id}/atributos?success_message=Atributo excluído com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades/{entidade_id}/atributos?error_message=Erro ao excluir atributo", 
            status_code=303
        )