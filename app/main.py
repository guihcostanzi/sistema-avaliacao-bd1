from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Importação de router (colocando 'app.' pois está dentro da pasta app)
from app.routers import avaliacoes 

# --- Configuração da Aplicação ---
app = FastAPI(
    title="Sistema de Avaliações",
    description="Uma API para criar e gerenciar avaliações, agora de forma organizada!",
    version="0.2.0",
)

# Configuração de arquivos estáticos e templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Incluir os Roteadores ---

# Esta linha adiciona todas as rotas de 'avaliacoes.py' à sua aplicação principal
app.include_router(
    avaliacoes.router, 
    prefix="/api",        # Adiciona '/api' na frente de todas as rotas do router
    tags=["Avaliações"]   # Agrupa estas rotas na documentação /docs
)

# --- Endpoints da Página Principal (Frontend) ---
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    context = {
        "request": request,
        "title": "Sistema de Avaliações",
        "welcome_message": "Bem-vindo ao nosso Sistema de Avaliações!"
    }
    return templates.TemplateResponse("index.html", context)