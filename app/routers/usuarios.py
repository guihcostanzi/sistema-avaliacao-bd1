from fastapi import APIRouter, Depends, status, HTTPException
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
    
    # --- INÍCIO DA NOSSA DEPURAÇÃO ---
    # Vamos imprimir o valor, o tipo e o tamanho da senha que a função recebeu.
    print("--- DADOS DE DEPURAÇÃO DA SENHA ---")
    print(f"VALOR RECEBIDO: {usuario.senha}")
    print(f"TIPO DA VARIÁVEL: {type(usuario.senha)}")
    print(f"TAMANHO DA STRING: {len(usuario.senha)}")
    print("------------------------------------")
    # --- FIM DA DEPURAÇÃO ---

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