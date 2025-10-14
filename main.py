from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Cria a instância da aplicação FastAPI
app = FastAPI(
    title="API de Sistema de Avaliações",
    description="Uma API para criar e gerenciar avaliações.",
    version="0.1.0",
)

# 1. Monta o diretório 'static' para servir arquivos estáticos (CSS, JS, imagens)
# A URL para acessar esses arquivos será, por exemplo, http://localhost:8000/static/css/style.css
app.mount("/static", StaticFiles(directory="static"), name="static")

# 2. Configura o diretório de templates para o Jinja2
# O FastAPI vai procurar os arquivos HTML na pasta 'templates'
templates = Jinja2Templates(directory="templates")


# 3. Modifica o endpoint para renderizar o HTML
# response_class=HTMLResponse diz ao navegador para interpretar a resposta como HTML
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    """
    Endpoint raiz que renderiza e retorna a página principal em HTML.
    """
    # Dados que você quer passar para o template
    context = {
        "request": request,
        "title": "Sistema de Avaliações",
        "welcome_message": "Bem-vindo ao nosso Sistema de Avaliações!"
    }
    
    # Renderiza o template 'index.html' com o contexto
    return templates.TemplateResponse("index.html", context)