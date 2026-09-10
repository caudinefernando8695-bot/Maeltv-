# MaelTV — backend inicial

Backend funcional sem dependências externas para o catálogo MaelTV.

## O que já existe

- Login de convidado com token temporário
- Consulta de utilizador autenticado
- Catálogo de filmes, séries, documentários e canais
- Pesquisa por título, descrição e categoria
- Filtro por categoria e tipo
- Favoritos por convidado
- Base SQLite criada automaticamente em `data/maeltv.db`
- CORS preparado para ligar ao frontend
- Dados iniciais com fontes oficiais/domínio público

## Executar

Requer Python 3.10 ou superior:

```text
python3 server.py
```

Por padrão, a API fica em `http://127.0.0.1:8080`.

## Endpoints

- `GET /api/health`
- `POST /api/auth/guest`
- `GET /api/me` com `Authorization: Bearer TOKEN`
- `GET /api/categories`
- `GET /api/catalog`
- `GET /api/catalog?q=acao`
- `GET /api/catalog?category=Ação`
- `GET /api/catalog?type=movie`
- `POST /api/favorites` com `{ "catalog_id": 1 }` e token

## Próximo passo para ficar online

Este pacote precisa ser colocado num serviço que execute Python continuamente, como Render, Railway, Fly.io ou um VPS. A página MaelTV publicada no Zapia é estática e não consegue executar este servidor por si só.

Antes de publicar o catálogo real, substituir as fontes de demonstração por URLs próprias ou licenciadas. Não adicionar canais pagos ou filmes protegidos sem autorização.
