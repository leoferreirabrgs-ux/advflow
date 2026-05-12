# JurisFlow Go-Live Plan

Objetivo: deixar o JurisFlow online amanhã com 2 landing pages e banco de dados integrado.

## Etapa 1 — Base do projeto
- Corrigir o README para o caminho real do projeto.
- Criar `.env.example` com as variáveis necessárias.
- Criar a estrutura `content/` para copy e textos de marketing.
- Revisar mensagens, placeholders e CTA principal.

## Etapa 2 — Duas landing pages
- Landing 1: página institucional principal com foco em conversão.
- Landing 2: página específica para diagnóstico/oferta ou nicho prioritário.
- Revisar navegação, CTA, prova social e seções comerciais.

## Etapa 3 — Banco de dados
- Definir banco principal para produção: Supabase/Postgres ou outro.
- Garantir que o formulário salve leads no banco.
- Revisar schema e indexação básica.
- Validar fluxo de gravação local e em produção.

## Etapa 4 — Deploy
- Preparar Render.
- Configurar variáveis de ambiente.
- Validar rota `/health`.
- Testar envio do formulário em produção.

## Etapa 5 — Ajustes finais
- Revisão visual mobile.
- Revisão de textos e contatos.
- Checklist de publicação.

## O que preciso do usuário
1. Acesso ou dados do provedor de banco:
   - Supabase recomendado, ou outra opção.
2. Acesso ao deploy:
   - Render, Railway, Fly ou outro escolhido.
3. DNS/domínio:
   - acesso ao `jurisflow.com.br` ou ao registrador.
4. Conteúdo das 2 landing pages:
   - público-alvo principal de cada página,
   - proposta de valor,
   - CTA desejado,
   - WhatsApp/e-mail,
   - prova social/case se houver.
5. Identidade visual:
   - logo, cores, fonte, referência de estilo, se quiser customizar.
6. Preferência de banco:
   - manter SQLite só local e Postgres em produção, ou tudo em Postgres.

## Decisão prática que posso seguir se você quiser velocidade
- Usar Supabase para banco.
- Usar Render para deploy.
- Manter uma landing geral + uma landing para diagnóstico.
- Preencher com textos provisórios se você ainda não tiver o copy final.
