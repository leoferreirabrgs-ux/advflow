from __future__ import annotations

import csv
import io
import os
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for

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

SERVICOS = [
    {
        "slug": "monitoramento",
        "nome": "Monitoramento de processos",
        "resumo": "Acompanhamento automático de movimentações e prazos com leitura da fonte.",
        "resultado": "Menos conferência manual e mais controle sobre o que mudou.",
        "gancho": "O time ainda abre portal por portal para descobrir as novidades?",
        "impacto": [
            "captura de movimentações e prazos",
            "alertas para equipe e cliente",
            "histórico centralizado por processo",
        ],
    },
    {
        "slug": "documentos",
        "nome": "Arquivamento inteligente",
        "resumo": "Organização de anexos, peças e documentos com padrão único.",
        "resultado": "Arquivo mais limpo, rastreável e fácil de consultar.",
        "gancho": "Os documentos vivem espalhados entre e-mail, Drive e WhatsApp?",
        "impacto": [
            "padronização de nomes e pastas",
            "download e agrupamento por caso",
            "integração com Drive ou CRM",
        ],
    },
    {
        "slug": "operacao",
        "nome": "Painel de operação",
        "resumo": "Status, responsável e fila de trabalho em um único lugar.",
        "resultado": "Mais visibilidade sobre análise, pendências e prioridade.",
        "gancho": "Você sabe agora quais processos exigem atenção hoje?",
        "impacto": [
            "painel executivo para sócios",
            "filtros por status e área",
            "fluxo de acompanhamento por responsável",
        ],
    },
    {
        "slug": "comunicacao",
        "nome": "Comunicação com cliente",
        "resumo": "Mensagens e atualizações para reduzir repetição de contato.",
        "resultado": "Retorno mais consistente e menos perda de tempo.",
        "gancho": "A equipe responde a mesma dúvida várias vezes por semana?",
        "impacto": [
            "avisos automáticos por e-mail ou WhatsApp",
            "follow-up de status e prazos",
            "experiência mais profissional para o cliente",
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
    {"titulo": "Diagnóstico", "texto": "Entendemos rotina, volume, risco e gargalos."},
    {"titulo": "Proposta técnica", "texto": "Traduzimos a dor em solução com escopo claro."},
    {"titulo": "Implantação", "texto": "Colocamos em produção e ajustamos com dados reais."},
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
        "eyebrow": "Automação jurídica premium",
        "headline": "Rotinas jurídicas com mais velocidade, padrão e controle.",
        "lead": "Automação sob medida para escritórios de advocacia que querem reduzir trabalho manual, organizar processos e melhorar o atendimento.",
        "primary_cta": "Solicitar diagnóstico",
        "secondary_cta": "Ver soluções",
        "trust": ["Foco em escritórios", "Implantação sob medida", "Conversa orientada por diagnóstico", "Prioridade em conversão"],
        "hero_points": [
            {"title": "Menos manual", "text": "Processos que deixam de depender de conferência repetitiva."},
            {"title": "Mais organização", "text": "Documentos, tarefas e status centralizados."},
            {"title": "Mais percepção de valor", "text": "Resposta, clareza e consistência no atendimento."},
        ],
        "sections": [
            {"kicker": "Como a JurisFlow trabalha", "title": "Uma operação de automação pensada para escritórios.", "description": "Começamos pela dor mais urgente e avançamos em blocos independentes.", "cards": PROCESSO, "type": "steps"},
            {"kicker": "Frentes de atuação", "title": "O que entregamos para organizar a operação.", "description": "Cada frente está ligada a um ganho operacional claro.", "cards": SERVICOS, "type": "servicos"},
            {"kicker": "Formatos de contratação", "title": "Modelos simples para começar e evoluir.", "description": "O cliente pode entrar com clareza e avançar conforme a maturidade.", "cards": PACOTES, "type": "pacotes"},
        ],
        "cta_title": "Se o escritório ainda depende de conferência manual, o primeiro passo é o diagnóstico.",
        "cta_text": "Você entende a operação antes de vender a solução, e a proposta fica mais convincente.",
        "cta_href": "/diagnostico",
        "cta_label": "Montar diagnóstico",
    },
    "diagnostico": {
        "eyebrow": "Landing de conversão",
        "headline": "Descubra onde o escritório perde tempo e qual automação gera resultado primeiro.",
        "lead": "Uma landing focada em qualificar lead e levar o escritório direto para o formulário de diagnóstico.",
        "primary_cta": "Abrir diagnóstico",
        "secondary_cta": "Conhecer soluções",
        "trust": ["Formulário qualificado", "Banco integrado", "Lead mais organizado", "Pronto para produção"],
        "hero_points": [
            {"title": "Captação clara", "text": "Menos ruído e mais informação útil para a primeira conversa."},
            {"title": "Qualificação", "text": "Porte, volume, objetivo e gargalo em um só lugar."},
            {"title": "Próximo passo", "text": "A conversa já começa com contexto real."},
        ],
        "sections": [
            {"kicker": "O que vamos mapear", "title": "Antes de vender automação, é preciso entender a operação.", "description": "O diagnóstico organiza as informações que importam para propor a solução certa.", "cards": [
                {"titulo": "Tempo perdido", "texto": "Onde o time ainda faz conferências manuais."},
                {"titulo": "Ferramentas atuais", "texto": "Quais sistemas já fazem parte da rotina."},
                {"titulo": "Prioridade inicial", "texto": "Qual frente faz mais sentido começar."},
            ], "type": "cards"},
            {"kicker": "Resultado esperado", "title": "Uma proposta forte começa com contexto real.", "description": "Depois do envio, o lead fica organizado para a venda e acompanhamento.", "cards": [
                {"titulo": "Lead organizado", "texto": "Dados salvos em banco de dados e prontos para análise."},
                {"titulo": "Conversa melhor", "texto": "A primeira reunião já nasce com contexto."},
                {"titulo": "Escalável", "texto": "Base pronta para dashboard, automação e produção."},
            ], "type": "cards"},
        ],
        "cta_title": "Pronto para captar leads mais qualificados?",
        "cta_text": "Use esta landing como porta de entrada para o diagnóstico.",
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
                cur.execute("CREATE INDEX IF NOT EXISTS processos_status_idx ON processos (status)")
                cur.execute("CREATE INDEX IF NOT EXISTS processos_numero_idx ON processos (numero)")
            conn.commit()
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
            CREATE INDEX IF NOT EXISTS processos_status_idx ON processos (status);
            CREATE INDEX IF NOT EXISTS processos_numero_idx ON processos (numero);
            """
        )
        conn.commit()
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
    for offset in range(5, -1, -1):
        anchor = (now.replace(day=1) - timedelta(days=offset * 31)).replace(day=1)
        months.append(anchor.strftime("%b"))
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


def _build_dashboard_context() -> dict[str, object]:
    ensure_storage()
    processos = fetch_all("SELECT * FROM processos ORDER BY COALESCE(updated_at, created_at) DESC, id DESC")
    events = fetch_all(
        """
        SELECT e.*, p.numero, p.cliente, p.status AS processo_status
        FROM processo_eventos e
        JOIN processos p ON p.id = e.processo_id
        ORDER BY e.timestamp DESC, e.id DESC
        LIMIT 8
        """
    )

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


@app.context_processor
def inject_globals():
    return {
        "marca": "JurisFlow",
        "proposta": "Automação sob medida para escritórios de advocacia que querem reduzir trabalho manual, organizar processos e melhorar o atendimento.",
        "diferenciais": DIFERENCIAIS,
        "servicos": SERVICOS,
        "pacotes": PACOTES,
        "processo": PROCESSO,
        "ganchos": GANCHOS,
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
def dashboard():
    return render_template("dashboard.html", **_build_dashboard_context())


@app.route("/processos")
def processos_page():
    return render_template("processos.html", **_build_dashboard_context())


@app.route("/processos/<int:processo_id>")
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
