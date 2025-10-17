from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Depends
from starlette.exceptions import HTTPException as StarletteHTTPException

# Importa a instância centralizada do motor de templates
from app.templating import templates as templates_instance
 
# Importa o middleware de sessão
from starlette.middleware.sessions import SessionMiddleware

# Importa a dependência de segurança, que verifica se o usuário está autenticado
from app.session_dependencies import get_usuario_autenticado

# Importação de routers (colocando 'app.' pois estão dentro da pasta app)
from app.routers import usuario, authentication

# --- Configuração da Aplicação ---
app = FastAPI(
    title="Sistema de Avaliações",
    description="Uma API para criar e gerenciar avaliações, agora de forma organizada!",
    version="0.2.0",
)

@app.middleware("http")
async def redirecionar_se_nao_autenticado(request: Request, call_next):
   
    # Define uma lista de caminhos que NÃO precisam de autenticação.
    allowed_paths = [
        "api/auth/login",
        "/docs",
        "/openapi.json"
    ]
    
    # Não bloqueia requisições para arquivos estáticos ou rotas de API
    if request.url.path.startswith("/static") or request.url.path.startswith("/api"):
        response = await call_next(request)
        return response

    usuario = request.session.get('usuario')

    # Se o usuário NÃO está logado E o caminho que ele tenta acessar NÃO está na lista de permitidos, redireciona para a página de login.
    if not usuario and request.url.path not in allowed_paths:
        return RedirectResponse(url="/api/auth/login")

    response = await call_next(request)
    return response

# Adiciona o middleware de sessão ao aplicativo
app.add_middleware(
    SessionMiddleware,
    secret_key="xK9mP2vL8qR5nW7jE_______45>opse<22______fG9hJ2kL5nM8qR1wE4rT7yU0iO3pA6sD9f"
)

# Adicionando tratamento para 404 (rota não encontrada)
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
   
    # Verifica se a exceção é um erro 404 (Not Found)
    if exc.status_code == 404:
        # Verifica se o usuário está logado (procurando na sessão)
        usuario_logado = request.session.get('usuario')

        if not usuario_logado:
            # Se não estiver logado, redireciona para a página de login.
            return RedirectResponse(url="/login")
        else:
            # Se estiver logado, mostra a página de erro 404 amigável.
            context = {"request": request, "usuario": usuario_logado}
            return templates.TemplateResponse("404_fallback.html", context, status_code=404)
    
    # Para qualquer outro erro HTTP, mantém o comportamento padrão.
    return RedirectResponse(url="/login")

# Configuração de arquivos estáticos e templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = templates_instance

# --- Incluir os Roteadores ---

app.include_router(
    authentication.router, 
    prefix="/api/auth",
    tags=["Autenticação"]   # Agrupa estas rotas na documentação /docs
)

app.include_router(
    usuario.router, 
    prefix="/api/usuarios",        
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