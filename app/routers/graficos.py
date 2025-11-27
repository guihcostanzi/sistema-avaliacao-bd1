from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Dict, Any
from collections import Counter
from datetime import datetime

from app.db.database import get_db
from app.session_dependencies import get_usuario_autenticado

# Configurar templates
templates = Jinja2Templates(directory="templates")

router = APIRouter()

@router.get("/{projeto_id}", response_class=HTMLResponse)
def tela_graficos(
    projeto_id: int,
    request: Request,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    """Tela principal para geração de gráficos"""
    
    # Verificar acesso ao projeto
    query_projeto = text("""
        SELECT p.ID, p.NOME FROM PROJETO p 
        INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
        WHERE p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
    """)
    projeto = db.execute(query_projeto, {"projeto_id": projeto_id, "usuario_id": current_user['id']}).first()
    
    if not projeto:
        return RedirectResponse(url="/submissoes?error_message=Projeto não encontrado", status_code=303)
    
    # Buscar perguntas do projeto
    query_perguntas = text("""
        SELECT p.ID, p.PERGUNTA, p.TIPO, p.MODELO,
               COUNT(DISTINCT s.ID) as total_submissoes
        FROM PERGUNTA p
        LEFT JOIN RESPOSTA r ON p.ID = r.PERGUNTA_ID
        LEFT JOIN SUBMISSAO s ON r.SUBMISSAO_ID = s.ID
        WHERE p.PROJETO_ID = :projeto_id
        GROUP BY p.ID, p.PERGUNTA, p.TIPO, p.MODELO
        HAVING COUNT(DISTINCT s.ID) > 0
        ORDER BY p.ID
    """)
    perguntas = db.execute(query_perguntas, {"projeto_id": projeto_id}).fetchall()
    
    # Buscar total de submissões do projeto
    query_total = text("""
        SELECT COUNT(*) as total 
        FROM SUBMISSAO 
        WHERE PROJETO_ID = :projeto_id
    """)
    total_submissoes = db.execute(query_total, {"projeto_id": projeto_id}).scalar()
    
    contexto = {
        "request": request,
        "projeto": projeto,
        "perguntas": perguntas,
        "total_submissoes": total_submissoes,
        "usuario": current_user
    }
    
    return templates.TemplateResponse("graficos.html", contexto)

@router.post("/{projeto_id}/gerar")
async def gerar_grafico(
    projeto_id: int,
    request: Request,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    """Endpoint para gerar dados do gráfico"""
    
    try:
        # Processar dados do formulário
        form_data = await request.form()
        tipo_grafico = form_data.get("tipo_grafico")
        pergunta_x = form_data.get("pergunta_x")
        pergunta_y = form_data.get("pergunta_y")
        
        # Validações básicas
        if not tipo_grafico:
            return JSONResponse({"error": "Selecione um tipo de gráfico"}, status_code=400)
        
        if not pergunta_x:
            return JSONResponse({"error": "Selecione pelo menos uma pergunta"}, status_code=400)
        
        # Verificar acesso ao projeto
        query_verificar = text("""
            SELECT 1 FROM PROJETO p 
            INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
            WHERE p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        if not db.execute(query_verificar, {"projeto_id": projeto_id, "usuario_id": current_user['id']}).first():
            return JSONResponse({"error": "Acesso negado ao projeto"}, status_code=403)
        
        # Buscar informações das perguntas
        perguntas_info = {}
        for pid in [pergunta_x, pergunta_y]:
            if pid:
                query_info = text("""
                    SELECT ID, PERGUNTA, TIPO, MODELO 
                    FROM PERGUNTA 
                    WHERE ID = :pergunta_id AND PROJETO_ID = :projeto_id
                """)
                info = db.execute(query_info, {"pergunta_id": pid, "projeto_id": projeto_id}).first()
                if info:
                    perguntas_info[pid] = info
        
        # Validar compatibilidade do gráfico
        validacao = validar_compatibilidade_grafico(tipo_grafico, perguntas_info, pergunta_x, pergunta_y)
        if validacao["erro"]:
            return JSONResponse({"error": validacao["erro"]}, status_code=400)
        
        # Gerar dados do gráfico
        dados_grafico = gerar_dados_grafico(
            db, projeto_id, tipo_grafico, pergunta_x, pergunta_y, perguntas_info
        )
        
        return JSONResponse(dados_grafico)
        
    except Exception as e:
        print(f"Erro ao gerar gráfico: {e}")
        return JSONResponse({"error": "Erro interno do servidor"}, status_code=500)

def validar_compatibilidade_grafico(tipo_grafico: str, perguntas_info: Dict, pergunta_x: str, pergunta_y: str = None) -> Dict[str, Any]:
    """Valida se as perguntas são compatíveis com o tipo de gráfico"""
    
    if tipo_grafico == "pie":
        if pergunta_y:
            return {"erro": "Gráfico de pizza aceita apenas uma pergunta"}
        
        pergunta_info = perguntas_info.get(pergunta_x)
        if not pergunta_info:
            return {"erro": "Pergunta não encontrada"}
        
        return {"erro": None}
    
    elif tipo_grafico == "bar":
        if not pergunta_y:
            return {"erro": "Gráfico de barras requer duas perguntas (X e Y)"}
        
        pergunta_x_info = perguntas_info.get(pergunta_x)
        pergunta_y_info = perguntas_info.get(pergunta_y)
        
        if not pergunta_x_info or not pergunta_y_info:
            return {"erro": "Uma ou ambas perguntas não foram encontradas"}
        
        if pergunta_y_info.tipo not in ['numero'] and pergunta_x_info.tipo == pergunta_y_info.tipo:
            return {"erro": "Para gráfico de barras com dois campos não numéricos, eles devem ser diferentes para permitir contagem"}
        
        return {"erro": None}
    
    elif tipo_grafico == "line":
        if not pergunta_y:
            return {"erro": "Gráfico de linha requer duas perguntas (X e Y)"}
        
        pergunta_x_info = perguntas_info.get(pergunta_x)
        pergunta_y_info = perguntas_info.get(pergunta_y)
        
        if not pergunta_x_info or not pergunta_y_info:
            return {"erro": "Uma ou ambas perguntas não foram encontradas"}
        
        if pergunta_x_info.tipo not in ['data', 'numero'] and pergunta_y_info.tipo not in ['numero']:
            return {"erro": "Gráfico de linha funciona melhor com X sendo data/número e Y sendo numérico"}
        
        return {"erro": None}
    
    elif tipo_grafico == "scatter":
        pergunta_info = perguntas_info.get(pergunta_x)
        if not pergunta_info:
            return {"erro": "Pergunta não encontrada"}
        
        if pergunta_info.tipo not in ['numero', 'data']:
            return {"erro": "Gráfico de dispersão funciona melhor com dados numéricos ou de data"}
        
        return {"erro": None}
    
    return {"erro": "Tipo de gráfico não suportado"}

def gerar_dados_grafico(db: Session, projeto_id: int, tipo_grafico: str, pergunta_x: str, pergunta_y: str = None, perguntas_info: Dict = None) -> Dict[str, Any]:
    """Gera os dados específicos para cada tipo de gráfico"""
    
    if tipo_grafico == "pie":
        return gerar_dados_pizza(db, projeto_id, pergunta_x, perguntas_info)
    elif tipo_grafico == "bar":
        return gerar_dados_barras(db, projeto_id, pergunta_x, pergunta_y, perguntas_info)
    elif tipo_grafico == "line":
        return gerar_dados_linha(db, projeto_id, pergunta_x, pergunta_y, perguntas_info)
    elif tipo_grafico == "scatter":
        return gerar_dados_dispersao(db, projeto_id, pergunta_x, perguntas_info)

def gerar_dados_pizza(db: Session, projeto_id: int, pergunta_id: str, perguntas_info: Dict) -> Dict[str, Any]:
    """Gera dados para gráfico de pizza"""
    
    pergunta_info = perguntas_info[pergunta_id]
    
    query = text("""
        SELECT r.RESPOSTA
        FROM RESPOSTA r
        INNER JOIN SUBMISSAO s ON r.SUBMISSAO_ID = s.ID
        WHERE s.PROJETO_ID = :projeto_id AND r.PERGUNTA_ID = :pergunta_id
        AND r.RESPOSTA IS NOT NULL AND r.RESPOSTA != ''
    """)
    
    respostas = db.execute(query, {"projeto_id": projeto_id, "pergunta_id": pergunta_id}).fetchall()
    
    contador = Counter([r.resposta for r in respostas])
    
    series_data = []
    for valor, count in contador.most_common():
        series_data.append({
            "name": str(valor),
            "data": count
        })
    
    return {
        "type": "pie",
        "title": {
            "text": f"Distribuição: {pergunta_info.pergunta}"
        },
        "series": series_data
    }

def gerar_dados_barras(db: Session, projeto_id: int, pergunta_x: str, pergunta_y: str, perguntas_info: Dict) -> Dict[str, Any]:
    """Gera dados para gráfico de barras"""
    
    pergunta_x_info = perguntas_info[pergunta_x]
    pergunta_y_info = perguntas_info[pergunta_y]
    
    query = text("""
        SELECT rx.RESPOSTA as x_valor, ry.RESPOSTA as y_valor
        FROM RESPOSTA rx
        INNER JOIN SUBMISSAO s ON rx.SUBMISSAO_ID = s.ID
        INNER JOIN RESPOSTA ry ON s.ID = ry.SUBMISSAO_ID
        WHERE s.PROJETO_ID = :projeto_id 
        AND rx.PERGUNTA_ID = :pergunta_x 
        AND ry.PERGUNTA_ID = :pergunta_y
        AND rx.RESPOSTA IS NOT NULL AND rx.RESPOSTA != ''
        AND ry.RESPOSTA IS NOT NULL AND ry.RESPOSTA != ''
    """)
    
    dados = db.execute(query, {
        "projeto_id": projeto_id, 
        "pergunta_x": pergunta_x, 
        "pergunta_y": pergunta_y
    }).fetchall()
    
    if pergunta_y_info.tipo == 'numero':
        agrupados = {}
        for row in dados:
            x_val = str(row.x_valor)
            y_val = float(row.y_valor) if row.y_valor else 0
            
            if x_val not in agrupados:
                agrupados[x_val] = []
            agrupados[x_val].append(y_val)
        
        categories = list(agrupados.keys())
        values = [sum(vals)/len(vals) for vals in agrupados.values()]
        
    else:
        contador = Counter([(row.x_valor, row.y_valor) for row in dados])
        
        agrupados = {}
        for (x_val, y_val), count in contador.items():
            x_str = str(x_val)
            if x_str not in agrupados:
                agrupados[x_str] = 0
            agrupados[x_str] += count
        
        categories = list(agrupados.keys())
        values = list(agrupados.values())
    
    return {
        "type": "bar",
        "title": {
            "text": f"{pergunta_x_info.pergunta} vs {pergunta_y_info.pergunta}"
        },
        "series": [{
            "name": pergunta_y_info.pergunta,
            "data": values
        }],
        "categories": categories
    }

def gerar_dados_linha(db: Session, projeto_id: int, pergunta_x: str, pergunta_y: str, perguntas_info: Dict) -> Dict[str, Any]:
    """Gera dados para gráfico de linha"""
    
    pergunta_x_info = perguntas_info[pergunta_x]
    pergunta_y_info = perguntas_info[pergunta_y]
    
    query = text("""
        SELECT rx.RESPOSTA as x_valor, ry.RESPOSTA as y_valor
        FROM RESPOSTA rx
        INNER JOIN SUBMISSAO s ON rx.SUBMISSAO_ID = s.ID
        INNER JOIN RESPOSTA ry ON s.ID = ry.SUBMISSAO_ID
        WHERE s.PROJETO_ID = :projeto_id 
        AND rx.PERGUNTA_ID = :pergunta_x 
        AND ry.PERGUNTA_ID = :pergunta_y
        AND rx.RESPOSTA IS NOT NULL AND rx.RESPOSTA != ''
        AND ry.RESPOSTA IS NOT NULL AND ry.RESPOSTA != ''
        ORDER BY rx.RESPOSTA
    """)
    
    dados = db.execute(query, {
        "projeto_id": projeto_id, 
        "pergunta_x": pergunta_x, 
        "pergunta_y": pergunta_y
    }).fetchall()
    
    if pergunta_x_info.tipo == 'data':
        dados_processados = []
        for row in dados:
            try:
                x_val = datetime.strptime(row.x_valor, '%Y-%m-%d').strftime('%m/%d/%Y')
                y_val = float(row.y_valor) if pergunta_y_info.tipo == 'numero' else 1
                dados_processados.append((x_val, y_val))
            except:
                continue
        
        agrupados = {}
        for x_val, y_val in dados_processados:
            if x_val not in agrupados:
                agrupados[x_val] = []
            agrupados[x_val].append(y_val)
        
        categories = sorted(agrupados.keys())
        values = [sum(agrupados[cat])/len(agrupados[cat]) for cat in categories]
        
    else:
        agrupados = {}
        for row in dados:
            x_val = str(row.x_valor)
            y_val = float(row.y_valor) if pergunta_y_info.tipo == 'numero' else 1
            
            if x_val not in agrupados:
                agrupados[x_val] = []
            agrupados[x_val].append(y_val)
        
        categories = list(agrupados.keys())
        values = [sum(vals)/len(vals) for vals in agrupados.values()]
    
    return {
        "type": "line",
        "title": {
            "text": f"{pergunta_x_info.pergunta} ao longo de {pergunta_y_info.pergunta}"
        },
        "series": [{
            "name": pergunta_y_info.pergunta,
            "data": values,
            "mode": "lines+markers"
        }],
        "categories": categories
    }

def gerar_dados_dispersao(db: Session, projeto_id: int, pergunta_id: str, perguntas_info: Dict) -> Dict[str, Any]:
    """Gera dados para gráfico de dispersão"""
    
    pergunta_info = perguntas_info[pergunta_id]
    
    query = text("""
        SELECT r.RESPOSTA, ROW_NUMBER() OVER (ORDER BY s.DATA_CADASTRO) as seq
        FROM RESPOSTA r
        INNER JOIN SUBMISSAO s ON r.SUBMISSAO_ID = s.ID
        WHERE s.PROJETO_ID = :projeto_id AND r.PERGUNTA_ID = :pergunta_id
        AND r.RESPOSTA IS NOT NULL AND r.RESPOSTA != ''
        ORDER BY s.DATA_CADASTRO
    """)
    
    dados = db.execute(query, {"projeto_id": projeto_id, "pergunta_id": pergunta_id}).fetchall()
    
    scatter_data = []
    for row in dados:
        try:
            if pergunta_info.tipo == 'numero':
                y_val = float(row.resposta)
            elif pergunta_info.tipo == 'data':
                date_obj = datetime.strptime(row.resposta, '%Y-%m-%d')
                y_val = date_obj.timestamp()
            else:
                y_val = hash(row.resposta) % 1000
            
            scatter_data.append([int(row.seq), y_val])
        except:
            continue
    
    return {
        "type": "scatter",
        "title": {
            "text": f"Dispersão: {pergunta_info.pergunta}"
        },
        "series": [{
            "name": pergunta_info.pergunta,
            "data": scatter_data,
            "mode": "markers",
            "marker": {
                "size": 8,
                "color": "blue"
            }
        }]
    }