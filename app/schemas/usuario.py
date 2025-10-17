from typing import Optional
from pydantic import BaseModel, EmailStr

# Define os campos básicos que todo usuário terá
class UsuarioBase(BaseModel):
    nome: str
    email: EmailStr # Valida email


# Usado para criar um novo usuario, possui a senha
class UsuarioCreate(UsuarioBase):
    senha: str

# Usado para atualizar um usuário, todos os campos são opcionais
class UsuarioUpdate(BaseModel):
    nome: Optional[str] = None
    email: Optional[EmailStr] = None
    senha: Optional[str] = None

# Usado para retornar dados de um usuário (sem a senha)
class Usuario(UsuarioBase):
    id: int

    # Configuração interna para que o Pydantic consiga ler dados
    # que vêm diretamente de um resultado de banco de dados.
    class Config:
        from_attributes = True