from fastapi import APIRouter, status
from pydantic import BaseModel, Field

# Cria uma instância de APIRouter para agrupar endpoints
router = APIRouter()

# --- Modelo de Dados e Banco de Dados Temporário ---

# Define a estrutura de dados para uma avaliação usando Pydantic.
# Isso garante a validação automática dos dados recebidos pela API.
class Avaliacao(BaseModel):
    nome_usuario: str
    nota: int = Field(ge=1, le=5, description="A nota deve ser entre 1 e 5.")
    comentario: str | None = None # O comentário é um campo opcional.

# Simula um banco de dados em memória para armazenar as avaliações.
# Em uma aplicação real, isso seria substituído por uma conexão com um banco de dados.
db_avaliacoes = []

# --- Endpoints da API ---

@router.post("/avaliacoes", status_code=status.HTTP_201_CREATED)
def criar_avaliacao(avaliacao: Avaliacao):
    """
    Endpoint para criar uma nova avaliação.
    Recebe um JSON no corpo da requisição e o valida contra o modelo 'Avaliacao'.
    """
    # Converte o objeto Pydantic recebido para um dicionário Python.
    avaliacao_dict = avaliacao.model_dump()
    
    # Simula a geração de um ID único para a nova avaliação.
    id_gerado = len(db_avaliacoes) + 1
    avaliacao_dict["id"] = id_gerado
    
    # Adiciona a nova avaliação ao nosso "banco de dados".
    db_avaliacoes.append(avaliacao_dict)
    
    # Retorna a avaliação criada, que o FastAPI converterá para JSON.
    return avaliacao_dict

@router.get("/avaliacoes")
def listar_avaliacoes():
    """
    Endpoint para listar todas as avaliações existentes.
    """
    # Retorna um dicionário contendo a lista de todas as avaliações.
    return {"avaliacoes": db_avaliacoes}