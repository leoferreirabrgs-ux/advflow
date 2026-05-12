# JurisFlow

Site institucional em Python para automação jurídica.

Proposta:
"Automação sob medida para escritórios de advocacia que querem reduzir trabalho manual, organizar processos e melhorar o atendimento ao cliente."

## Estrutura
- `app.py` -> app Flask principal
- `templates/` -> páginas HTML com Jinja2
- `static/css/` -> estilos
- `static/js/` -> scripts do front-end
- `content/` -> textos de marca, ofertas e copy
- `scripts/` -> utilitários e automações auxiliares
- `data/` -> banco local SQLite e arquivos de apoio

## Rodar localmente
```bash
cd "/mnt/c/Users/leona/OneDrive/Documentos/GitHub/_repos"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python3 app.py
```

Se quiser usar Postgres/Supabase em desenvolvimento, defina `DATABASE_URL` no `.env`.

Depois abra:
http://127.0.0.1:5000

## Deploy sugerido
- Banco: Supabase Postgres
- Hospedagem: Render
- Domínio: jurisflow.com.br

## Próximos passos
1. Definir o provedor de banco principal (Supabase/Postgres)
2. Conectar a aplicação ao banco em produção usando a connection string PostgreSQL do Supabase
3. Se o host de deploy for IPv4-only, usar o session pooler do Supabase em vez do endpoint direto do banco
4. Publicar no Render
5. Apontar o domínio
6. Ajustar copy final das 2 landing pages
7. Revisar formulário e captação de leads
8. Subir a planilha/exportação inicial de processos para testar o dashboard
