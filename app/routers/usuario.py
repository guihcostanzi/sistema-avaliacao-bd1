from typing import List, Optional
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

# Importa os schemas que criamos e a conexão com o banco
from app.schemas import usuario as usuario_schema
from app.core import security
from app.db.database import SessionLocal
from app.db.database import get_db

# Cria o router específico para usuários
router = APIRouter()

@router.post("/", response_model=usuario_schema.Usuario, status_code=status.HTTP_201_CREATED)
def criar_usuario(usuario: usuario_schema.UsuarioCreate, db: Session = Depends(get_db)):
    """
    Endpoint para criar um novo usuário.
    """
    # Verifica se o e-mail já existe para evitar duplicatas
    query_checar_email = text("SELECT id FROM usuario WHERE email = :email")
    if db.execute(query_checar_email, {"email": usuario.email}).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")

    # Gera o hash da senha antes de salvar
    senha_hash = security.get_senha_hash(usuario.senha)
    
    # Insere o novo usuário no banco de dados
    query_cadastro = text("INSERT INTO usuario (nome, email, senha) VALUES (:nome, :email, :senha) RETURNING id")
    result = db.execute(query_cadastro, {"nome": usuario.nome, "email": usuario.email, "senha": senha_hash})
    db.commit()
    
    # Obtém o ID do novo usuário criado
    novo_id = result.scalar_one()
    
    # Retorna o usuário criado, seguindo o schema de resposta segura
    return usuario_schema.Usuario(id=novo_id, nome=usuario.nome, email=usuario.email)

@router.get("/", response_model=List[usuario_schema.Usuario])
def listar_usuarios(
    passo: int = Query(0, ge=0, description="Número de registros para pular"),
    limite: int = Query(100, ge=1, le=1000, description="Número máximo de registros"),
    nome: Optional[str] = Query(None, description="Filtrar por nome"),
    email: Optional[str] = Query(None, description="Filtrar por email"),
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
    
    # Converte para lista de objetos Usuario
    return [
        usuario_schema.Usuario(id=row.id, nome=row.nome, email=row.email)
        for row in usuarios
    ]

@router.get("/{usuario_id}", response_model=usuario_schema.Usuario)
def obter_usuario(usuario_id: int, db: Session = Depends(get_db)):
   
    # Select pelo ID do usuário
    query = text("SELECT id, nome, email FROM usuario WHERE id = :id")
    result = db.execute(query, {"id": usuario_id}).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    return usuario_schema.Usuario(id=result.id, nome=result.nome, email=result.email)

@router.put("/{usuario_id}", response_model=usuario_schema.Usuario)
def atualizar_usuario(
    usuario_id: int, 
    usuario_update: usuario_schema.UsuarioUpdate, 
    db: Session = Depends(get_db)
):
  
    # Verifica se o usuário existe
    query_verificar = text("SELECT id FROM usuario WHERE id = :id")
    if not db.execute(query_verificar, {"id": usuario_id}).first():
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    # Verifica se o novo e-mail já existe em outro usuário
    if usuario_update.email:
        query_checar_email = text("SELECT id FROM usuario WHERE email = :email AND id != :id")
        if db.execute(query_checar_email, {"email": usuario_update.email, "id": usuario_id}).first():
            raise HTTPException(status_code=400, detail="E-mail já cadastrado para outro usuário.")
    
    # Constrói a query de atualização dinamicamente
    campos_update = []
    parametros = {"id": usuario_id}
    
    if usuario_update.nome is not None:
        campos_update.append("nome = :nome")
        parametros["nome"] = usuario_update.nome
    
    if usuario_update.email is not None:
        campos_update.append("email = :email")
        parametros["email"] = usuario_update.email
    
    if usuario_update.senha is not None:
        campos_update.append("senha = :senha")
        parametros["senha"] = security.get_senha_hash(usuario_update.senha)
    
    if not campos_update:
        raise HTTPException(status_code=400, detail="Nenhum campo fornecido para atualização.")
    
    # Executa a atualização via UPDATE
    query_update = text(f"UPDATE usuario SET {', '.join(campos_update)} WHERE id = :id")
    db.execute(query_update, parametros)
    db.commit()
    
    # Retorna o usuário atualizado
    return obter_usuario(usuario_id, db)

@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def deletar_usuario(usuario_id: int, db: Session = Depends(get_db)):
 
    # Verifica se o usuário existe
    query_verificar = text("SELECT id FROM usuario WHERE id = :id")
    if not db.execute(query_verificar, {"id": usuario_id}).first():
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    # Deleta o usuário
    query_delete = text("DELETE FROM usuario WHERE id = :id")
    db.execute(query_delete, {"id": usuario_id})
    db.commit()
    
    return None

@router.get("/count/total")
def contar_usuarios(db: Session = Depends(get_db)):
    
    # Conta o total de usuários na tabela
    query = text("SELECT COUNT(*) as total FROM usuario")
    result = db.execute(query).scalar()
    
    return {"total": result}