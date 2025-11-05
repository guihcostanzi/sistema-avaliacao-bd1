from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi.templating import Jinja2Templates
from typing import Optional

from app.db.database import get_db
from app.session_dependencies import get_usuario_autenticado

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
def listar_projetos_submissao(
    request: Request,
    success_message: Optional[str] = None,
    error_message: Optional[str] = None,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    # Buscar projetos que o usuário tem acesso
    query_projetos = text("""
        SELECT p.ID, p.NOME,
               COUNT(DISTINCT pg.ID) as total_perguntas,
               COUNT(DISTINCT s.ID) as total_submissoes_usuario
        FROM PROJETO p
        INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID
        LEFT JOIN PERGUNTA pg ON p.ID = pg.PROJETO_ID
        LEFT JOIN SUBMISSAO s ON p.ID = s.PROJETO_ID AND s.USUARIO_ID = :usuario_id
        WHERE up.USUARIO_ID = :usuario_id
        GROUP BY p.ID, p.NOME
        ORDER BY p.NOME
    """)
    projetos = db.execute(query_projetos, {"usuario_id": current_user['id']}).fetchall()

    contexto = {
        "request": request,
        "projetos": projetos,
        "success_message": success_message,
        "error_message": error_message,
        "usuario": current_user
    }
    
    return templates.TemplateResponse("submissoes_projetos.html", contexto)

@router.get("/{projeto_id}/formulario", response_class=HTMLResponse)
def formulario_submissao(
    projeto_id: int,
    request: Request,
    success_message: Optional[str] = None,
    error_message: Optional[str] = None,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    # Verificar se o usuário tem acesso ao projeto
    query_verificar_projeto = text("""
        SELECT p.ID, p.NOME FROM PROJETO p 
        INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
        WHERE p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
    """)
    projeto = db.execute(query_verificar_projeto, {"projeto_id": projeto_id, "usuario_id": current_user['id']}).first()
    
    if not projeto:
        return RedirectResponse(url="/submissoes?error_message=Projeto não encontrado ou sem acesso", status_code=303)
    
    # Buscar perguntas do projeto
    query_perguntas = text("""
        SELECT p.ID, p.PERGUNTA, p.TIPO, p.MODELO, p.ESTR_ENTIDADE_ID
        FROM PERGUNTA p
        WHERE p.PROJETO_ID = :projeto_id
        ORDER BY p.ID
    """)
    perguntas = db.execute(query_perguntas, {"projeto_id": projeto_id}).fetchall()
    
    if not perguntas:
        return RedirectResponse(url="/submissoes?error_message=Este projeto não possui perguntas configuradas", status_code=303)
    
    # Buscar valores padrão para perguntas pré-definidas
    valores_padrao = {}
    valores_entidade = {}
    
    for pergunta in perguntas:
        if pergunta.modelo == 'pre-definido':
            # Buscar valores padrão
            query_valores = text("""
                SELECT VALOR FROM VALORES_PADRAO 
                WHERE PERGUNTA_ID = :pergunta_id 
                ORDER BY VALOR
            """)
            valores = db.execute(query_valores, {"pergunta_id": pergunta.id}).fetchall()
            valores_padrao[pergunta.id] = [v.valor for v in valores]
        
        elif pergunta.estr_entidade_id:
            # Buscar entidades disponíveis
            query_entidades = text("""
                SELECT e.ID_SEQ, 
                       COALESCE(
                           STRING_AGG(
                               CASE WHEN ea.EXIBICAO = TRUE 
                                    THEN CONCAT(ea.LABEL, ': ', a.VALOR) 
                                    ELSE NULL 
                               END, 
                               ' | ' ORDER BY ea.ID_SEQ
                           ), 
                           CONCAT('Entidade ', e.ID_SEQ)
                       ) as display_text
                FROM ENTIDADE e
                LEFT JOIN ESTR_ATRIBUTOS ea ON e.ESTR_ENTIDADE_ID = ea.ESTR_ENTIDADE_ID
                LEFT JOIN ATRIBUTOS a ON e.ESTR_ENTIDADE_ID = a.ESTR_ENTIDADE_ID 
                                      AND e.ID_SEQ = a.ENTIDADE_ID_SEQ 
                                      AND ea.ID_SEQ = a.ESTR_ATRIBUTO_ID_SEQ
                WHERE e.ESTR_ENTIDADE_ID = :estr_entidade_id
                GROUP BY e.ID_SEQ, e.ESTR_ENTIDADE_ID
                ORDER BY e.ID_SEQ
            """)
            entidades = db.execute(query_entidades, {"estr_entidade_id": pergunta.estr_entidade_id}).fetchall()
            valores_entidade[pergunta.id] = [{"id": f"{pergunta.estr_entidade_id}_{e.id_seq}", "text": e.display_text} for e in entidades]

    contexto = {
        "request": request,
        "projeto": projeto,
        "perguntas": perguntas,
        "valores_padrao": valores_padrao,
        "valores_entidade": valores_entidade,
        "success_message": success_message,
        "error_message": error_message,
        "usuario": current_user
    }
    
    return templates.TemplateResponse("formulario_submissao.html", contexto)

@router.post("/{projeto_id}/enviar")
async def enviar_submissao(
    projeto_id: int,
    request: Request,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
    from datetime import datetime
    import re
    
    try:
        # Verificar se o usuário tem acesso ao projeto
        query_verificar_projeto = text("""
            SELECT p.ID FROM PROJETO p 
            INNER JOIN USUARIO_PROJETO up ON p.ID = up.PROJETO_ID 
            WHERE p.ID = :projeto_id AND up.USUARIO_ID = :usuario_id
        """)
        projeto_result = db.execute(query_verificar_projeto, {"projeto_id": projeto_id, "usuario_id": current_user['id']}).first()
        
        if not projeto_result:
            return RedirectResponse(
                url="/submissoes?error_message=Projeto não encontrado", 
                status_code=303
            )
        
        # Buscar perguntas do projeto
        query_perguntas = text("""
            SELECT ID, PERGUNTA, TIPO 
            FROM PERGUNTA 
            WHERE PROJETO_ID = :projeto_id
        """)
        perguntas = db.execute(query_perguntas, {"projeto_id": projeto_id}).fetchall()
        
        # Processar form data
        form_data = await request.form()
        
        # Validação por tipo
        for pergunta in perguntas:
            campo_nome = f"pergunta_{pergunta.id}"
            valor = form_data.get(campo_nome, "").strip()

            print(f"Validando pergunta ID {pergunta.id} do tipo {pergunta.tipo} com valor '{valor}'")  # Debug
            
            if valor:
                if pergunta.tipo == 'numero':
                    try:
                        float(valor)
                    except ValueError:
                        return RedirectResponse(
                            url=f"/submissoes/{projeto_id}/formulario?error_message=Resposta inválida para '{pergunta.pergunta}': digite apenas números", 
                            status_code=303
                        )
                elif pergunta.tipo == 'email':
                    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
                    if not re.match(email_regex, valor):
                        return RedirectResponse(
                            url=f"/submissoes/{projeto_id}/formulario?error_message=Resposta inválida para '{pergunta.pergunta}': digite um email válido", 
                            status_code=303
                        )
                elif pergunta.tipo == 'data':
                    try:
                        datetime.strptime(valor, '%Y-%m-%d')
                    except ValueError:
                        return RedirectResponse(
                            url=f"/submissoes/{projeto_id}/formulario?error_message=Resposta inválida para '{pergunta.pergunta}': selecione uma data válida", 
                            status_code=303
                        )
                elif pergunta.tipo == 'entidade':
                    # Validar formato entidade_id_seq
                    if '_' not in valor:
                        return RedirectResponse(
                            url=f"/submissoes/{projeto_id}/formulario?error_message=Resposta inválida para '{pergunta.pergunta}': selecione uma entidade válida", 
                            status_code=303
                        )
                    try:
                        partes = valor.split('_')
                        if len(partes) != 2:
                            raise ValueError("Formato inválido")
                        int(partes[0])  # Validar se é número
                        int(partes[1])  # Validar se é número
                    except ValueError:
                        return RedirectResponse(
                            url=f"/submissoes/{projeto_id}/formulario?error_message=Resposta inválida para '{pergunta.pergunta}': selecione uma entidade válida", 
                            status_code=303
                        )
        
        # Criar submissão
        query_submissao = text("""
            INSERT INTO SUBMISSAO (PROJETO_ID, USUARIO_ID) 
            VALUES (:projeto_id, :usuario_id) RETURNING ID
        """)
        result = db.execute(query_submissao, {
            "projeto_id": projeto_id,
            "usuario_id": current_user['id']
        })
        
        # Obter ID da submissão
        submissao_row = result.fetchone()
        if submissao_row:
            submissao_id = submissao_row[0]
        else:
            # Fallback para bancos que não suportam RETURNING
            submissao_id = result.lastrowid
        
        # Salvar respostas
        for pergunta in perguntas:
            campo_nome = f"pergunta_{pergunta.id}"
            valor = form_data.get(campo_nome, "").strip()
            
            print(f"Salvando pergunta ID {pergunta.id} do tipo {pergunta.tipo} com valor '{valor}'")  # Debug
            
            if valor:  # Só salva se tiver valor
                if pergunta.tipo == 'entidade':
                    # Separar entidade_id e seq para perguntas do tipo entidade
                    partes = valor.split('_')
                    entidade_id = int(partes[0])
                    seq = int(partes[1])
                    
                    query_resposta = text("""
                        INSERT INTO RESPOSTA (SUBMISSAO_ID, PERGUNTA_ID, RESPOSTA, ENTIDADE_ESTR_ENTIDADE_ID, ENTIDADE_ID_SEQ) 
                        VALUES (:submissao_id, :pergunta_id, :resposta, :entidade_id, :seq)
                    """)
                    db.execute(query_resposta, {
                        "submissao_id": submissao_id,
                        "pergunta_id": pergunta.id,
                        "resposta": valor,  # Manter o valor original também
                        "entidade_id": entidade_id,
                        "seq": seq
                    })
                else:
                    # Para outros tipos de pergunta
                    query_resposta = text("""
                        INSERT INTO RESPOSTA (SUBMISSAO_ID, PERGUNTA_ID, RESPOSTA) 
                        VALUES (:submissao_id, :pergunta_id, :resposta)
                    """)
                    db.execute(query_resposta, {
                        "submissao_id": submissao_id,
                        "pergunta_id": pergunta.id,
                        "resposta": valor
                    })
        
        db.commit()
        
        return RedirectResponse(
            url="/submissoes?success_message=Submissão enviada com sucesso!", 
            status_code=303
        )
        
    except Exception as e:
        db.rollback()
        print(f"Erro ao enviar submissão: {e}")  # Para debug
        return RedirectResponse(
            url=f"/submissoes/{projeto_id}/formulario?error_message=Erro ao enviar submissão", 
            status_code=303
        )

@router.get("/{projeto_id}/historico", response_class=HTMLResponse)
def historico_submissoes(
    projeto_id: int,
    request: Request,
    current_user = Depends(get_usuario_autenticado),
    db: Session = Depends(get_db)
):
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
        SELECT ID, PERGUNTA, TIPO 
        FROM PERGUNTA 
        WHERE PROJETO_ID = :projeto_id 
        ORDER BY ID
    """)
    perguntas = db.execute(query_perguntas, {"projeto_id": projeto_id}).fetchall()
    
    # Buscar submissões do usuário
    query_submissoes = text("""
        SELECT ID, DATA_CADASTRO 
        FROM SUBMISSAO 
        WHERE PROJETO_ID = :projeto_id AND USUARIO_ID = :usuario_id 
        ORDER BY DATA_CADASTRO DESC
    """)
    submissoes_raw = db.execute(query_submissoes, {"projeto_id": projeto_id, "usuario_id": current_user['id']}).fetchall()
    
    # Buscar todas as respostas
    submissoes = []
    for submissao in submissoes_raw:
        query_respostas = text("""
            SELECT r.PERGUNTA_ID, r.RESPOSTA, r.ENTIDADE_ESTR_ENTIDADE_ID, r.ENTIDADE_ID_SEQ,
                   COALESCE(
                       STRING_AGG(
                           CASE WHEN ea.EXIBICAO = TRUE 
                                THEN CONCAT(ea.LABEL, ': ', a.VALOR) 
                                ELSE NULL 
                           END, 
                           ' | ' ORDER BY ea.ID_SEQ
                       ), 
                       CASE 
                           WHEN r.ENTIDADE_ESTR_ENTIDADE_ID IS NOT NULL THEN 
                               CONCAT('Entidade ', r.ENTIDADE_ESTR_ENTIDADE_ID, '_', r.ENTIDADE_ID_SEQ)
                           ELSE NULL 
                       END
                   ) as entidade_info
            FROM RESPOSTA r 
            LEFT JOIN ESTR_ATRIBUTOS ea ON r.ENTIDADE_ESTR_ENTIDADE_ID = ea.ESTR_ENTIDADE_ID
            LEFT JOIN ATRIBUTOS a ON r.ENTIDADE_ESTR_ENTIDADE_ID = a.ESTR_ENTIDADE_ID 
                                  AND r.ENTIDADE_ID_SEQ = a.ENTIDADE_ID_SEQ 
                                  AND ea.ID_SEQ = a.ESTR_ATRIBUTO_ID_SEQ
            WHERE r.SUBMISSAO_ID = :submissao_id
            GROUP BY r.PERGUNTA_ID, r.RESPOSTA, r.ENTIDADE_ESTR_ENTIDADE_ID, r.ENTIDADE_ID_SEQ
        """)
        respostas_raw = db.execute(query_respostas, {"submissao_id": submissao.id}).fetchall()
        
        # Organizar respostas por pergunta_id
        respostas = {}
        for resposta in respostas_raw:
            respostas[resposta.pergunta_id] = resposta
        
        submissoes.append({
            "id": submissao.id,
            "data_cadastro": submissao.data_cadastro,
            "respostas": respostas
        })
    
    contexto = {
        "request": request,
        "projeto": projeto,
        "perguntas": perguntas,
        "submissoes": submissoes,
        "usuario": current_user
    }
    
    return templates.TemplateResponse("historico_submissoes.html", contexto)