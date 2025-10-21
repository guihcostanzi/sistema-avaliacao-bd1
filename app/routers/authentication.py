from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi import Depends


# Importa a instância centralizada do motor de templates
from app.templating import templates

# Importa a dependência para obter a sessão do banco de dados
from app.db.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text

# Importando security para verificação de senha
from app.core import security

# Cria uma instância do APIRouter
router = APIRouter()

# Rota GET para exibir a página de login
@router.get("/login", response_class=HTMLResponse)
def pagina_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# Rota POST para processar o formulário de login
@router.post("/login", response_class=HTMLResponse)
def processar_login(
    request: Request, 
    email: str = Form(), 
    senha: str = Form(),
    db: Session = Depends(get_db)
):
    # Define a query e tenta buscar o usuário no banco de dados
    query = text("SELECT id, nome, email, senha FROM usuario WHERE email = :email")
    usuario_db = db.execute(query, {"email": email}).mappings().first()

    # Verifica se o usuário existe e se a senha está correta
    if not usuario_db or not security.verificar_Senha(senha, usuario_db['senha']):
        context = {"request": request, "error_message": "E-mail ou senha inválidos."}

        # Se a verificação falhar, retorna à página de login com uma mensagem de erro
        return templates.TemplateResponse("login.html", context, status_code=401)
    
    # Se a verificação for bem-sucedida, cria a sessão
    request.session['usuario'] = {'id': usuario_db['id'], 'nome': usuario_db['nome'], 'email': usuario_db['email']}
    
    # Redireciona para a página principal
    return RedirectResponse(url="/home", status_code=302)

# Rota GET para logout
@router.get("/logout")
def logout(request: Request):

    # Limpa a sessão
    request.session.clear()

    return RedirectResponse(url="/auth/login", status_code=302)