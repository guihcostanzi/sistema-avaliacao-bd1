from fastapi.templating import Jinja2Templates

# Cria uma única instância do motor de templates que será usada em toda a aplicação.
templates = Jinja2Templates(directory="templates")