from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse

# Importa a instância centralizada do motor de templates
from app.templating import templates

# Cria uma instância do APIRouter
router = APIRouter()

# Rota GET para exibir a página de login
@router.get("/login", response_class=HTMLResponse)
def pagina_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


# Rota POST para processar o formulário de login
@router.post("/login", response_class=HTMLResponse)
def processar_login(request: Request, usuario: str = Form(), senha: str = Form()):
    if usuario == "admin" and senha == "senha123":

        # Armazena informações do usuário na sessão
        request.session['usuario'] = {'username': usuario, 'role': 'admin'}

        return RedirectResponse(url="/home", status_code=302)
    else:
        context = {
            "request": request,
            "error_message": "Usuário ou senha inválidos."
        }
        return templates.TemplateResponse("login.html", context)

# Rota GET para logout
@router.get("/logout")
def logout(request: Request):

    # Limpa a sessão
    request.session.clear()

    return RedirectResponse(url="/login", status_code=302)