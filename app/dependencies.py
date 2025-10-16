from fastapi import Request, HTTPException
from starlette import status

# Função para obter o usuário atual da sessão (segurança)
def get_usuario_autenticado(request: Request) -> dict:

    usuario = request.session.get('usuario')
    
    if not usuario:
        # Redireciona para a página de login se o usuário não estiver autenticado.
        raise HTTPException(
            status_code=status.HTTP_302_FOUND, 
            detail="Not authenticated", 
            headers={"Location": "/login"}
        )
    
    return usuario