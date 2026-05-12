from __future__ import annotations

import csv
import io
import logging
import os
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

try:
    import psycopg2
except ImportError:  # pragma: no cover - local fallback if dependency is missing
    psycopg2 = None

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-me")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
SQLITE_FILE = DATA_DIR / "jurisflow.db"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DEFAULT_CLIENT_USERNAME = "FabricioDias"
DEFAULT_CLIENT_DISPLAY_NAME = "Fabrício Dias"
DEFAULT_CLIENT_PASSWORD = os.getenv("FABRICIO_PASSWORD", "mengo123")

logger = logging.getLogger(__name__)
if DATABASE_URL:
    logger.warning("JurisFlow storage backend: PostgreSQL/Supabase (DATABASE_URL detected)")
else:
    logger.warning("JurisFlow storage backend: SQLite fallback (DATABASE_URL missing)")

SERVICOS = [
    {
        "slug": "pje-amapa",
        "nome": "Integração direta com o PJe do Amapá",
        "resumo": "Acompanhamento processual direto da fonte, sem depender de checagem manual em portal por portal.",
        "resultado": "O escritório vê movimentações e eventos assim que eles aparecem na origem.",
        "gancho": "Menos conferência manual, mais tempo para atuar no que importa.",
        "impacto": [
            "captura automática da movimentação",
            "visão centralizada do andamento",
            "base pronta para automações futuras",
        ],
    },
    {
        "slug": "prazos-alertas",
        "nome": "Prazos automáticos e alertas imediatos",
        "resumo": "Atualizações relevantes viram alerta para equipe, com prioridade e contexto.",
        "resultado": "Menos risco de perder prazo e menos dependência de alguém lembrar de avisar.",
        "gancho": "A rotina não pode depender de memória e planilha solta.",
        "impacto": [
            "identificação de prazos e datas críticas",
            "notificações para time e responsáveis",
            "priorização automática por urgência",
        ],
    },
    {
        "slug": "dashboard-insights",
        "nome": "Dashboards, acompanhamentos e insights",
        "resumo": "Painel visual para entender fila, status, volume e evolução da operação.",
        "resultado": "Mais clareza para decidir o que precisa de atenção agora.",
        "gancho": "Em vez de sensação, o escritório passa a olhar dado real.",
        "impacto": [
            "visão executiva do escritório",
            "métricas por status e por período",
            "leitura rápida da operação",
        ],
    },
    {
        "slug": "mensagens-clientes",
        "nome": "Mensagens automáticas para clientes",
        "resumo": "O cliente recebe avisos sobre o próprio processo sem precisar ficar cobrando atualização.",
        "resultado": "Menos perguntas repetidas e mais percepção de cuidado e profissionalismo.",
        "gancho": "A comunicação vira parte da operação, não uma tarefa solta.",
        "impacto": [
            "envio de atualizações por gatilho",
            "redução de chamadas e cobranças repetidas",
            "experiência mais organizada para o cliente",
        ],
    },
    {
        "slug": "documentos-drive",
        "nome": "Documentos, PDFs e organização no Drive",
        "resumo": "Baixa documentos, organiza arquivos e integra a rotina com o Drive.",
        "resultado": "Arquivo mais limpo, padronizado e fácil de localizar depois.",
        "gancho": "Documento perdido deixa de ser problema recorrente.",
        "impacto": [
            "download e organização de anexos",
            "padrão de pastas e nomes",
            "integração com Google Drive",
        ],
    },
    {
        "slug": "mensagens-internas",
        "nome": "Mensagens internas e criação de demanda",
        "resumo": "Alertas para funcionários e abertura de demanda a partir da própria atualização do processo.",
        "resultado": "O time não se perde no meio da operação e a próxima ação nasce do evento certo.",
        "gancho": "Menos tarefa esquecida, mais execução guiada pela fonte.",
        "impacto": [
            "notificações internas por evento",
            "criação de demanda conforme atualização",
            "fluxo de trabalho mais confiável",
        ],
    },
]

PACOTES = [
    {
        "nome": "Diagnóstico de automação",
        "descricao": "Mapeamento da operação, gargalos e oportunidade de ganho rápido.",
        "ideal": "Para o escritório que quer clareza antes de investir.",
    },
    {
        "nome": "Projeto sob medida",
        "descricao": "Uma frente crítica resolvida com foco em impacto imediato.",
        "ideal": "Para quem quer sair do manual com rapidez.",
    },
    {
        "nome": "Operação contínua",
        "descricao": "Manutenção e evolução do fluxo conforme a operação cresce.",
        "ideal": "Para quem quer parceria de longo prazo.",
    },
]

PROCESSO = [
    {"titulo": "Diagnóstico", "texto": "Entendemos rotina, volume, risco, gargalos e onde a automação mais ajuda."},
    {"titulo": "Integração", "texto": "Conectamos a fonte, organizamos os dados e deixamos a operação centralizada."},
    {"titulo": "Evolução", "texto": "Evoluímos com dashboards, alertas, cliente e novos fluxos conforme a necessidade."},
]

GANCHOS = [
    {"titulo": "Monitoramento manual", "texto": "Pare de depender de conferência manual diária."},
    {"titulo": "Documentos dispersos", "texto": "Traga o arquivo jurídico para um padrão único."},
    {"titulo": "Operação sem visão", "texto": "Centralize tarefas, status e responsáveis."},
    {"titulo": "Atendimento repetitivo", "texto": "Diminua as mesmas perguntas em loop."},
    {"titulo": "Entrada sem padrão", "texto": "Organize novos casos desde o primeiro contato."},
    {"titulo": "Gestão por sensação", "texto": "Decida com dados da operação e não só intuição."},
]

DIFERENCIAIS = [
    "Especialização em automação para escritórios de advocacia",
    "Experiência prática com rotinas jurídicas e operação de escritório",
    "Soluções sob medida, sem automação genérica",
    "Diagnóstico antes da execução para reduzir retrabalho",
    "Projetos modulares que começam pela dor mais urgente",
    "Suporte e evolução contínua do fluxo implantado",
]

FORM_OPTIONS = {
    "porte": ["Solo/pequeno", "Pequeno", "Médio", "Estruturado"],
    "volume": ["Até 20 casos/processos", "20–50", "50–100", "100+"],
    "objetivo": ["Reduzir trabalho manual", "Organizar a operação", "Melhorar o atendimento", "Tudo isso ao mesmo tempo"],
    "prioridade": ["Diagnóstico", "Projeto sob medida", "Operação contínua"],
}

SISTEMAS = ["Notion", "WhatsApp", "Google Drive", "CRM", "Planilhas", "E-mail", "Outro"]

LANDINGS = {
    "institucional": {
        "eyebrow": "Automação jurídica e portal do cliente",
        "headline_lines": ["Controle real dos processos", "com organização de verdade."],
        "lead": "Conecte o escritório à fonte, reduza trabalho manual e acompanhe processos, alertas e atendimento em um fluxo limpo.",
        "primary_cta": "Solicitar diagnóstico",
        "secondary_cta": "Ver soluções",
        "trust": ["PJe do Amapá", "Banco integrado", "Alertas e dashboards", "Página do cliente"],
        "hero_points": [
            {"title": "Acompanhamento direto da fonte", "text": "Movimentações e prazos entram sem depender de checagem manual."},
            {"title": "Cliente informado", "text": "Atualizações automáticas reduzem cobranças e retrabalho."},
            {"title": "Operação organizada", "text": "Dashboards, alertas e documentos ficam em um fluxo único."},
        ],
        "sections": [
            {"kicker": "Benefícios", "title": "O que a JurisFlow entrega para a operação do escritório.", "description": "Do acompanhamento processual ao atendimento, tudo centralizado e com menos fricção.", "cards": SERVICOS, "type": "servicos"},
            {"kicker": "Página do cliente", "title": "Depois do fechamento, o cliente terá acesso ao próprio espaço.", "description": "A área do cliente vai concentrar dashboard, processos e importação de planilha com login individual.", "cards": [
                {"titulo": "Dashboard e status", "texto": "O cliente vê o andamento sem precisar ficar pedindo atualização."},
                {"titulo": "Documentos e histórico", "texto": "Tudo fica organizado para consulta rápida e segura."},
                {"titulo": "Sincronização com planilha", "texto": "A operação interna pode importar e atualizar a base com poucos cliques."},
            ], "type": "cards"},
            {"kicker": "Como a implantação começa", "title": "Do diagnóstico à evolução contínua.", "description": "Começamos pela dor principal e avançamos por etapas, sem tentar fazer tudo de uma vez.", "cards": PROCESSO, "type": "steps"},
        ],
        "cta_title_lines": ["Quando a operação está espalhada,", "o diagnóstico vira controle."],
        "cta_text": "A partir daí fica mais fácil vender a solução certa, com benefício claro para o cliente final.",
        "cta_href": "/diagnostico",
        "cta_label": "Montar diagnóstico",
    },
    "diagnostico": {
        "eyebrow": "Diagnóstico inicial",
        "headline": "Descubra onde o escritório perde tempo e qual automação gera resultado primeiro.",
        "lead": "Um formulário para organizar o primeiro contato e levar a conversa para o diagnóstico com contexto real.",
        "primary_cta": "Abrir diagnóstico",
        "secondary_cta": "Conhecer soluções",
        "trust": ["Formulário organizado", "Banco integrado", "Contato qualificado", "Pronto para produção"],
        "hero_points": [
            {"title": "Contexto", "text": "Menos ruído e mais informação útil para a primeira conversa."},
            {"title": "Qualificação", "text": "Porte, volume, objetivo e gargalo em um só lugar."},
            {"title": "Próximo passo", "text": "A conversa já começa com contexto real."},
        ],
        "sections": [
            {"kicker": "O que vamos mapear", "title": "Antes de vender automação, é preciso entender a operação.", "description": "O diagnóstico organiza as informações que importam para propor a solução certa.", "cards": [
                {"titulo": "Tempo perdido", "texto": "Onde o time ainda faz conferências manuais."},
                {"titulo": "Ferramentas atuais", "texto": "Quais sistemas já fazem parte da rotina."},
                {"titulo": "Prioridade inicial", "texto": "Qual frente faz mais sentido começar."},
            ], "type": "cards"},
            {"kicker": "Resultado esperado", "title": "Uma proposta forte começa com contexto real.", "description": "Depois do envio, o contato fica organizado para a venda e acompanhamento.", "cards": [
                {"titulo": "Contato organizado", "texto": "Dados salvos em banco de dados e prontos para análise."},
                {"titulo": "Conversa melhor", "texto": "A primeira reunião já nasce com contexto."},
                {"titulo": "Escalável", "texto": "Base pronta para dashboard, automação e produção."},
            ], "type": "cards"},
        ],
        "cta_title": "Pronto para organizar contatos mais qualificados?",
        "cta_text": "Use esta página como porta de entrada para o diagnóstico.",
        "cta_href": "/diagnostico",
        "cta_label": "Ir para o diagnóstico",
    },
}

PROCESS_IMPORT_COLUMNS = {
    "numero": ["numero", "numero_processo", "processo", "processo_numero", "n_processo"],
    "cliente": ["cliente", "nome_cliente", "parte", "escritorio", "assunto"],
    "tribunal": ["tribunal", "orgao", "vara", "foro"],
    "area": ["area", "ramo", "area_juridica"],
    "status": ["status", "situacao", "fase"],
    "responsavel": ["responsavel", "advogado", "gestor"],
    "ultima_movimentacao": ["ultima_movimentacao", "movimentacao", "ultima_atualizacao", "atualizado_em"],
    "fonte": ["fonte", "origem", "planilha"],
}


def _connect():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, sslmode=os.getenv("DB_SSLMODE", "require"))
    return sqlite3.connect(SQLITE_FILE)


def _exec_sql(cursor, sql: str, params: tuple | list = ()):  # works for sqlite and psycopg2
    cursor.execute(sql.replace("?", "%s") if DATABASE_URL else sql, params)


def fetch_all(sql: str, params: tuple | list = ()) -> list[dict[str, object]]:
    if DATABASE_URL:
        with _connect() as conn:
            with conn.cursor() as cur:
                _exec_sql(cur, sql, params)
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
    with _connect() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def fetch_one(sql: str, params: tuple | list = ()) -> dict[str, object] | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def _safe_next_url(target: str | None) -> str:
    if not target:
        return url_for("dashboard")
    if target.startswith("//"):
        return url_for("dashboard")
    if not target.startswith("/"):
        return url_for("dashboard")
    return target


def _upsert_default_client_user() -> None:
    password_hash = generate_password_hash(DEFAULT_CLIENT_PASSWORD)
    if DATABASE_URL:
        with _connect() as conn:
            with conn.cursor() as cur:
                _exec_sql(cur, "SELECT id FROM usuarios WHERE username = ?", (DEFAULT_CLIENT_USERNAME,))
                existing = cur.fetchone()
                if existing:
                    _exec_sql(
                        cur,
                        """
                        UPDATE usuarios
                        SET display_name = ?, password_hash = ?, role = ?, active = ?, updated_at = ?
                        WHERE username = ?
                        """,
                        [DEFAULT_CLIENT_DISPLAY_NAME, password_hash, "cliente", True, _iso_now(), DEFAULT_CLIENT_USERNAME],
                    )
                else:
                    _exec_sql(
                        cur,
                        """
                        INSERT INTO usuarios (username, display_name, password_hash, role, active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        [DEFAULT_CLIENT_USERNAME, DEFAULT_CLIENT_DISPLAY_NAME, password_hash, "cliente", True, _iso_now(), _iso_now()],
                    )
            conn.commit()
        return

    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE username = ?", (DEFAULT_CLIENT_USERNAME,))
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """
                UPDATE usuarios
                SET display_name = ?, password_hash = ?, role = ?, active = ?, updated_at = ?
                WHERE username = ?
                """,
                [DEFAULT_CLIENT_DISPLAY_NAME, password_hash, "cliente", 1, _iso_now(), DEFAULT_CLIENT_USERNAME],
            )
        else:
            cur.execute(
                """
                INSERT INTO usuarios (username, display_name, password_hash, role, active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [DEFAULT_CLIENT_USERNAME, DEFAULT_CLIENT_DISPLAY_NAME, password_hash, "cliente", 1, _iso_now(), _iso_now()],
            )
        conn.commit()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Faça login para acessar essa área.")
            return redirect(url_for("cliente_page", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def _iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_date(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%d/%m/%Y %H:%M"):
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue
    return None


def _normalize_column(row: dict[str, str], aliases: list[str]) -> str:
    lowered = {key.lower().strip(): value for key, value in row.items()}
    for alias in aliases:
        value = lowered.get(alias)
        if value:
            return value.strip()
    return ""


def _status_bucket(value: str) -> str:
    normalized = (value or "").lower().strip()
    if not normalized:
        return "Sem status"
    if any(token in normalized for token in ("anal", "analis", "revis", "esper", "fila")):
        return "Em análise"
    if any(token in normalized for token in ("arquiv", "encerr", "final")):
        return "Arquivado"
    if any(token in normalized for token in ("atual", "mov", "andament", "moviment")):
        return "Atualizado"
    if any(token in normalized for token in ("parad", "aguard", "pend", "suspens")):
        return "Aguardando"
    return "Em análise"


def _seed_demo_processos() -> None:
    if DATABASE_URL:
        return
    if fetch_one("SELECT id FROM processos LIMIT 1"):
        return

    demo_rows = [
        {
            "numero": "0001234-45.2024.8.00.0001",
            "cliente": "Restaurante Aurora",
            "tribunal": "TJ/AP",
            "area": "Cível",
            "status": "Em análise",
            "responsavel": "Dra. Marina",
            "ultima_movimentacao": (datetime.now() - timedelta(hours=4)).isoformat(timespec="minutes"),
            "fonte": "planilha",
            "descricao": "Processo aguardando conferência de despacho.",
        },
        {
            "numero": "0005821-12.2023.5.01.0032",
            "cliente": "Pizzaria Central",
            "tribunal": "TRT-1",
            "area": "Trabalhista",
            "status": "Atualizado",
            "responsavel": "Dr. Lucas",
            "ultima_movimentacao": (datetime.now() - timedelta(days=1)).isoformat(timespec="minutes"),
            "fonte": "pje",
            "descricao": "Nova publicação disponível e processo pronto para leitura.",
        },
        {
            "numero": "0008899-77.2022.8.24.0000",
            "cliente": "Grupo Horizonte",
            "tribunal": "TJ/SC",
            "area": "Empresarial",
            "status": "Aguardando",
            "responsavel": "Dra. Paula",
            "ultima_movimentacao": (datetime.now() - timedelta(days=3)).isoformat(timespec="minutes"),
            "fonte": "proc",
            "descricao": "Aguardando retorno externo antes da próxima movimentação.",
        },
    ]

    with _connect() as conn:
        for row in demo_rows:
            if DATABASE_URL:
                cur = conn.cursor()
                _exec_sql(
                    cur,
                    """
                    INSERT INTO processos (numero, cliente, tribunal, area, status, responsavel, ultima_movimentacao, fonte, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    RETURNING id
                    """,
                    [
                        row["numero"],
                        row["cliente"],
                        row["tribunal"],
                        row["area"],
                        row["status"],
                        row["responsavel"],
                        row["ultima_movimentacao"],
                        row["fonte"],
                        _iso_now(),
                        _iso_now(),
                    ],
                )
                processo_id = cur.fetchone()[0]
            else:
                cur = conn.execute(
                    """
                    INSERT INTO processos (numero, cliente, tribunal, area, status, responsavel, ultima_movimentacao, fonte, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        row["numero"],
                        row["cliente"],
                        row["tribunal"],
                        row["area"],
                        row["status"],
                        row["responsavel"],
                        row["ultima_movimentacao"],
                        row["fonte"],
                        _iso_now(),
                        _iso_now(),
                    ],
                )
                processo_id = cur.lastrowid
            _exec_sql(
                cur,
                """
                INSERT INTO processo_eventos (processo_id, timestamp, titulo, descricao, origem)
                VALUES (?, ?, ?, ?, ?)
                """,
                [processo_id, row["ultima_movimentacao"], "Movimentação importada", row["descricao"], row["fonte"]],
            )
        conn.commit()


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DATABASE_URL:
        if psycopg2 is None:
            raise RuntimeError("psycopg2 is required when DATABASE_URL is set")
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS leads (
                        id BIGSERIAL PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        nome TEXT NOT NULL,
                        escritorio TEXT NOT NULL,
                        cargo TEXT,
                        email TEXT NOT NULL,
                        whatsapp TEXT NOT NULL,
                        cidade_estado TEXT,
                        area TEXT,
                        porte TEXT,
                        volume TEXT,
                        objetivo TEXT,
                        prioridade TEXT,
                        sistemas TEXT,
                        principal_gargalo TEXT NOT NULL,
                        observacoes TEXT,
                        consentimento TEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS processos (
                        id BIGSERIAL PRIMARY KEY,
                        numero TEXT NOT NULL UNIQUE,
                        cliente TEXT NOT NULL,
                        tribunal TEXT,
                        area TEXT,
                        status TEXT NOT NULL,
                        responsavel TEXT,
                        ultima_movimentacao TEXT,
                        fonte TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS processo_eventos (
                        id BIGSERIAL PRIMARY KEY,
                        processo_id BIGINT NOT NULL REFERENCES processos(id) ON DELETE CASCADE,
                        timestamp TEXT NOT NULL,
                        titulo TEXT NOT NULL,
                        descricao TEXT NOT NULL,
                        origem TEXT
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS usuarios (
                        id BIGSERIAL PRIMARY KEY,
                        username TEXT NOT NULL UNIQUE,
                        display_name TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'cliente',
                        active BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                cur.execute("CREATE INDEX IF NOT EXISTS usuarios_username_idx ON usuarios (username)")
                cur.execute("CREATE INDEX IF NOT EXISTS processos_status_idx ON processos (status)")
                cur.execute("CREATE INDEX IF NOT EXISTS processos_numero_idx ON processos (numero)")
            conn.commit()
        _upsert_default_client_user()
        return

    with sqlite3.connect(SQLITE_FILE) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                nome TEXT NOT NULL,
                escritorio TEXT NOT NULL,
                cargo TEXT,
                email TEXT NOT NULL,
                whatsapp TEXT NOT NULL,
                cidade_estado TEXT,
                area TEXT,
                porte TEXT,
                volume TEXT,
                objetivo TEXT,
                prioridade TEXT,
                sistemas TEXT,
                principal_gargalo TEXT NOT NULL,
                observacoes TEXT,
                consentimento TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'cliente',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS processos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT NOT NULL UNIQUE,
                cliente TEXT NOT NULL,
                tribunal TEXT,
                area TEXT,
                status TEXT NOT NULL,
                responsavel TEXT,
                ultima_movimentacao TEXT,
                fonte TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS processo_eventos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                processo_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                titulo TEXT NOT NULL,
                descricao TEXT NOT NULL,
                origem TEXT,
                FOREIGN KEY (processo_id) REFERENCES processos(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS usuarios_username_idx ON usuarios (username);
            CREATE INDEX IF NOT EXISTS processos_status_idx ON processos (status);
            CREATE INDEX IF NOT EXISTS processos_numero_idx ON processos (numero);
            """
        )
        conn.commit()
    _upsert_default_client_user()
    _seed_demo_processos()


def save_lead(payload: dict[str, str]) -> None:
    ensure_storage()
    if DATABASE_URL:
        with _connect() as conn:
            with conn.cursor() as cur:
                _exec_sql(
                    cur,
                    """
                    INSERT INTO leads (
                        timestamp, nome, escritorio, cargo, email, whatsapp, cidade_estado, area,
                        porte, volume, objetivo, prioridade, sistemas, principal_gargalo, observacoes, consentimento
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        payload["timestamp"],
                        payload["nome"],
                        payload["escritorio"],
                        payload["cargo"],
                        payload["email"],
                        payload["whatsapp"],
                        payload["cidade_estado"],
                        payload["area"],
                        payload["porte"],
                        payload["volume"],
                        payload["objetivo"],
                        payload["prioridade"],
                        payload["sistemas"],
                        payload["principal_gargalo"],
                        payload["observacoes"],
                        payload["consentimento"],
                    ],
                )
            conn.commit()
        logger.warning("Lead salvo em PostgreSQL/Supabase")
        return

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO leads (
                timestamp, nome, escritorio, cargo, email, whatsapp, cidade_estado, area,
                porte, volume, objetivo, prioridade, sistemas, principal_gargalo, observacoes, consentimento
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                payload["timestamp"],
                payload["nome"],
                payload["escritorio"],
                payload["cargo"],
                payload["email"],
                payload["whatsapp"],
                payload["cidade_estado"],
                payload["area"],
                payload["porte"],
                payload["volume"],
                payload["objetivo"],
                payload["prioridade"],
                payload["sistemas"],
                payload["principal_gargalo"],
                payload["observacoes"],
                payload["consentimento"],
            ],
        )
        conn.commit()
        logger.warning("Lead salvo em SQLite fallback")


def save_process_rows(rows: list[dict[str, str]]) -> dict[str, int]:
    ensure_storage()
    stats = {"inserted": 0, "updated": 0, "events": 0, "ignored": 0}
    if not rows:
        return stats

    if DATABASE_URL:
        with _connect() as conn:
            with conn.cursor() as cur:
                for row in rows:
                    numero = row.get("numero", "").strip()
                    if not numero:
                        stats["ignored"] += 1
                        continue
                    cliente = (row.get("cliente", "") or numero).strip()
                    tribunal = row.get("tribunal", "").strip()
                    area = row.get("area", "").strip()
                    status = _status_bucket(row.get("status", ""))
                    responsavel = row.get("responsavel", "").strip()
                    ultima = row.get("ultima_movimentacao", "").strip() or _iso_now()
                    fonte = row.get("fonte", "").strip() or "planilha"

                    _exec_sql(cur, "SELECT id FROM processos WHERE numero = ?", (numero,))
                    existing = cur.fetchone()
                    if existing:
                        processo_id = existing[0]
                        _exec_sql(
                            cur,
                            """
                            UPDATE processos
                            SET cliente = ?, tribunal = ?, area = ?, status = ?, responsavel = ?,
                                ultima_movimentacao = ?, fonte = ?, updated_at = ?
                            WHERE id = ?
                            """,
                            [cliente, tribunal, area, status, responsavel, ultima, fonte, _iso_now(), processo_id],
                        )
                        stats["updated"] += 1
                    else:
                        _exec_sql(
                            cur,
                            """
                            INSERT INTO processos (
                                numero, cliente, tribunal, area, status, responsavel, ultima_movimentacao,
                                fonte, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            RETURNING id
                            """,
                            [numero, cliente, tribunal, area, status, responsavel, ultima, fonte, _iso_now(), _iso_now()],
                        )
                        processo_id = cur.fetchone()[0]
                        stats["inserted"] += 1

                    _exec_sql(
                        cur,
                        """
                        INSERT INTO processo_eventos (processo_id, timestamp, titulo, descricao, origem)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        [processo_id, ultima, "Sincronizado da planilha", f"Processo {numero} atualizado para {status}.", fonte],
                    )
                    stats["events"] += 1
            conn.commit()
        return stats

    with _connect() as conn:
        for row in rows:
            numero = row.get("numero", "").strip()
            if not numero:
                stats["ignored"] += 1
                continue
            cliente = (row.get("cliente", "") or numero).strip()
            tribunal = row.get("tribunal", "").strip()
            area = row.get("area", "").strip()
            status = _status_bucket(row.get("status", ""))
            responsavel = row.get("responsavel", "").strip()
            ultima = row.get("ultima_movimentacao", "").strip() or _iso_now()
            fonte = row.get("fonte", "").strip() or "planilha"

            existing = conn.execute("SELECT id FROM processos WHERE numero = ?", (numero,)).fetchone()
            if existing:
                processo_id = existing[0]
                conn.execute(
                    """
                    UPDATE processos
                    SET cliente = ?, tribunal = ?, area = ?, status = ?, responsavel = ?,
                        ultima_movimentacao = ?, fonte = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    [cliente, tribunal, area, status, responsavel, ultima, fonte, _iso_now(), processo_id],
                )
                stats["updated"] += 1
            else:
                cur = conn.execute(
                    """
                    INSERT INTO processos (
                        numero, cliente, tribunal, area, status, responsavel, ultima_movimentacao,
                        fonte, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [numero, cliente, tribunal, area, status, responsavel, ultima, fonte, _iso_now(), _iso_now()],
                )
                processo_id = cur.lastrowid
                stats["inserted"] += 1

            conn.execute(
                """
                INSERT INTO processo_eventos (processo_id, timestamp, titulo, descricao, origem)
                VALUES (?, ?, ?, ?, ?)
                """,
                [processo_id, ultima, "Sincronizado da planilha", f"Processo {numero} atualizado para {status}.", fonte],
            )
            stats["events"] += 1
        conn.commit()
    return stats


def _status_series(processos: list[dict[str, object]]) -> list[dict[str, object]]:
    counts = Counter(_status_bucket(str(item.get("status", ""))) for item in processos)
    labels = [
        ("Em análise", "#f3c74f"),
        ("Atualizado", "#6cb9ff"),
        ("Aguardando", "#8b7cff"),
        ("Arquivado", "#c4c8d0"),
        ("Sem status", "#d9aa5c"),
    ]
    max_value = max([counts.get(label, 0) for label, _ in labels] or [1]) or 1
    series = []
    for label, color in labels:
        value = counts.get(label, 0)
        series.append({"label": label, "value": value, "height": max(16, round(value / max_value * 100)), "color": color})
    return series


def _activity_series(processos: list[dict[str, object]]) -> list[dict[str, object]]:
    now = datetime.now()
    months = []
    keys = []
    month_labels = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    for offset in range(5, -1, -1):
        anchor = (now.replace(day=1) - timedelta(days=offset * 31)).replace(day=1)
        months.append(month_labels[anchor.month - 1])
        keys.append(anchor.strftime("%Y-%m"))
    counts = Counter()
    for item in processos:
        parsed = _parse_date(item.get("updated_at") or item.get("ultima_movimentacao") or item.get("created_at"))
        if parsed:
            counts[parsed.strftime("%Y-%m")] += 1
    max_value = max([counts.get(key, 0) for key in keys] or [1]) or 1
    return [
        {"label": label, "value": counts.get(key, 0), "height": max(16, round(counts.get(key, 0) / max_value * 100))}
        for label, key in zip(months, keys)
    ]


def _demo_processes() -> tuple[list[dict[str, str]], dict[str, object]]:
    rows = [
        {
            "numero_processo": "0001234-45.2024.8.00.0001",
            "processo": "Ação de cobrança - Restaurante Aurora",
            "numero": "0001234-45.2024.8.00.0001",
            "cliente": "Restaurante Aurora",
            "nome_cliente": "Restaurante Aurora",
            "tribunal": "TJ/AP",
            "foro": "Macapá",
            "vara": "3ª Vara Cível",
            "area": "Cível",
            "area_juridica": "Cível",
            "status": "Em análise",
            "fase": "Análise",
            "situacao": "Pendente",
            "responsavel": "Dra. Marina",
            "advogado": "Dra. Marina",
            "ultima_movimentacao": "2026-05-12 08:10",
            "atualizado_em": "2026-05-12 08:10",
        },
        {
            "numero_processo": "0005821-12.2023.5.01.0032",
            "processo": "Reclamação trabalhista - Pizzaria Central",
            "numero": "0005821-12.2023.5.01.0032",
            "cliente": "Pizzaria Central",
            "nome_cliente": "Pizzaria Central",
            "tribunal": "TRT-1",
            "foro": "Rio de Janeiro",
            "vara": "12ª Vara do Trabalho",
            "area": "Trabalhista",
            "area_juridica": "Trabalhista",
            "status": "Atualizado",
            "fase": "Publicação recebida",
            "situacao": "Em curso",
            "responsavel": "Dr. Lucas",
            "advogado": "Dr. Lucas",
            "ultima_movimentacao": "2026-05-11 16:40",
            "atualizado_em": "2026-05-11 16:40",
        },
        {
            "numero_processo": "0008899-77.2022.8.24.0000",
            "processo": "Execução empresarial - Grupo Horizonte",
            "numero": "0008899-77.2022.8.24.0000",
            "cliente": "Grupo Horizonte",
            "nome_cliente": "Grupo Horizonte",
            "tribunal": "TJ/SC",
            "foro": "Florianópolis",
            "vara": "1ª Vara Empresarial",
            "area": "Empresarial",
            "area_juridica": "Empresarial",
            "status": "Aguardando",
            "fase": "Aguardando retorno",
            "situacao": "Em espera",
            "responsavel": "Dra. Paula",
            "advogado": "Dra. Paula",
            "ultima_movimentacao": "2026-05-09 10:25",
            "atualizado_em": "2026-05-09 10:25",
        },
        {
            "numero_processo": "0042211-88.2021.8.26.0100",
            "processo": "Renegociação contratual - Hotel Vênus",
            "numero": "0042211-88.2021.8.26.0100",
            "cliente": "Hotel Vênus",
            "nome_cliente": "Hotel Vênus",
            "tribunal": "TJ/SP",
            "foro": "São Paulo",
            "vara": "6ª Vara Cível",
            "area": "Cível",
            "area_juridica": "Cível",
            "status": "Atualizado",
            "fase": "Aguardando assinatura",
            "situacao": "Em negociação",
            "responsavel": "Dra. Marina",
            "advogado": "Dra. Marina",
            "ultima_movimentacao": "2026-05-10 14:55",
            "atualizado_em": "2026-05-10 14:55",
        },
        {
            "numero_processo": "0011144-10.2024.8.16.0001",
            "processo": "Cumprimento de sentença - Clínica Sorriso",
            "numero": "0011144-10.2024.8.16.0001",
            "cliente": "Clínica Sorriso",
            "nome_cliente": "Clínica Sorriso",
            "tribunal": "TJ/PR",
            "foro": "Curitiba",
            "vara": "2ª Vara Empresarial",
            "area": "Empresarial",
            "area_juridica": "Empresarial",
            "status": "Em análise",
            "fase": "Leitura de intimação",
            "situacao": "Pendente",
            "responsavel": "Dr. Felipe",
            "advogado": "Dr. Felipe",
            "ultima_movimentacao": "2026-05-12 09:35",
            "atualizado_em": "2026-05-12 09:35",
        },
    ]
    by_client = Counter(row["nome_cliente"] for row in rows)
    by_area = Counter(row["area_juridica"] for row in rows)
    by_lawyer = Counter(row["advogado"] for row in rows)
    by_tribunal = Counter(row["tribunal"] for row in rows)

    demo = []
    for row in rows:
        demo.append(
            {
                **row,
                "insight": f"{row['status']} · {row['fase']} · {row['situacao']}",
                "cruzamento": f"{row['nome_cliente']} ({by_client[row['nome_cliente']]}x) · {row['area_juridica']} ({by_area[row['area_juridica']]}x) · {row['advogado']} ({by_lawyer[row['advogado']]}x)",
            }
        )

    summary = {
        "total": 17,
        "clientes": 17,
        "areas": 3,
        "advogados": 4,
        "tribunais": 4,
        "em_analise": 15,
        "atualizados": 1,
        "aguardando": 1,
        "arquivados": 0,
        "top_area": "Cível",
        "top_area_count": 8,
        "top_advogado": "Dra. Marina",
        "top_advogado_count": 7,
        "top_tribunal": "TJ/SP",
        "top_tribunal_count": 6,
        "status_breakdown": [
            {"label": "Em análise", "count": 15},
            {"label": "Atualizados", "count": 1},
            {"label": "Aguardando", "count": 1},
            {"label": "Arquivados", "count": 0},
        ],
        "lawyer_breakdown": [
            {"label": "Dra. Marina", "count": 7, "hint": "Cível e Empresarial"},
            {"label": "Dr. Lucas", "count": 5, "hint": "Trabalhista e Cível"},
            {"label": "Dra. Paula", "count": 3, "hint": "Empresarial"},
            {"label": "Dr. Felipe", "count": 2, "hint": "Cível"},
        ],
        "area_breakdown": [
            {"label": "Cível", "count": 8},
            {"label": "Trabalhista", "count": 5},
            {"label": "Empresarial", "count": 4},
        ],
    }
    return demo, summary


def _recent_events(limit: int = 8) -> list[dict[str, object]]:
    ensure_storage()
    return fetch_all(
        """
        SELECT e.*, p.numero, p.cliente, p.status AS processo_status
        FROM processo_eventos e
        JOIN processos p ON p.id = e.processo_id
        ORDER BY e.timestamp DESC, e.id DESC
        LIMIT ?
        """,
        (limit,),
    )


def _build_dashboard_context() -> dict[str, object]:
    ensure_storage()
    processos = fetch_all("SELECT * FROM processos ORDER BY COALESCE(updated_at, created_at) DESC, id DESC")
    events = _recent_events(8)

    total = len(processos)
    em_analise = sum(1 for item in processos if _status_bucket(str(item.get("status", ""))) == "Em análise")
    atualizados = sum(1 for item in processos if _status_bucket(str(item.get("status", ""))) == "Atualizado")
    aguardando = sum(1 for item in processos if _status_bucket(str(item.get("status", ""))) == "Aguardando")
    arquivados = sum(1 for item in processos if _status_bucket(str(item.get("status", ""))) == "Arquivado")
    clientes = len({str(item.get("cliente", "")).strip() for item in processos if str(item.get("cliente", "")).strip()})

    return {
        "body_class": "dashboard-mode",
        "stats": {
            "total": total,
            "clientes": clientes,
            "em_analise": em_analise,
            "atualizados": atualizados,
            "aguardando": aguardando,
            "arquivados": arquivados,
        },
        "processos": processos[:10],
        "all_processos": processos,
        "recent_events": events,
        "status_series": _status_series(processos),
        "activity_series": _activity_series(processos),
        "insights": [
            {"title": "Processos em análise", "value": em_analise, "hint": "precisam de leitura ativa"},
            {"title": "Atualizados", "value": atualizados, "hint": "com movimentação recente"},
            {"title": "Aguardando", "value": aguardando, "hint": "dependem de retorno externo"},
            {"title": "Arquivados", "value": arquivados, "hint": "já saíram da fila ativa"},
        ],
    }


def _build_demo_context(tab: str = "painel") -> dict[str, object]:
    demo_processos, demo_summary = _demo_processes()
    demo_events = [
        {
            "numero": row["numero_processo"],
            "cliente": row["nome_cliente"],
            "timestamp": row["atualizado_em"],
            "descricao": row["ultima_movimentacao"],
            "processo_status": row["status"],
        }
        for row in demo_processos[:8]
    ]
    tab_data = {
        "painel": {
            "eyebrow": "Demonstração pública",
            "title": "Painel de controle simulado",
            "text": "Veja uma amostra fixa da operação: os dados não dependem de login e servem para apresentar o valor do portal.",
        },
        "processos": {
            "eyebrow": "Demonstração pública",
            "title": "Processos simulados",
            "text": "Lista demonstrativa com números, cliente, tribunal, área, status, responsável e cruzamentos preparados para apresentação.",
        },
        "historico": {
            "eyebrow": "Demonstração pública",
            "title": "Histórico simulado",
            "text": "Linha do tempo fixa com eventos de exemplo para mostrar como a atualização chega e como a leitura fica organizada.",
        },
        "insights": {
            "eyebrow": "Demonstração pública",
            "title": "Insights simulados",
            "text": "Resumo executivo com cruzamentos por advogado, área, tribunal e status — tudo fixo para a demonstração.",
        },
    }
    current = tab_data.get(tab, tab_data["painel"])
    return {
        "body_class": "dashboard-mode",
        "demo_tab": tab,
        "demo_tab_eyebrow": current["eyebrow"],
        "demo_tab_title": current["title"],
        "demo_tab_text": current["text"],
        "demo_events": demo_events,
        "demo_processos": demo_processos,
        "demo_summary": demo_summary,
    }


def _build_history_context() -> dict[str, object]:
    events = _recent_events(30)
    latest = events[0]["timestamp"] if events else None
    return {
        "body_class": "dashboard-mode",
        "events": events,
        "stats": {
            "total": len(events),
            "latest": latest,
        },
    }


@app.context_processor
def inject_globals():
    current_user = None
    if session.get("user_id"):
        current_user = {
            "id": session.get("user_id"),
            "username": session.get("username"),
            "display_name": session.get("display_name"),
            "role": session.get("role"),
        }
    return {
        "marca": "JurisFlow",
        "proposta": "Automação sob medida para escritórios de advocacia que querem reduzir trabalho manual, organizar processos e melhorar o atendimento.",
        "diferenciais": DIFERENCIAIS,
        "servicos": SERVICOS,
        "pacotes": PACOTES,
        "processo": PROCESSO,
        "ganchos": GANCHOS,
        "current_user": current_user,
        "is_authenticated": bool(current_user),
    }


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/")
def home():
    return render_template("landing.html", landing=LANDINGS["institucional"], slug="institucional")


@app.route("/lp/<slug>")
def landing_page(slug: str):
    landing = LANDINGS.get(slug)
    if landing is None:
        return render_template("landing.html", landing=LANDINGS["institucional"], slug="institucional"), 404
    return render_template("landing.html", landing=landing, slug=slug)


@app.route("/servicos")
def servicos_page():
    return render_template("servicos.html")



@app.route("/cliente")
def cliente_page():
    return render_template("cliente.html", body_class="dashboard-mode", next_url=request.args.get("next", url_for("dashboard")))


@app.route("/login", methods=["POST"])
def login():
    ensure_storage()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    next_url = _safe_next_url(request.form.get("next") or request.args.get("next"))

    if not username or not password:
        flash("Informe usuário e senha.")
        return redirect(url_for("cliente_page", next=next_url))

    user = fetch_one(
        "SELECT id, username, display_name, password_hash, role, active FROM usuarios WHERE username = ?",
        (username,),
    )
    if not user or not user.get("active") or not check_password_hash(str(user["password_hash"]), password):
        flash("Usuário ou senha inválidos.")
        return redirect(url_for("cliente_page", next=next_url))

    session.clear()
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["display_name"] = user["display_name"]
    session["role"] = user["role"]
    flash(f"Bem-vindo, {user['display_name']}.")
    return redirect(next_url)


@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da área do cliente.")
    return redirect(url_for("cliente_page"))


@app.route("/diagnostico", methods=["GET", "POST"])
def diagnostico():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        escritorio = request.form.get("escritorio", "").strip()
        email = request.form.get("email", "").strip()
        whatsapp = request.form.get("whatsapp", "").strip()
        gargalo = request.form.get("principal_gargalo", "").strip()
        consentimento = request.form.get("consentimento")

        if not all([nome, escritorio, email, whatsapp, gargalo, consentimento]):
            flash("Preencha os campos obrigatórios para enviar o diagnóstico.")
            return redirect(url_for("diagnostico"))

        payload = {
            "timestamp": _iso_now(),
            "nome": nome,
            "escritorio": escritorio,
            "cargo": request.form.get("cargo", "").strip(),
            "email": email,
            "whatsapp": whatsapp,
            "cidade_estado": request.form.get("cidade_estado", "").strip(),
            "area": request.form.get("area", "").strip(),
            "porte": request.form.get("porte", "").strip(),
            "volume": request.form.get("volume", "").strip(),
            "objetivo": request.form.get("objetivo", "").strip(),
            "prioridade": request.form.get("prioridade", "").strip(),
            "sistemas": ", ".join(request.form.getlist("sistemas")),
            "principal_gargalo": gargalo,
            "observacoes": request.form.get("observacoes", "").strip(),
            "consentimento": "sim",
        }
        save_lead(payload)
        flash("Diagnóstico enviado com sucesso. Vamos analisar a operação do escritório.")
        return redirect(url_for("diagnostico"))

    return render_template("diagnostico.html", form_options=FORM_OPTIONS, sistemas=SISTEMAS)


@app.route("/contato")
def contato():
    return render_template("contato.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", **_build_dashboard_context())


@app.route("/demonstracao")
@app.route("/demonstracao/painel")
def demonstracao():
    return render_template("demonstracao.html", **_build_demo_context("painel"))


@app.route("/demonstracao/processos")
def demonstracao_processos():
    return render_template("demonstracao.html", **_build_demo_context("processos"))


@app.route("/demonstracao/historico")
def demonstracao_historico():
    return render_template("demonstracao.html", **_build_demo_context("historico"))


@app.route("/demonstracao/insights")
def demonstracao_insights():
    return render_template("demonstracao.html", **_build_demo_context("insights"))


@app.route("/insights")
@login_required
def insights():
    return render_template("insights.html", **_build_dashboard_context())


@app.route("/historico")
@login_required
def historico():
    return render_template("historico.html", **_build_history_context())


@app.route("/processos")
@login_required
def processos_page():
    return render_template("processos.html", **_build_dashboard_context())


@app.route("/processos/<int:processo_id>")
@login_required
def processo_detalhe(processo_id: int):
    ensure_storage()
    processo = fetch_one("SELECT * FROM processos WHERE id = ?", (processo_id,))
    if processo is None:
        return render_template("processo_detail.html", processo=None, events=[], body_class="dashboard-mode"), 404
    events = fetch_all(
        """
        SELECT * FROM processo_eventos
        WHERE processo_id = ?
        ORDER BY timestamp DESC, id DESC
        """,
        (processo_id,),
    )
    return render_template("processo_detail.html", processo=processo, events=events, body_class="dashboard-mode")


@app.route("/processos/importar", methods=["GET", "POST"])
@login_required
def importar_processos():
    if request.method == "POST":
        arquivo = request.files.get("arquivo")
        if arquivo is None or not arquivo.filename.lower().endswith((".csv", ".txt")):
            flash("Envie um arquivo CSV com a exportação da planilha.")
            return redirect(url_for("importar_processos"))

        stream = io.TextIOWrapper(arquivo.stream, encoding="utf-8-sig", newline="")
        reader = csv.DictReader(stream)
        rows: list[dict[str, str]] = []
        for raw_row in reader:
            row = {key.lower().strip(): (value or "").strip() for key, value in raw_row.items()}
            numero = _normalize_column(row, PROCESS_IMPORT_COLUMNS["numero"])
            if not numero:
                continue
            rows.append(
                {
                    "numero": numero,
                    "cliente": _normalize_column(row, PROCESS_IMPORT_COLUMNS["cliente"]),
                    "tribunal": _normalize_column(row, PROCESS_IMPORT_COLUMNS["tribunal"]),
                    "area": _normalize_column(row, PROCESS_IMPORT_COLUMNS["area"]),
                    "status": _normalize_column(row, PROCESS_IMPORT_COLUMNS["status"]),
                    "responsavel": _normalize_column(row, PROCESS_IMPORT_COLUMNS["responsavel"]),
                    "ultima_movimentacao": _normalize_column(row, PROCESS_IMPORT_COLUMNS["ultima_movimentacao"]),
                    "fonte": _normalize_column(row, PROCESS_IMPORT_COLUMNS["fonte"]) or "planilha",
                }
            )

        stats = save_process_rows(rows)
        flash(f"Sincronização concluída: {stats['inserted']} novos, {stats['updated']} atualizados, {stats['events']} eventos salvos.")
        return redirect(url_for("dashboard"))

    return render_template("import_processos.html", body_class="dashboard-mode")


ensure_storage()

if __name__ == "__main__":
    app.run(debug=True)
