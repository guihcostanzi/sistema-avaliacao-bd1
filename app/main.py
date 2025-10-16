from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Depends

# Importa o middleware de sessão
from starlette.middleware.sessions import SessionMiddleware

# Importa a dependência de segurança, que verifica se o usuário está autenticado
from app.dependencies import get_usuario_autenticado

# Importação de routers (colocando 'app.' pois estão dentro da pasta app)
from app.routers import usuarios, authentication

# --- Configuração da Aplicação ---
app = FastAPI(
    title="Sistema de Avaliações",
    description="Uma API para criar e gerenciar avaliações, agora de forma organizada!",
    version="0.2.0",
)

# Adiciona o middleware de sessão ao aplicativo
app.add_middleware(
    SessionMiddleware,
    secret_key="aaasdada"
)

# Configuração de arquivos estáticos e templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Incluir os Roteadores ---

app.include_router(
    authentication.router, 
    prefix="",
    tags=["Autenticação"]   # Agrupa estas rotas na documentação /docs
)

app.include_router(
    usuarios.router, 
    prefix="/usuarios",        
    tags=["Usuarios"]   
)

# --- Endpoints da Página Principal (Frontend) ---
@app.get("/home", response_class=HTMLResponse)
def read_root(request: Request, usuario: dict = Depends(get_usuario_autenticado)):
    context = {
        "request": request,
        "usuario": usuario,
        "title": "Sistema de Avaliações",
        "welcome_message": "Bem-vindo ao nosso Sistema de Avaliações!"
    }
    return templates.TemplateResponse("index.html", context)