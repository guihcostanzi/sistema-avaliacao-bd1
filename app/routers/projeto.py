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
    
# Endpoints de perguntas

@router.get("/{projeto_id}/perguntas", response_class=HTMLResponse)
def listar_perguntas(
    projeto_id: int,
    request: Request,
    passo: int = 0,
    limite: int = 10,
    pergunta: Optional[str] = None,
    tipo: Optional[str] = None,
    modelo: Optional[str] = None,
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
    
    query_base = """
        SELECT p.ID, p.PERGUNTA, p.TIPO, p.MODELO, p.DATA_CADASTRO, p.ESTR_ENTIDADE_ID,
               ee.NOME as entidade_nome
        FROM PERGUNTA p 
        LEFT JOIN ESTR_ENTIDADE ee ON p.ESTR_ENTIDADE_ID = ee.ID
        WHERE p.PROJETO_ID = :projeto_id
    """
    parametros = {"projeto_id": projeto_id}
    
    if pergunta:
        query_base += " AND p.PERGUNTA ILIKE :pergunta"
        parametros["pergunta"] = f"%{pergunta}%"
    
    if tipo:
        query_base += " AND p.TIPO = :tipo"
        parametros["tipo"] = tipo
    
    if modelo:
        query_base += " AND p.MODELO = :modelo"
        parametros["modelo"] = modelo
    
    query_base += " ORDER BY p.DATA_CADASTRO DESC LIMIT :limite OFFSET :passo"
    parametros["limite"] = limite
    parametros["passo"] = passo
    
    query = text(query_base)
    result = db.execute(query, parametros)
    perguntas = result.fetchall()
    
    query_total = text("SELECT COUNT(*) as total FROM PERGUNTA WHERE PROJETO_ID = :projeto_id")
    total_perguntas = db.execute(query_total, {"projeto_id": projeto_id}).scalar()
    
    query_entidades = text("SELECT ID, NOME FROM ESTR_ENTIDADE WHERE PROJETO_ID = :projeto_id ORDER BY NOME")
    entidades = db.execute(query_entidades, {"projeto_id": projeto_id}).fetchall()
    
    total_paginas = (total_perguntas + limite - 1) // limite if total_perguntas > 0 else 1
    pagina_atual = (passo // limite) + 1

    contexto = {
        "request": request,
        "projeto": projeto,
        "perguntas": perguntas,
        "entidades": entidades,
        "total_perguntas": total_perguntas,
        "pagina_atual": pagina_atual,
        "total_paginas": total_paginas,
        "limite": limite,
        "filtro_pergunta": pergunta or "",
        "filtro_tipo": tipo or "",
        "filtro_modelo": modelo or "",
        "has_previous": passo > 0,
        "has_next": pagina_atual < total_paginas,
        "previous_page": max(1, pagina_atual - 1),
        "next_page": min(total_paginas, pagina_atual + 1),
        "success_message": success_message,
        "error_message": error_message,
        "usuario": current_user
    }
    
    return templates.TemplateResponse("perguntas.html", contexto)

@router.post("/{projeto_id}/perguntas/criar")
def criar_pergunta(
    projeto_id: int,
    pergunta: str = Form(...),
    tipo: str = Form(...),
    modelo: str = Form(...),
    estr_entidade_id: Optional[int] = Form(None),
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
        
        if tipo == "entidade" and not estr_entidade_id:
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/perguntas?error_message=Entidade é obrigatória para perguntas do tipo Entidade", 
                status_code=303
            )
        
        if tipo != "entidade":
            estr_entidade_id = None
        
        query_cadastro = text("""
            INSERT INTO PERGUNTA (PROJETO_ID, ESTR_ENTIDADE_ID, PERGUNTA, TIPO, MODELO)
            VALUES (:projeto_id, :estr_entidade_id, :pergunta, :tipo, :modelo)
        """)
        db.execute(query_cadastro, {
            "projeto_id": projeto_id,
            "estr_entidade_id": estr_entidade_id,
            "pergunta": pergunta,
            "tipo": tipo,
            "modelo": modelo
        })
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/perguntas?success_message=Pergunta criada com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/perguntas?error_message=Erro ao criar pergunta", 
            status_code=303
        )

@router.post("/{projeto_id}/perguntas/editar/{pergunta_id}")
def editar_pergunta(
    projeto_id: int,
    pergunta_id: int,
    pergunta: str = Form(...),
    tipo: str = Form(...),
    modelo: str = Form(...),
    estr_entidade_id: Optional[int] = Form(None),
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar = text("""
            SELECT p.ID FROM PERGUNTA p
            INNER JOIN PROJETO pr ON p.PROJETO_ID = pr.ID
            INNER JOIN USUARIO_PROJETO up ON pr.ID = up.PROJETO_ID 
            WHERE p.ID = :pergunta_id AND pr.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar, {"pergunta_id": pergunta_id, "projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/perguntas?error_message=Pergunta não encontrada", 
                status_code=303
            )
        
        if tipo == "entidade" and not estr_entidade_id:
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/perguntas?error_message=Entidade é obrigatória para perguntas do tipo Entidade", 
                status_code=303
            )
        
        if tipo != "entidade":
            estr_entidade_id = None
        
        query_update = text("""
            UPDATE PERGUNTA 
            SET PERGUNTA = :pergunta, TIPO = :tipo, MODELO = :modelo, ESTR_ENTIDADE_ID = :estr_entidade_id
            WHERE ID = :pergunta_id
        """)
        db.execute(query_update, {
            "pergunta": pergunta,
            "tipo": tipo,
            "modelo": modelo,
            "estr_entidade_id": estr_entidade_id,
            "pergunta_id": pergunta_id
        })
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/perguntas?success_message=Pergunta atualizada com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/perguntas?error_message=Erro ao atualizar pergunta", 
            status_code=303
        )

@router.post("/{projeto_id}/perguntas/deletar/{pergunta_id}")
def deletar_pergunta(
    projeto_id: int,
    pergunta_id: int,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar = text("""
            SELECT p.ID FROM PERGUNTA p
            INNER JOIN PROJETO pr ON p.PROJETO_ID = pr.ID
            INNER JOIN USUARIO_PROJETO up ON pr.ID = up.PROJETO_ID 
            WHERE p.ID = :pergunta_id AND pr.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar, {"pergunta_id": pergunta_id, "projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/perguntas?error_message=Pergunta não encontrada", 
                status_code=303
            )
        
        query_delete = text("DELETE FROM PERGUNTA WHERE ID = :pergunta_id")
        db.execute(query_delete, {"pergunta_id": pergunta_id})
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/perguntas?success_message=Pergunta excluída com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/perguntas?error_message=Erro ao excluir pergunta", 
            status_code=303
        )
    
# Endpoints de instâncias

@router.get("/{projeto_id}/entidades/{entidade_id}/instancias", response_class=HTMLResponse)
def listar_instancias(
    projeto_id: int,
    entidade_id: int,
    request: Request,
    passo: int = 0,
    limite: int = 10,
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
    
    query_atributos = text("""
        SELECT ID_SEQ, NOME_ATRIBUTO, TIPO, LABEL, EXIBICAO, EDITAVEL, OBRIGATORIO
        FROM ESTR_ATRIBUTOS 
        WHERE ESTR_ENTIDADE_ID = :entidade_id
        ORDER BY ID_SEQ
    """)
    todos_atributos = db.execute(query_atributos, {"entidade_id": entidade_id}).fetchall()
    
    atributo_exibicao = None
    outros_atributos = []
    
    for atributo in todos_atributos:
        if atributo.exibicao:
            atributo_exibicao = atributo
        else:
            outros_atributos.append(atributo)
    
    query_base = """
        SELECT e.ID_SEQ, e.DATA_CADASTRO
        FROM ENTIDADE e
        WHERE e.ESTR_ENTIDADE_ID = :entidade_id
        ORDER BY e.DATA_CADASTRO DESC 
        LIMIT :limite OFFSET :passo
    """
    
    result = db.execute(text(query_base), {"entidade_id": entidade_id, "limite": limite, "passo": passo})
    entidades_base = result.fetchall()
    
    instancias = []
    for entidade_row in entidades_base:
        instancia = {
            "id_seq": entidade_row.id_seq,
            "data_cadastro": entidade_row.data_cadastro
        }
        
        for atributo in todos_atributos:
            query_valor = text("""
                SELECT VALOR FROM ATRIBUTOS 
                WHERE ESTR_ENTIDADE_ID = :entidade_id 
                AND ENTIDADE_ID_SEQ = :entidade_seq 
                AND ESTR_ATRIBUTO_ID_SEQ = :atributo_seq
            """)
            valor_result = db.execute(query_valor, {
                "entidade_id": entidade_id,
                "entidade_seq": entidade_row.id_seq,
                "atributo_seq": atributo.id_seq
            }).first()
            
            instancia[f"valor_{atributo.nome_atributo}"] = valor_result.valor if valor_result else None
        
        instancias.append(instancia)
    
    query_total = text("SELECT COUNT(*) as total FROM ENTIDADE WHERE ESTR_ENTIDADE_ID = :entidade_id")
    total_instancias = db.execute(query_total, {"entidade_id": entidade_id}).scalar()
    
    total_paginas = (total_instancias + limite - 1) // limite if total_instancias > 0 else 1
    pagina_atual = (passo // limite) + 1

    contexto = {
        "request": request,
        "projeto": projeto,
        "entidade": entidade,
        "instancias": instancias,
        "todos_atributos": todos_atributos,
        "atributo_exibicao": atributo_exibicao,
        "outros_atributos": outros_atributos,
        "total_instancias": total_instancias,
        "pagina_atual": pagina_atual,
        "total_paginas": total_paginas,
        "limite": limite,
        "has_previous": passo > 0,
        "has_next": pagina_atual < total_paginas,
        "previous_page": max(1, pagina_atual - 1),
        "next_page": min(total_paginas, pagina_atual + 1),
        "success_message": success_message,
        "error_message": error_message,
        "usuario": current_user
    }
    
    return templates.TemplateResponse("instancias.html", contexto)

@router.post("/{projeto_id}/entidades/{entidade_id}/instancias/criar")
async def criar_instancia(
    projeto_id: int,
    entidade_id: int,
    request: Request,
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
        
        query_max_seq = text("SELECT COALESCE(MAX(ID_SEQ), 0) + 1 as next_seq FROM ENTIDADE WHERE ESTR_ENTIDADE_ID = :entidade_id")
        next_seq = db.execute(query_max_seq, {"entidade_id": entidade_id}).scalar()
        
        query_criar_entidade = text("INSERT INTO ENTIDADE (ID_SEQ, ESTR_ENTIDADE_ID) VALUES (:id_seq, :entidade_id)")
        db.execute(query_criar_entidade, {"id_seq": next_seq, "entidade_id": entidade_id})
        
        query_atributos = text("""
            SELECT ID_SEQ, NOME_ATRIBUTO, OBRIGATORIO
            FROM ESTR_ATRIBUTOS 
            WHERE ESTR_ENTIDADE_ID = :entidade_id
        """)
        atributos = db.execute(query_atributos, {"entidade_id": entidade_id}).fetchall()
        
        form_data = await request.form()
        
        for atributo in atributos:
            valor = form_data.get(atributo.nome_atributo)
            
            if atributo.obrigatorio and not valor:
                return RedirectResponse(
                    url=f"/projetos/{projeto_id}/entidades/{entidade_id}/instancias?error_message=Campo {atributo.nome_atributo} é obrigatório", 
                    status_code=303
                )
            
            if valor:
                query_inserir_valor = text("""
                    INSERT INTO ATRIBUTOS (ESTR_ENTIDADE_ID, ENTIDADE_ID_SEQ, ESTR_ATRIBUTO_ID_SEQ, VALOR)
                    VALUES (:entidade_id, :entidade_seq, :atributo_seq, :valor)
                """)
                db.execute(query_inserir_valor, {
                    "entidade_id": entidade_id,
                    "entidade_seq": next_seq,
                    "atributo_seq": atributo.id_seq,
                    "valor": valor
                })
        
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades/{entidade_id}/instancias?success_message=Instância criada com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades/{entidade_id}/instancias?error_message=Erro ao criar instância", 
            status_code=303
        )

@router.post("/{projeto_id}/entidades/{entidade_id}/instancias/editar/{instancia_id}")
async def editar_instancia(
    projeto_id: int,
    entidade_id: int,
    instancia_id: int,
    request: Request,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar = text("""
            SELECT e.ID_SEQ FROM ENTIDADE e
            INNER JOIN ESTR_ENTIDADE ee ON e.ESTR_ENTIDADE_ID = ee.ID
            INNER JOIN PROJETO p ON ee.PROJETO_ID = p.ID
            INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
            WHERE e.ID_SEQ = :instancia_id AND e.ESTR_ENTIDADE_ID = :entidade_id 
            AND ee.ID = :entidade_id AND p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar, {"instancia_id": instancia_id, "entidade_id": entidade_id, "projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/entidades/{entidade_id}/instancias?error_message=Instância não encontrada", 
                status_code=303
            )
        
        query_atributos = text("""
            SELECT ID_SEQ, NOME_ATRIBUTO, OBRIGATORIO, EDITAVEL
            FROM ESTR_ATRIBUTOS 
            WHERE ESTR_ENTIDADE_ID = :entidade_id
        """)
        atributos = db.execute(query_atributos, {"entidade_id": entidade_id}).fetchall()
        
        form_data = await request.form()
        
        for atributo in atributos:
            if not atributo.editavel:
                continue
                
            valor = form_data.get(atributo.nome_atributo)
            
            if atributo.obrigatorio and not valor:
                return RedirectResponse(
                    url=f"/projetos/{projeto_id}/entidades/{entidade_id}/instancias?error_message=Campo {atributo.nome_atributo} é obrigatório", 
                    status_code=303
                )
            
            query_delete_valor = text("""
                DELETE FROM ATRIBUTOS 
                WHERE ESTR_ENTIDADE_ID = :entidade_id 
                AND ENTIDADE_ID_SEQ = :instancia_id 
                AND ESTR_ATRIBUTO_ID_SEQ = :atributo_seq
            """)
            db.execute(query_delete_valor, {
                "entidade_id": entidade_id,
                "instancia_id": instancia_id,
                "atributo_seq": atributo.id_seq
            })
            
            if valor:
                query_inserir_valor = text("""
                    INSERT INTO ATRIBUTOS (ESTR_ENTIDADE_ID, ENTIDADE_ID_SEQ, ESTR_ATRIBUTO_ID_SEQ, VALOR)
                    VALUES (:entidade_id, :instancia_id, :atributo_seq, :valor)
                """)
                db.execute(query_inserir_valor, {
                    "entidade_id": entidade_id,
                    "instancia_id": instancia_id,
                    "atributo_seq": atributo.id_seq,
                    "valor": valor
                })
        
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades/{entidade_id}/instancias?success_message=Instância atualizada com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades/{entidade_id}/instancias?error_message=Erro ao atualizar instância", 
            status_code=303
        )

@router.post("/{projeto_id}/entidades/{entidade_id}/instancias/deletar/{instancia_id}")
def deletar_instancia(
    projeto_id: int,
    entidade_id: int,
    instancia_id: int,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar = text("""
            SELECT e.ID_SEQ FROM ENTIDADE e
            INNER JOIN ESTR_ENTIDADE ee ON e.ESTR_ENTIDADE_ID = ee.ID
            INNER JOIN PROJETO p ON ee.PROJETO_ID = p.ID
            INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
            WHERE e.ID_SEQ = :instancia_id AND e.ESTR_ENTIDADE_ID = :entidade_id 
            AND ee.ID = :entidade_id AND p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar, {"instancia_id": instancia_id, "entidade_id": entidade_id, "projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/entidades/{entidade_id}/instancias?error_message=Instância não encontrada", 
                status_code=303
            )
        
        query_delete = text("DELETE FROM ENTIDADE WHERE ID_SEQ = :instancia_id AND ESTR_ENTIDADE_ID = :entidade_id")
        db.execute(query_delete, {"instancia_id": instancia_id, "entidade_id": entidade_id})
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades/{entidade_id}/instancias?success_message=Instância excluída com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/entidades/{entidade_id}/instancias?error_message=Erro ao excluir instância", 
            status_code=303
        )
    
# Endpoints de valores padrão das perguntas

@router.get("/{projeto_id}/perguntas/{pergunta_id}/valores-padrao", response_class=HTMLResponse)
def listar_valores_padrao_pergunta(
    projeto_id: int,
    pergunta_id: int,
    request: Request,
    success_message: Optional[str] = None,
    error_message: Optional[str] = None,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    query_verificar = text("""
        SELECT p.ID, p.PERGUNTA, p.TIPO, p.MODELO, pr.NOME as projeto_nome
        FROM PERGUNTA p
        INNER JOIN PROJETO pr ON p.PROJETO_ID = pr.ID
        INNER JOIN USUARIO_PROJETO up ON pr.ID = up.PROJETO_ID 
        WHERE p.ID = :pergunta_id AND pr.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
    """)
    resultado = db.execute(query_verificar, {"pergunta_id": pergunta_id, "projeto_id": projeto_id, "usuario_id": current_user['id']}).first()
    
    if not resultado:
        return RedirectResponse(url="/projetos/?error_message=Pergunta não encontrada", status_code=303)
    
    pergunta = {
        "id": resultado.id,
        "pergunta": resultado.pergunta,
        "tipo": resultado.tipo,
        "modelo": resultado.modelo
    }
    projeto = {"id": projeto_id, "nome": resultado.projeto_nome}
    
    query_valores = text("""
        SELECT PERGUNTA_ID, VALOR
        FROM VALORES_PADRAO 
        WHERE PERGUNTA_ID = :pergunta_id
        ORDER BY VALOR
    """)
    valores_padrao = db.execute(query_valores, {"pergunta_id": pergunta_id}).fetchall()

    contexto = {
        "request": request,
        "projeto": projeto,
        "pergunta": pergunta,
        "valores_padrao": valores_padrao,
        "success_message": success_message,
        "error_message": error_message,
        "usuario": current_user
    }
    
    return templates.TemplateResponse("valores_padrao_pergunta.html", contexto)

@router.post("/{projeto_id}/perguntas/{pergunta_id}/valores-padrao/criar")
def criar_valor_padrao_pergunta(
    projeto_id: int,
    pergunta_id: int,
    valor: str = Form(...),
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar = text("""
            SELECT p.ID, p.TIPO FROM PERGUNTA p
            INNER JOIN PROJETO pr ON p.PROJETO_ID = pr.ID
            INNER JOIN USUARIO_PROJETO up ON pr.ID = up.PROJETO_ID 
            WHERE p.ID = :pergunta_id AND pr.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        pergunta_result = db.execute(query_verificar, {"pergunta_id": pergunta_id, "projeto_id": projeto_id, "usuario_id": current_user['id']}).first()
        
        if not pergunta_result:
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/perguntas?error_message=Pergunta não encontrada", 
                status_code=303
            )
        
        # Validação por tipo
        valor_limpo = valor.strip()
        tipo_pergunta = pergunta_result.tipo
        
        if tipo_pergunta == 'numero':
            try:
                float(valor_limpo)
            except ValueError:
                return RedirectResponse(
                    url=f"/projetos/{projeto_id}/perguntas/{pergunta_id}/valores-padrao?error_message=Para perguntas do tipo número, digite apenas valores numéricos", 
                    status_code=303
                )
        elif tipo_pergunta == 'email':
            import re
            email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
            if not re.match(email_regex, valor_limpo):
                return RedirectResponse(
                    url=f"/projetos/{projeto_id}/perguntas/{pergunta_id}/valores-padrao?error_message=Para perguntas do tipo email, digite um email válido", 
                    status_code=303
                )
        elif tipo_pergunta == 'data':
            from datetime import datetime
            try:
                datetime.strptime(valor_limpo, '%Y-%m-%d')
            except ValueError:
                return RedirectResponse(
                    url=f"/projetos/{projeto_id}/perguntas/{pergunta_id}/valores-padrao?error_message=Para perguntas do tipo data, use o formato YYYY-MM-DD", 
                    status_code=303
                )
        elif tipo_pergunta == 'booleano':
            if valor_limpo not in ['true', 'false']:
                return RedirectResponse(
                    url=f"/projetos/{projeto_id}/perguntas/{pergunta_id}/valores-padrao?error_message=Para perguntas do tipo booleano, selecione apenas Sim ou Não", 
                    status_code=303
                )
        
        # Verificar se já existe este valor
        query_existe = text("SELECT PERGUNTA_ID FROM VALORES_PADRAO WHERE PERGUNTA_ID = :pergunta_id AND VALOR = :valor")
        if db.execute(query_existe, {"pergunta_id": pergunta_id, "valor": valor_limpo}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/perguntas/{pergunta_id}/valores-padrao?error_message=Este valor já existe", 
                status_code=303
            )
        
        query_insert = text("INSERT INTO VALORES_PADRAO (PERGUNTA_ID, VALOR) VALUES (:pergunta_id, :valor)")
        db.execute(query_insert, {"pergunta_id": pergunta_id, "valor": valor_limpo})
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/perguntas/{pergunta_id}/valores-padrao?success_message=Valor padrão criado com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/perguntas/{pergunta_id}/valores-padrao?error_message=Erro ao criar valor padrão", 
            status_code=303
        )

@router.post("/{projeto_id}/perguntas/{pergunta_id}/valores-padrao/deletar")
def deletar_valor_padrao_pergunta(
    projeto_id: int,
    pergunta_id: int,
    valor: str = Form(...),
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    try:
        query_verificar = text("""
            SELECT p.ID FROM PERGUNTA p
            INNER JOIN PROJETO pr ON p.PROJETO_ID = pr.ID
            INNER JOIN USUARIO_PROJETO up ON pr.ID = up.PROJETO_ID 
            WHERE p.ID = :pergunta_id AND pr.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar, {"pergunta_id": pergunta_id, "projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return RedirectResponse(
                url=f"/projetos/{projeto_id}/perguntas?error_message=Pergunta não encontrada", 
                status_code=303
            )
        
        query_delete = text("DELETE FROM VALORES_PADRAO WHERE PERGUNTA_ID = :pergunta_id AND VALOR = :valor")
        db.execute(query_delete, {"pergunta_id": pergunta_id, "valor": valor})
        db.commit()
        
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/perguntas/{pergunta_id}/valores-padrao?success_message=Valor padrão removido com sucesso", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url=f"/projetos/{projeto_id}/perguntas/{pergunta_id}/valores-padrao?error_message=Erro ao remover valor padrão", 
            status_code=303
        )