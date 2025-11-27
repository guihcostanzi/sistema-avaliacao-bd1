from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List, Dict, Any
from collections import Counter, defaultdict
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
        agregacao_y = form_data.get("agregacao_y", "soma")  # NOVO: soma ou contagem
        
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
            db, projeto_id, tipo_grafico, pergunta_x, pergunta_y, perguntas_info, agregacao_y
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
        
        return {"erro": None}
    
    elif tipo_grafico == "line":
        if not pergunta_y:
            return {"erro": "Gráfico de linha requer duas perguntas (X e Y)"}
        
        pergunta_x_info = perguntas_info.get(pergunta_x)
        pergunta_y_info = perguntas_info.get(pergunta_y)
        
        if not pergunta_x_info or not pergunta_y_info:
            return {"erro": "Uma ou ambas perguntas não foram encontradas"}
        
        return {"erro": None}
    
    elif tipo_grafico == "scatter":
        pergunta_info = perguntas_info.get(pergunta_x)
        if not pergunta_info:
            return {"erro": "Pergunta não encontrada"}
        
        return {"erro": None}
    
    return {"erro": "Tipo de gráfico não suportado"}

def gerar_dados_grafico(db: Session, projeto_id: int, tipo_grafico: str, pergunta_x: str, pergunta_y: str = None, perguntas_info: Dict = None, agregacao_y: str = "soma") -> Dict[str, Any]:
    """Gera os dados específicos para cada tipo de gráfico"""
    
    if tipo_grafico == "pie":
        return gerar_dados_pizza(db, projeto_id, pergunta_x, perguntas_info)
    elif tipo_grafico == "bar":
        return gerar_dados_barras(db, projeto_id, pergunta_x, pergunta_y, perguntas_info, agregacao_y)
    elif tipo_grafico == "line":
        return gerar_dados_linha(db, projeto_id, pergunta_x, pergunta_y, perguntas_info, agregacao_y)
    elif tipo_grafico == "scatter":
        return gerar_dados_dispersao(db, projeto_id, pergunta_x, perguntas_info)

def formatar_data_para_exibicao(data_str: str) -> str:
    """Converte data de YYYY-MM-DD para DD/MM/YYYY"""
    try:
        data_obj = datetime.strptime(data_str, '%Y-%m-%d')
        return data_obj.strftime('%d/%m/%Y')
    except:
        return data_str

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
        # Formatar datas se necessário
        valor_display = formatar_data_para_exibicao(valor) if pergunta_info.tipo == 'data' else str(valor)
        series_data.append({
            "name": valor_display,
            "data": count
        })
    
    return {
        "type": "pie",
        "title": {
            "text": f"Distribuição: {pergunta_info.pergunta}"
        },
        "series": series_data
    }

def gerar_dados_barras(db: Session, projeto_id: int, pergunta_x: str, pergunta_y: str, perguntas_info: Dict, agregacao_y: str = "soma") -> Dict[str, Any]:
    """Gera dados para gráfico de barras com agregação configurável"""
    
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
    
    # Agrupar por X
    agrupados = defaultdict(list)
    
    for row in dados:
        x_val = row.x_valor
        y_val = row.y_valor
        
        # Formatar data para agrupamento (manter formato original para agrupamento)
        x_key = x_val
        agrupados[x_key].append(y_val)
    
    # Processar agregação
    categories = []
    values = []
    
    # Ordenar as chaves (especialmente importante para datas)
    sorted_keys = sorted(agrupados.keys())
    if pergunta_x_info.tipo == 'data':
        try:
            sorted_keys = sorted(agrupados.keys(), key=lambda x: datetime.strptime(x, '%Y-%m-%d'))
        except:
            sorted_keys = sorted(agrupados.keys())
    
    for x_key in sorted_keys:
        y_valores = agrupados[x_key]
        
        # Formatar chave para exibição
        if pergunta_x_info.tipo == 'data':
            x_display = formatar_data_para_exibicao(x_key)
        else:
            x_display = str(x_key)
        
        categories.append(x_display)
        
        # Aplicar agregação
        if agregacao_y == "contagem":
            values.append(len(y_valores))
        else:  # soma (padrão)
            if pergunta_y_info.tipo == 'numero':
                # Somar valores numéricos
                soma = sum(float(v) for v in y_valores if v)
                values.append(soma)
            else:
                # Para não numéricos, contar ocorrências
                values.append(len(y_valores))
    
    # Determinar label do eixo Y
    if agregacao_y == "contagem":
        y_label = f"Contagem de {pergunta_y_info.pergunta}"
    else:
        if pergunta_y_info.tipo == 'numero':
            y_label = f"Soma de {pergunta_y_info.pergunta}"
        else:
            y_label = f"Contagem de {pergunta_y_info.pergunta}"
    
    return {
        "type": "bar",
        "title": {
            "text": f"{pergunta_x_info.pergunta} vs {y_label}"
        },
        "series": [{
            "name": y_label,
            "data": values
        }],
        "categories": categories
    }

def gerar_dados_linha(db: Session, projeto_id: int, pergunta_x: str, pergunta_y: str, perguntas_info: Dict, agregacao_y: str = "soma") -> Dict[str, Any]:
    """Gera dados para gráfico de linha com agregação configurável"""
    
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
    
    # Agrupar por X
    agrupados = defaultdict(list)
    
    for row in dados:
        x_val = row.x_valor
        y_val = row.y_valor
        agrupados[x_val].append(y_val)
    
    # Processar dados
    categories = []
    values = []
    
    # Ordenar as chaves
    sorted_keys = sorted(agrupados.keys())
    if pergunta_x_info.tipo == 'data':
        try:
            sorted_keys = sorted(agrupados.keys(), key=lambda x: datetime.strptime(x, '%Y-%m-%d'))
        except:
            sorted_keys = sorted(agrupados.keys())
    
    for x_key in sorted_keys:
        y_valores = agrupados[x_key]
        
        # Formatar chave para exibição
        if pergunta_x_info.tipo == 'data':
            x_display = formatar_data_para_exibicao(x_key)
        else:
            x_display = str(x_key)
        
        categories.append(x_display)
        
        # Aplicar agregação
        if agregacao_y == "contagem":
            values.append(len(y_valores))
        else:  # soma (padrão)
            if pergunta_y_info.tipo == 'numero':
                soma = sum(float(v) for v in y_valores if v)
                values.append(soma)
            else:
                values.append(len(y_valores))
    
    # Determinar label do eixo Y
    if agregacao_y == "contagem":
        y_label = f"Contagem de {pergunta_y_info.pergunta}"
    else:
        if pergunta_y_info.tipo == 'numero':
            y_label = f"Soma de {pergunta_y_info.pergunta}"
        else:
            y_label = f"Contagem de {pergunta_y_info.pergunta}"
    
    return {
        "type": "line",
        "title": {
            "text": f"{pergunta_x_info.pergunta} ao longo do tempo"
        },
        "series": [{
            "name": y_label,
            "data": values,
            "mode": "lines+markers"
        }],
        "categories": categories
    }

def gerar_dados_dispersao(db: Session, projeto_id: int, pergunta_id: str, perguntas_info: Dict) -> Dict[str, Any]:
    """Gera dados para gráfico de dispersão"""
    
    pergunta_info = perguntas_info[pergunta_id]
    
    query = text("""
        SELECT r.RESPOSTA, s.DATA_CADASTRO
        FROM RESPOSTA r
        INNER JOIN SUBMISSAO s ON r.SUBMISSAO_ID = s.ID
        WHERE s.PROJETO_ID = :projeto_id AND r.PERGUNTA_ID = :pergunta_id
        AND r.RESPOSTA IS NOT NULL AND r.RESPOSTA != ''
        ORDER BY s.DATA_CADASTRO
    """)
    
    dados = db.execute(query, {"projeto_id": projeto_id, "pergunta_id": pergunta_id}).fetchall()
    
    scatter_data = []
    for i, row in enumerate(dados):
        try:
            if pergunta_info.tipo == 'numero':
                y_val = float(row.resposta)
            elif pergunta_info.tipo == 'data':
                date_obj = datetime.strptime(row.resposta, '%Y-%m-%d')
                y_val = date_obj.timestamp()
            else:
                y_val = hash(row.resposta) % 1000
            
            scatter_data.append([i + 1, y_val])
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