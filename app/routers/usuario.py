from typing import Optional
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text

# Importa os schemas que criamos e a conexão com o banco
from app.core import security
from app.db.database import get_db

# Cria o router específico para usuários
router = APIRouter()

# Configurar templates
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse, name="pagina_usuarios")
def pagina_usuarios(
    request: Request,
    passo: int = 0,
    limite: int = 10,
    nome: Optional[str] = None,
    email: Optional[str] = None,
    success: Optional[str] = None,
    error: Optional[str] = None,
    db: Session = Depends(get_db)
):
    
    # Query base usando 1 = 1 para facilitar a adição de condições
    query_base = "SELECT id, nome, email FROM usuario WHERE 1=1"
    parametros = {}
    
    # Adiciona filtros se fornecidos
    if nome:
        query_base += " AND nome ILIKE :nome"
        parametros["nome"] = f"%{nome}%"
    
    if email:
        query_base += " AND email ILIKE :email"
        parametros["email"] = f"%{email}%"
    
    # Adiciona ordenação e paginação
    query_base += " ORDER BY nome LIMIT :limite OFFSET :passo"
    parametros["limite"] = limite
    parametros["passo"] = passo
    
    # Executa a query
    query = text(query_base)
    result = db.execute(query, parametros)
    usuarios = result.fetchall()
    
    # Conta o total de usuários na tabela
    query_total = text("SELECT COUNT(*) as total FROM usuario")
    total_usuarios = db.execute(query_total).scalar()
    
    # Calcula paginação
    total_paginas = (total_usuarios + limite - 1) // limite if total_usuarios > 0 else 1
    pagina_atual = (passo // limite) + 1

    contexto ={
        "request": request,
        "usuarios": usuarios,
        "total_usuarios": total_usuarios,
        "pagina_atual": pagina_atual,
        "total_paginas": total_paginas,
        "limite": limite,
        "filtro_nome": nome or "",
        "filtro_email": email or "",
        "has_previous": passo > 0,
        "has_next": pagina_atual < total_paginas,
        "previous_page": max(1, pagina_atual - 1),
        "next_page": min(total_paginas, pagina_atual + 1),
        "success_message": success,
        "error_message": error
    }
    
    return templates.TemplateResponse("usuarios.html", contexto)

@router.post("/criar")
def criar_usuario(
    nome: str = Form(...),
    email: str = Form(...),
    senha: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        # Verifica se o e-mail já existe para evitar duplicatas
        query_checar_email = text("SELECT id FROM usuario WHERE email = :email")
        if db.execute(query_checar_email, {"email": email}).first():
            return RedirectResponse(
                url="/usuarios/?error=E-mail já cadastrado.", 
                status_code=303
            )
        
        # Gera o hash da senha antes de salvar
        senha_hash = security.get_senha_hash(senha)
        
        # Insere o novo usuário no banco de dados
        query_cadastro = text("INSERT INTO usuario (nome, email, senha) VALUES (:nome, :email, :senha)")
        db.execute(query_cadastro, {"nome": nome, "email": email, "senha": senha_hash})
        db.commit()
        
        return RedirectResponse(
            url="/usuarios/?success=Usuário criado com sucesso!", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url="/usuarios/?error=Erro ao criar usuário.", 
            status_code=303
        )

@router.post("/editar/{usuario_id}")
def editar_usuario(
    usuario_id: int,
    nome: str = Form(...),
    email: str = Form(...),
    senha: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        # Verifica se o usuário existe
        query_verificar = text("SELECT id FROM usuario WHERE id = :id")
        if not db.execute(query_verificar, {"id": usuario_id}).first():
            return RedirectResponse(
                url="/usuarios/?error=Usuário não encontrado!", 
                status_code=303
            )
        
        # Verifica se o novo e-mail já existe em outro usuário
        query_checar_email = text("SELECT id FROM usuario WHERE email = :email AND id != :id")
        if db.execute(query_checar_email, {"email": email, "id": usuario_id}).first():
            return RedirectResponse(
                url="/usuarios/?error=E-mail já cadastrado para outro usuário!", 
                status_code=303
            )
        
        # Atualiza o usuário
        if senha and senha.strip():  # Se senha foi fornecida e não está vazia
            senha_hash = security.get_senha_hash(senha)
            query_update = text("UPDATE usuario SET nome = :nome, email = :email, senha = :senha WHERE id = :id")
            db.execute(query_update, {"nome": nome, "email": email, "senha": senha_hash, "id": usuario_id})
        else:
            query_update = text("UPDATE usuario SET nome = :nome, email = :email WHERE id = :id")
            db.execute(query_update, {"nome": nome, "email": email, "id": usuario_id})
        
        db.commit()
        
        return RedirectResponse(
            url="/usuarios/?success=Usuário atualizado com sucesso!", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url="/usuarios/?error=Erro ao atualizar usuário!", 
            status_code=303
        )

@router.post("/deletar/{usuario_id}")
def deletar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    try:
        # Verifica se o usuário existe
        query_verificar = text("SELECT id FROM usuario WHERE id = :id")
        if not db.execute(query_verificar, {"id": usuario_id}).first():
            return RedirectResponse(
                url="/usuarios/?error=Usuário não encontrado!", 
                status_code=303
            )
        
        # Deleta o usuário
        query_delete = text("DELETE FROM usuario WHERE id = :id")
        db.execute(query_delete, {"id": usuario_id})
        db.commit()
        
        return RedirectResponse(
            url="/usuarios/?success=Usuário excluído com sucesso!", 
            status_code=303
        )
        
    except Exception as e:
        return RedirectResponse(
            url="/usuarios/?error=Erro ao excluir usuário!", 
            status_code=303
        )