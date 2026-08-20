"""Registro de espectadores e dos lutadores que eles possuem.

Mora em SQLite, num arquivo proprio dentro do diretorio de runtime, e nunca
toca no catalogo JSON. Tres razoes concretas, todas medidas no projeto:

* inserir um personagem no catalogo JSON custa dois parses completos, uma
  revalidacao de todas as referencias cruzadas e duas reescritas integrais --
  a milhares de lutadores isso e mais de um megabyte reescrito por espectador
  que entra;
* ``database`` serializa toda escrita com um lock **entre processos** de ate 30
  segundos; segurar isso durante um round congelaria a transmissao;
* ``personagens.json`` e asset curado e empacotado na wheel. Conteudo gerado por
  espectador nao pertence a ele.

O catalogo JSON continua sendo a fonte read-only de armas e do roster curado; o
registro apenas referencia armas pelo nome, validando na insercao com o mesmo
validador que a persistencia principal usa.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from neural_fights.data import database
from neural_fights.live.identity import (
    NomeExibicao,
    catalog_name_de,
    handle_de,
    resolver_display_name,
)

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
NOME_ARQUIVO = "live.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS viewer (
    viewer_id         TEXT PRIMARY KEY,
    platform          TEXT NOT NULL,
    platform_user_id  TEXT NOT NULL,
    display_name      TEXT NOT NULL,
    display_name_raw  TEXT NOT NULL DEFAULT '',
    first_seen_at     REAL NOT NULL,
    last_seen_at      REAL NOT NULL,
    banned            INTEGER NOT NULL DEFAULT 0,
    UNIQUE (platform, platform_user_id)
);

CREATE TABLE IF NOT EXISTS fighter (
    fighter_id    TEXT PRIMARY KEY,
    viewer_id     TEXT NOT NULL REFERENCES viewer(viewer_id) ON DELETE CASCADE,
    catalog_name  TEXT NOT NULL UNIQUE,
    display_name  TEXT NOT NULL,
    spec_json     TEXT NOT NULL,
    weapon_name   TEXT NOT NULL,
    created_at    REAL NOT NULL,
    retired_at    REAL
);

-- Um lutador ativo por espectador; aposentados nao ocupam a vaga.
CREATE UNIQUE INDEX IF NOT EXISTS idx_fighter_ativo
    ON fighter (viewer_id) WHERE retired_at IS NULL;

CREATE TABLE IF NOT EXISTS fighter_stats (
    fighter_id TEXT PRIMARY KEY REFERENCES fighter(fighter_id) ON DELETE CASCADE,
    wins       INTEGER NOT NULL DEFAULT 0,
    losses     INTEGER NOT NULL DEFAULT 0,
    draws      INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL
);

-- Chave primaria e o event_id da plataforma: reconexao reentrega o que ja foi
-- lido, e aplicar um gift duas vezes cobraria a pessoa duas vezes.
CREATE TABLE IF NOT EXISTS event_journal (
    event_id    TEXT PRIMARY KEY,
    sequence    INTEGER NOT NULL DEFAULT 0,
    received_at REAL NOT NULL,
    viewer_id   TEXT,
    kind        TEXT NOT NULL,
    value_units INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL,
    detalhe     TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS moderation_blocklist (
    pattern  TEXT PRIMARY KEY,
    added_at REAL NOT NULL
);

-- Intencao paga que vale para a proxima partida. Fica no banco, e nao em
-- memoria, porque o espectador ja gastou: uma queda de processo nao pode
-- simplesmente engolir o que foi comprado.
CREATE TABLE IF NOT EXISTS round_queue (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    enqueued_at REAL NOT NULL,
    viewer_id   TEXT,
    command_id  TEXT NOT NULL,
    payload     TEXT NOT NULL DEFAULT '',
    consumed_at REAL
);
"""


@dataclass(frozen=True)
class Viewer:
    viewer_id: str
    platform: str
    platform_user_id: str
    display_name: str
    banned: bool = False


@dataclass(frozen=True)
class Fighter:
    """Um lutador possuido por um espectador.

    ``catalog_name`` e a chave usada pelo motor; ``display_name`` e o texto
    seguro que vai para a tela.
    """

    fighter_id: str
    viewer_id: str
    catalog_name: str
    display_name: str
    spec: dict[str, Any]
    weapon_name: str

    @property
    def nome_no_motor(self) -> str:
        return self.catalog_name


def viewer_id_de(platform: str, platform_user_id: str) -> str:
    """Id estavel e global: o mesmo id pode existir em duas plataformas."""
    platform = str(platform).strip().lower()
    platform_user_id = str(platform_user_id).strip()
    if not platform or not platform_user_id:
        raise ValueError("platform e platform_user_id sao obrigatorios")
    digest = hashlib.blake2s(
        f"{platform}:{platform_user_id}".encode("utf-8"), digest_size=8
    ).hexdigest()
    return f"{platform[:2]}{digest}"


def fighter_id_de(viewer_id: str, ordinal: int = 0) -> str:
    """Deriva o id do lutador; a mesma entrada gera sempre o mesmo lutador."""
    digest = hashlib.blake2s(
        f"{viewer_id}:{ordinal}".encode("utf-8"), digest_size=5
    ).hexdigest()
    return digest


def caminho_padrao() -> str:
    """Arquivo do registro, isolado por ``NEURAL_FIGHTS_RUNTIME_DIR``."""
    return os.path.join(database.resolver_runtime_data_dir(), NOME_ARQUIVO)


class LiveRegistry:
    """Acesso ao registro. Escritas sao curtas e nunca acontecem num round."""

    def __init__(self, caminho: str | Path | None = None) -> None:
        self._caminho = str(caminho) if caminho is not None else caminho_padrao()
        if self._caminho != ":memory:":
            Path(self._caminho).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conexao = sqlite3.connect(
            self._caminho,
            check_same_thread=False,
            isolation_level=None,
        )
        self._conexao.row_factory = sqlite3.Row
        self._preparar()

    @property
    def caminho(self) -> str:
        return self._caminho

    def _preparar(self) -> None:
        with self._lock:
            cursor = self._conexao.cursor()
            # WAL deixa leitura concorrente sem bloquear a escrita do jogo, e
            # ``NORMAL`` troca durabilidade absoluta por nao pagar fsync a cada
            # commit -- perder o ultimo evento de uma live vale menos que um
            # engasgo de frame.
            if self._caminho != ":memory:":
                cursor.execute("PRAGMA journal_mode = WAL")
            cursor.execute("PRAGMA synchronous = NORMAL")
            cursor.execute("PRAGMA foreign_keys = ON")
            cursor.executescript(_SCHEMA)
            cursor.execute("INSERT OR IGNORE INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))

    def close(self) -> None:
        with self._lock:
            self._conexao.close()

    def __enter__(self) -> "LiveRegistry":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # ------------------------------------------------------------- espectador

    def registrar_viewer(
        self,
        *,
        platform: str,
        platform_user_id: str,
        display_name_bruto: object = "",
        agora: float | None = None,
    ) -> Viewer:
        """Insere ou atualiza um espectador. Idempotente por identidade."""
        agora = time.time() if agora is None else float(agora)
        viewer_id = viewer_id_de(platform, platform_user_id)
        nome = self.sanitizar(display_name_bruto, viewer_id=viewer_id, platform=platform)

        with self._lock:
            cursor = self._conexao.cursor()
            cursor.execute(
                """
                INSERT INTO viewer (viewer_id, platform, platform_user_id, display_name,
                                    display_name_raw, first_seen_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(viewer_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    display_name_raw = excluded.display_name_raw,
                    last_seen_at = excluded.last_seen_at
                """,
                (
                    viewer_id,
                    str(platform).strip().lower(),
                    str(platform_user_id).strip(),
                    nome.valor,
                    nome.original,
                    agora,
                    agora,
                ),
            )
            linha = cursor.execute(
                "SELECT * FROM viewer WHERE viewer_id = ?", (viewer_id,)
            ).fetchone()
        return _viewer_de_linha(linha)

    def obter_viewer(self, viewer_id: str) -> Viewer | None:
        with self._lock:
            linha = self._conexao.execute(
                "SELECT * FROM viewer WHERE viewer_id = ?", (viewer_id,)
            ).fetchone()
        return _viewer_de_linha(linha) if linha else None

    def definir_banimento(self, viewer_id: str, banido: bool) -> None:
        with self._lock:
            self._conexao.execute(
                "UPDATE viewer SET banned = ? WHERE viewer_id = ?",
                (1 if banido else 0, viewer_id),
            )

    # ---------------------------------------------------------------- lutador

    def obter_lutador_ativo(self, viewer_id: str) -> Fighter | None:
        with self._lock:
            linha = self._conexao.execute(
                "SELECT * FROM fighter WHERE viewer_id = ? AND retired_at IS NULL",
                (viewer_id,),
            ).fetchone()
        return _fighter_de_linha(linha) if linha else None

    def obter_lutador_por_catalogo(self, catalog_name: str) -> Fighter | None:
        with self._lock:
            linha = self._conexao.execute(
                "SELECT * FROM fighter WHERE catalog_name = ?", (catalog_name,)
            ).fetchone()
        return _fighter_de_linha(linha) if linha else None

    def listar_lutadores_ativos(self, limite: int | None = None) -> list[Fighter]:
        consulta = "SELECT * FROM fighter WHERE retired_at IS NULL ORDER BY created_at"
        parametros: tuple = ()
        if limite is not None:
            consulta += " LIMIT ?"
            parametros = (int(limite),)
        with self._lock:
            linhas = self._conexao.execute(consulta, parametros).fetchall()
        return [_fighter_de_linha(linha) for linha in linhas]

    def aposentar_lutador(self, fighter_id: str, agora: float | None = None) -> bool:
        agora = time.time() if agora is None else float(agora)
        with self._lock:
            cursor = self._conexao.execute(
                "UPDATE fighter SET retired_at = ? WHERE fighter_id = ? AND retired_at IS NULL",
                (agora, fighter_id),
            )
        return cursor.rowcount > 0

    def registrar_resultado(self, fighter_id: str, resultado: str) -> None:
        """Acumula vitoria/derrota/empate. E a base do ranking da Fase 5."""
        coluna = {"vitoria": "wins", "derrota": "losses", "empate": "draws"}.get(resultado)
        if coluna is None:
            raise ValueError(f"resultado desconhecido: {resultado!r}")
        with self._lock:
            self._conexao.execute(
                f"""
                INSERT INTO fighter_stats (fighter_id, {coluna}, updated_at)
                VALUES (?, 1, ?)
                ON CONFLICT(fighter_id) DO UPDATE SET
                    {coluna} = {coluna} + 1,
                    updated_at = excluded.updated_at
                """,
                (fighter_id, time.time()),
            )

    def registrar_resultado_por_catalogo(self, catalog_name: str, resultado: str) -> bool:
        """Contabiliza pelo nome que o motor usa. Nome curado e ignorado."""
        fighter = self.obter_lutador_por_catalogo(catalog_name)
        if fighter is None:
            return False
        self.registrar_resultado(fighter.fighter_id, resultado)
        return True

    def mapa_nomes_exibicao(self) -> dict[str, str]:
        """catalog_name -> display_name de todos os lutadores de espectador.

        Passe 3 (arte): o motor luta com o catalog_name ("@<id>") e a TELA
        precisa do nome sanitizado — todo o identity.py existia para isso
        e o HUD nunca o consumiu (o espectador via "@3f9a2c" na barra).
        """
        with self._lock:
            linhas = self._conexao.execute(
                "SELECT catalog_name, display_name FROM fighter"
            ).fetchall()
        return {linha[0]: linha[1] for linha in linhas}

    def classificacao(self, limite: int = 20) -> list[dict[str, Any]]:
        """Ranking dos lutadores de espectador, por vitorias e saldo.

        O desempate por saldo evita que quem lutou muito e perdeu muito fique
        acima de quem lutou pouco e ganhou tudo.
        """
        with self._lock:
            linhas = self._conexao.execute(
                """
                SELECT f.fighter_id, f.catalog_name, f.display_name,
                       COALESCE(s.wins, 0)   AS wins,
                       COALESCE(s.losses, 0) AS losses,
                       COALESCE(s.draws, 0)  AS draws
                FROM fighter AS f
                LEFT JOIN fighter_stats AS s ON s.fighter_id = f.fighter_id
                WHERE f.retired_at IS NULL
                ORDER BY wins DESC, (wins - losses) DESC, f.created_at ASC
                LIMIT ?
                """,
                (max(1, int(limite)),),
            ).fetchall()
        return [
            {
                "fighter_id": linha["fighter_id"],
                "catalog_name": linha["catalog_name"],
                "display_name": linha["display_name"],
                "wins": linha["wins"],
                "losses": linha["losses"],
                "draws": linha["draws"],
                "saldo": linha["wins"] - linha["losses"],
            }
            for linha in linhas
        ]

    def stats_do_lutador(self, fighter_id: str) -> dict[str, int]:
        with self._lock:
            linha = self._conexao.execute(
                "SELECT wins, losses, draws FROM fighter_stats WHERE fighter_id = ?",
                (fighter_id,),
            ).fetchone()
        if linha is None:
            return {"wins": 0, "losses": 0, "draws": 0}
        return {"wins": linha["wins"], "losses": linha["losses"], "draws": linha["draws"]}

    # ------------------------------------------------------------ idempotencia

    def ja_processado(self, event_id: str) -> bool:
        with self._lock:
            linha = self._conexao.execute(
                "SELECT 1 FROM event_journal WHERE event_id = ?", (event_id,)
            ).fetchone()
        return linha is not None

    def registrar_evento(
        self,
        *,
        event_id: str,
        kind: str,
        status: str,
        sequence: int = 0,
        viewer_id: str | None = None,
        value_units: int = 0,
        detalhe: str = "",
        agora: float | None = None,
    ) -> bool:
        """Journaliza um evento. Devolve ``False`` se ja tinha sido visto."""
        agora = time.time() if agora is None else float(agora)
        with self._lock:
            cursor = self._conexao.execute(
                """
                INSERT OR IGNORE INTO event_journal
                    (event_id, sequence, received_at, viewer_id, kind, value_units, status, detalhe)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, int(sequence), agora, viewer_id, kind, int(value_units), status, detalhe),
            )
        return cursor.rowcount > 0

    def atualizar_status_evento(self, event_id: str, status: str, detalhe: str = "") -> None:
        """Anota o desfecho de um evento ja journalizado."""
        with self._lock:
            self._conexao.execute(
                "UPDATE event_journal SET status = ?, detalhe = ? WHERE event_id = ?",
                (status, str(detalhe)[:500], event_id),
            )

    def status_do_evento(self, event_id: str) -> tuple[str, str] | None:
        with self._lock:
            linha = self._conexao.execute(
                "SELECT status, detalhe FROM event_journal WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        return (linha["status"], linha["detalhe"]) if linha else None

    # -------------------------------------------------- fila do proximo round

    def enfileirar_para_proximo_round(
        self,
        *,
        command_id: str,
        payload: str = "",
        viewer_id: str | None = None,
        agora: float | None = None,
    ) -> int:
        agora = time.time() if agora is None else float(agora)
        with self._lock:
            cursor = self._conexao.execute(
                """
                INSERT INTO round_queue (enqueued_at, viewer_id, command_id, payload)
                VALUES (?, ?, ?, ?)
                """,
                (agora, viewer_id, command_id, str(payload)),
            )
        return int(cursor.lastrowid)

    def consumir_fila_do_round(self, agora: float | None = None) -> list[dict[str, Any]]:
        """Retira o que estava enfileirado e marca como consumido.

        Devolve na ordem de chegada: quem pagou primeiro decide primeiro.
        """
        agora = time.time() if agora is None else float(agora)
        with self._lock:
            linhas = self._conexao.execute(
                "SELECT * FROM round_queue WHERE consumed_at IS NULL ORDER BY id"
            ).fetchall()
            if linhas:
                self._conexao.execute(
                    "UPDATE round_queue SET consumed_at = ? WHERE consumed_at IS NULL",
                    (agora,),
                )
        return [
            {
                "id": linha["id"],
                "viewer_id": linha["viewer_id"],
                "command_id": linha["command_id"],
                "payload": linha["payload"],
            }
            for linha in linhas
        ]

    def fila_pendente(self) -> int:
        with self._lock:
            linha = self._conexao.execute(
                "SELECT COUNT(*) AS total FROM round_queue WHERE consumed_at IS NULL"
            ).fetchone()
        return int(linha["total"])

    # -------------------------------------------------------------- moderacao

    def blocklist(self) -> tuple[str, ...]:
        with self._lock:
            linhas = self._conexao.execute(
                "SELECT pattern FROM moderation_blocklist"
            ).fetchall()
        return tuple(linha["pattern"] for linha in linhas)

    def bloquear_termo(self, termo: str) -> None:
        termo = str(termo).strip().casefold()
        if not termo:
            raise ValueError("termo de bloqueio nao pode ser vazio")
        with self._lock:
            self._conexao.execute(
                "INSERT OR IGNORE INTO moderation_blocklist(pattern, added_at) VALUES (?, ?)",
                (termo, time.time()),
            )

    def sanitizar(
        self,
        bruto: object,
        *,
        viewer_id: str,
        platform: str = "",
    ) -> NomeExibicao:
        """Sanitiza usando a blocklist viva, editavel durante a transmissao."""
        return resolver_display_name(
            bruto,
            viewer_id=viewer_id,
            platform=platform,
            blocklist=self.blocklist(),
        )

    # ------------------------------------------------------------------ entrar

    def criar_lutador(
        self,
        viewer: Viewer,
        *,
        armas: Sequence[dict[str, Any]] | None = None,
        agora: float | None = None,
    ) -> Fighter:
        """Gera e persiste o lutador de um espectador.

        Reusa ``gerar_personagem`` do gerador auditado em vez de inventar um
        segundo caminho de geracao, e valida com ``database.validar_personagens``
        -- o mesmo validador da persistencia principal.

        A geracao e semeada pelo ``fighter_id``, entao o mesmo espectador sempre
        recebe o mesmo lutador. O estado do ``random`` global e salvo e
        restaurado em volta da chamada: o gerador usa o modulo ``random``, e o
        ``Simulador`` semeia esse mesmo stream para reproduzir partidas.
        """
        if viewer.banned:
            raise PermissionError(f"espectador banido: {viewer.viewer_id}")

        existente = self.obter_lutador_ativo(viewer.viewer_id)
        if existente is not None:
            return existente

        agora = time.time() if agora is None else float(agora)
        fighter_id = fighter_id_de(viewer.viewer_id)
        catalog_name = catalog_name_de(fighter_id)
        spec = self._gerar_spec(fighter_id, catalog_name, armas)

        with self._lock:
            self._conexao.execute(
                """
                INSERT INTO fighter (fighter_id, viewer_id, catalog_name, display_name,
                                     spec_json, weapon_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fighter_id,
                    viewer.viewer_id,
                    catalog_name,
                    viewer.display_name,
                    json.dumps(spec, ensure_ascii=False, sort_keys=True),
                    spec["nome_arma"],
                    agora,
                ),
            )
        return Fighter(
            fighter_id=fighter_id,
            viewer_id=viewer.viewer_id,
            catalog_name=catalog_name,
            display_name=viewer.display_name,
            spec=spec,
            weapon_name=spec["nome_arma"],
        )

    def _gerar_spec(
        self,
        fighter_id: str,
        catalog_name: str,
        armas: Sequence[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        # Importado aqui para nao pagar o catalogo do gerador quando o registro
        # e usado so para consulta.
        from neural_fights.models.constants import LISTA_CLASSES
        from neural_fights.ai.personalities import PERSONALIDADES_PRESETS
        from neural_fights.tools.gerador_database import (
            gerar_personagem,
            selecionar_arma_por_classe,
        )

        if armas is None:
            armas = [arma.to_dict() for arma in database.carregar_armas()]
        if not armas:
            raise RuntimeError("catalogo de armas vazio: nao ha o que equipar")

        estado_anterior = random.getstate()
        try:
            random.seed(f"neural-fights:fighter:{fighter_id}")
            classe = random.choice(LISTA_CLASSES)
            personalidade = random.choice(sorted(PERSONALIDADES_PRESETS))
            candidatas = selecionar_arma_por_classe(classe.split(" (")[0], armas) or list(armas)
            arma = random.choice(candidatas)
            spec = gerar_personagem(classe, personalidade, arma["nome"])
        finally:
            random.setstate(estado_anterior)

        # O motor e name-keyed: o nome persistido e a chave de catalogo, nunca o
        # texto que o espectador escolheu.
        spec["nome"] = catalog_name
        database.validar_personagens(
            [spec],
            nomes_armas={a["nome"] for a in armas},
        )
        return spec


def _viewer_de_linha(linha: sqlite3.Row | None) -> Viewer:
    return Viewer(
        viewer_id=linha["viewer_id"],
        platform=linha["platform"],
        platform_user_id=linha["platform_user_id"],
        display_name=linha["display_name"],
        banned=bool(linha["banned"]),
    )


def _fighter_de_linha(linha: sqlite3.Row) -> Fighter:
    return Fighter(
        fighter_id=linha["fighter_id"],
        viewer_id=linha["viewer_id"],
        catalog_name=linha["catalog_name"],
        display_name=linha["display_name"],
        spec=json.loads(linha["spec_json"]),
        weapon_name=linha["weapon_name"],
    )


__all__ = [
    "NOME_ARQUIVO",
    "SCHEMA_VERSION",
    "Fighter",
    "LiveRegistry",
    "Viewer",
    "caminho_padrao",
    "fighter_id_de",
    "handle_de",
    "viewer_id_de",
]
