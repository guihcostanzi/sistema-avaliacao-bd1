from passlib.context import CryptContext

# Cria um contexto de criptografia, especificando o algoritmo 'bcrypt', bom para hashing de senhas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verificar_Senha(senha_raw: str, senha_hash: str) -> bool:
    # Verifica se a senha em texto plano corresponde ao hash armazenado
    return pwd_context.verify(senha_raw, senha_hash)

def get_senha_hash(senha: str) -> str:
   # Gera um hash seguro para a senha fornecida
    return pwd_context.hash(senha)