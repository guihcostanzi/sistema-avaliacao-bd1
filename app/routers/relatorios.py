from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.database import get_db
from app.session_dependencies import get_usuario_autenticado

templates = Jinja2Templates(directory="templates")
router = APIRouter()

@router.get("/", response_class=HTMLResponse)
def selecionar_projeto_relatorio(
    request: Request,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    """Tela para seleção de projeto para gráficos"""
    
    query_projetos = text("""
        SELECT p.ID, p.NOME,
               COUNT(DISTINCT s.ID) as total_submissoes
        FROM PROJETO p
        INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID
        LEFT JOIN SUBMISSAO s ON p.ID = s.PROJETO_ID
        WHERE up.USUARIO_ID = :usuario_id
        GROUP BY p.ID, p.NOME
        HAVING COUNT(DISTINCT s.ID) > 0
        ORDER BY p.NOME
    """)
    
    projetos = db.execute(query_projetos, {"usuario_id": current_user['id']}).fetchall()
    
    contexto = {
        "request": request,
        "projetos": projetos,
        "usuario": current_user
    }
    
    return templates.TemplateResponse("relatorios.html", contexto)