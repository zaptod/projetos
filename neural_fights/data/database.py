"""Persistencia e contratos dos dados JSON do Neural Fights.

Os arquivos de armas e personagens formam uma unica unidade logica. Antes de
serem expostos ao restante da aplicacao, sua estrutura e todas as referencias
entre catalogos sao validadas.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import tempfile
import threading
import time
from collections.abc import Iterable, Mapping, Sequence
from contextlib import contextmanager
from functools import wraps
from typing import Any

from neural_fights.models import Arma, Personagem, get_raridade_data
from neural_fights.models.constants import (
    ENCANTAMENTOS,
    LISTA_CLASSES,
    LISTA_RARIDADES,
    LISTA_TIPOS_ARMA,
    TIPOS_ARMA,
)


DATA_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(DATA_DIR)
RUNTIME_DATA_DIR_ENV = "NEURAL_FIGHTS_RUNTIME_DIR"


def resolver_runtime_data_dir() -> str:
    """Retorna um diretorio gravavel, separado dos assets instalados."""
    override = os.environ.get(RUNTIME_DATA_DIR_ENV)
    if override:
        return os.path.abspath(os.path.expanduser(override))
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    else:
        base = os.environ.get("XDG_STATE_HOME")
        if not base:
            base = os.path.join(os.path.expanduser("~"), ".local", "state")
    if not base:
        base = os.path.join(tempfile.gettempdir(), "neural-fights")
        return os.path.abspath(base)
    return os.path.abspath(os.path.join(base, "neural-fights"))


RUNTIME_DIR = resolver_runtime_data_dir()
# Assets imutaveis distribuidos com o pacote. Os aliases historicos sao
# mantidos para ferramentas que auditam o catalogo da versao instalada.
ARQUIVO_CHARS = os.path.join(DATA_DIR, "personagens.json")
ARQUIVO_ARMAS = os.path.join(DATA_DIR, "armas.json")
ARQUIVO_CHARS_RUNTIME = os.path.join(RUNTIME_DIR, "personagens.json")
ARQUIVO_ARMAS_RUNTIME = os.path.join(RUNTIME_DIR, "armas.json")
ARQUIVO_MATCH_DEFAULT = os.path.join(DATA_DIR, "fixtures", "default_match_config.json")
ARQUIVO_MATCH = os.path.join(RUNTIME_DIR, "match_config.json")
MATCH_CONFIG_ENV = "NEURAL_FIGHTS_MATCH_CONFIG"
_CAMPOS_GEOMETRIA_ARMA = frozenset(
    campo
    for dados_tipo in TIPOS_ARMA.values()
    for campo in dados_tipo["geometria"]
)
_CAMPOS_INTEIROS_GEOMETRIA = frozenset({"quantidade", "quantidade_orbitais"})


# Um unico lock reentrante protege, dentro do processo, tanto snapshots de
# varios arquivos quanto operacoes de leitura-modificacao-escrita. O RLock e
# necessario porque as APIs de alto nivel se compoem (por exemplo,
# ``renomear_arma`` chama ``carregar_database`` e ``salvar_database``).
_PERSISTENCE_LOCK = threading.RLock()
_INTERPROCESS_STATE = threading.local()
_INTERPROCESS_LOCK_TIMEOUT = 30.0


@contextmanager
def _bloqueio_persistencia_interprocesso():
    """Serializa snapshots e read-modify-write tambem entre processos.

    O arquivo de lock fica no diretorio temporario do usuario, que e gravavel
    mesmo quando a wheel esta instalada em modo somente leitura. Ele e mantido
    depois do uso: remover um lock desbloqueado abriria uma corrida entre um
    processo que ainda segura o inode antigo e outro que criasse um novo.
    """

    caminho = os.path.join(tempfile.gettempdir(), "neural-fights.persistence.lock")
    arquivo = open(caminho, "a+b")
    adquirido = False
    try:
        arquivo.seek(0, os.SEEK_END)
        if arquivo.tell() == 0:
            arquivo.write(b"\0")
            arquivo.flush()
        arquivo.seek(0)

        if os.name == "nt":
            import msvcrt

            limite = time.monotonic() + _INTERPROCESS_LOCK_TIMEOUT
            while True:
                try:
                    msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
                    adquirido = True
                    break
                except OSError as exc:
                    if time.monotonic() >= limite:
                        raise TimeoutError(
                            "tempo esgotado aguardando o lock de persistencia"
                        ) from exc
                    time.sleep(0.01)
        else:
            import fcntl

            fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX)
            adquirido = True

        yield
    finally:
        if adquirido:
            arquivo.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)
        arquivo.close()


def _serializar_persistencia(func):
    @wraps(func)
    def protegida(*args, **kwargs):
        with _PERSISTENCE_LOCK:
            profundidade = getattr(_INTERPROCESS_STATE, "depth", 0)
            if profundidade:
                _INTERPROCESS_STATE.depth = profundidade + 1
                try:
                    return func(*args, **kwargs)
                finally:
                    _INTERPROCESS_STATE.depth = profundidade

            with _bloqueio_persistencia_interprocesso():
                _INTERPROCESS_STATE.depth = 1
                try:
                    return func(*args, **kwargs)
                finally:
                    _INTERPROCESS_STATE.depth = 0

    return protegida


class DataValidationError(ValueError):
    """Indica JSON invalido ou um documento que viola o contrato de dados."""

    def __init__(self, erros: str | Iterable[str]):
        if isinstance(erros, str):
            self.erros = (erros,)
        else:
            self.erros = tuple(str(erro) for erro in erros)
        super().__init__("Dados invalidos:\n- " + "\n- ".join(self.erros))


@_serializar_persistencia
def resolver_database_paths(
    *,
    arquivo_armas: str | None = None,
    arquivo_personagens: str | None = None,
    para_escrita: bool = False,
) -> tuple[str, str]:
    """Resolve um snapshot coerente sem escrever no pacote instalado.

    Leituras usam a copia do usuario quando o par runtime existe e recorrem
    aos assets empacotados enquanto ela ainda nao foi criada. Escritas sempre
    apontam para o diretorio runtime. Um par runtime parcial e tratado como
    corrupcao para nao combinar versoes diferentes silenciosamente.
    """

    if (arquivo_armas is None) != (arquivo_personagens is None):
        raise ValueError(
            "informe arquivo_armas e arquivo_personagens juntos para manter "
            "o snapshot coerente"
        )
    if arquivo_armas is not None and arquivo_personagens is not None:
        return os.path.abspath(arquivo_armas), os.path.abspath(arquivo_personagens)

    runtime_armas = os.path.abspath(ARQUIVO_ARMAS_RUNTIME)
    runtime_chars = os.path.abspath(ARQUIVO_CHARS_RUNTIME)
    if para_escrita:
        return runtime_armas, runtime_chars

    armas_existe = os.path.exists(runtime_armas)
    chars_existe = os.path.exists(runtime_chars)
    if armas_existe != chars_existe:
        ausente = runtime_chars if armas_existe else runtime_armas
        raise DataValidationError(
            "snapshot runtime incompleto; arquivo ausente: " + ausente
        )
    if armas_existe:
        return runtime_armas, runtime_chars
    return os.path.abspath(ARQUIVO_ARMAS), os.path.abspath(ARQUIVO_CHARS)


def _rejeitar_constante_json(valor: str) -> None:
    raise ValueError(f"constante numerica nao permitida pelo JSON: {valor}")


def _parse_float_json_finito(valor: str) -> float:
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError(f"numero nao finito nao permitido pelo JSON: {valor}")
    return numero


def _objeto_json_sem_chaves_duplicadas(pares):
    resultado = {}
    for chave, valor in pares:
        if chave in resultado:
            raise ValueError(f"chave JSON duplicada: {chave!r}")
        resultado[chave] = valor
    return resultado


@_serializar_persistencia
def carregar_json(arquivo: str, padrao: Any = None) -> Any:
    """Carrega JSON sem converter corrupcao ou erro de permissao em lista vazia.

    Arquivos ausentes continuam aceitando um valor padrao por compatibilidade.
    Se ``padrao`` nao for informado, o padrao historico e uma lista vazia.
    """

    if not os.path.exists(arquivo):
        return [] if padrao is None else padrao

    try:
        with open(arquivo, "r", encoding="utf-8") as f:
            return json.load(
                f,
                parse_constant=_rejeitar_constante_json,
                parse_float=_parse_float_json_finito,
                object_pairs_hook=_objeto_json_sem_chaves_duplicadas,
            )
    except json.JSONDecodeError as exc:
        raise DataValidationError(
            f"JSON invalido em {os.path.abspath(arquivo)} "
            f"(linha {exc.lineno}, coluna {exc.colno}): {exc.msg}"
        ) from exc
    except ValueError as exc:
        raise DataValidationError(
            f"JSON invalido em {os.path.abspath(arquivo)}: {exc}"
        ) from exc


def _escrever_temporario(destino: str, dados: Any, *, indent: int = 4) -> str:
    diretorio = os.path.dirname(destino)
    if not os.path.isdir(diretorio):
        raise FileNotFoundError(f"Diretorio de destino inexistente: {diretorio}")

    temporario = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=diretorio,
            prefix=f".{os.path.basename(destino)}.",
            suffix=".tmp",
            delete=False,
        ) as f:
            temporario = f.name
            json.dump(
                dados,
                f,
                indent=indent,
                ensure_ascii=False,
                allow_nan=False,
            )
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        return temporario
    except BaseException:
        if temporario and os.path.exists(temporario):
            os.unlink(temporario)
        raise


@_serializar_persistencia
def salvar_json(arquivo: str, dados: Any) -> None:
    """Salva um documento atomicamente, mantendo o anterior em caso de falha."""

    destino = os.path.abspath(arquivo)
    temporario = _escrever_temporario(destino, dados)
    try:
        os.replace(temporario, destino)
        temporario = ""
    finally:
        if temporario and os.path.exists(temporario):
            os.unlink(temporario)


@_serializar_persistencia
def salvar_jsons_coerentes(documentos: Mapping[str, Any]) -> None:
    """Substitui varios JSONs como uma transacao com rollback em caso de erro.

    Todos os documentos sao serializados e sincronizados antes da primeira
    substituicao. Se qualquer ``os.replace`` falhar, todos os destinos que ja
    foram alterados voltam ao conteudo anterior.
    """

    if not documentos:
        return

    destinos = [(os.path.abspath(caminho), dados) for caminho, dados in documentos.items()]
    if len({caminho for caminho, _ in destinos}) != len(destinos):
        raise ValueError("A transacao contem destinos duplicados")

    temporarios: dict[str, str] = {}
    backups: dict[str, str | None] = {}
    instalados: list[str] = []
    try:
        for destino, dados in destinos:
            temporarios[destino] = _escrever_temporario(destino, dados, indent=2)

        for destino, _ in destinos:
            if not os.path.exists(destino):
                backups[destino] = None
                continue
            fd, backup = tempfile.mkstemp(
                dir=os.path.dirname(destino),
                prefix=f".{os.path.basename(destino)}.",
                suffix=".bak",
            )
            os.close(fd)
            shutil.copyfile(destino, backup)
            backups[destino] = backup
            with open(backup, "r+b") as f:
                os.fsync(f.fileno())

        for destino, _ in destinos:
            os.replace(temporarios[destino], destino)
            temporarios.pop(destino)
            instalados.append(destino)
    except BaseException:
        rollback_errors = []
        for destino in reversed(instalados):
            backup = backups.get(destino)
            try:
                if backup is None:
                    if os.path.exists(destino):
                        os.unlink(destino)
                elif os.path.exists(backup):
                    os.replace(backup, destino)
                    backups[destino] = None
            except OSError as exc:
                rollback_errors.append(f"{destino}: {exc}")
        if rollback_errors:
            raise RuntimeError(
                "Falha ao reverter a transacao JSON: " + "; ".join(rollback_errors)
            )
        raise
    finally:
        for temporario in temporarios.values():
            if os.path.exists(temporario):
                os.unlink(temporario)
        for backup in backups.values():
            if backup and os.path.exists(backup):
                os.unlink(backup)


def _catalogos_canonicos() -> tuple[set[str], set[str]]:
    # Imports tardios evitam carregar o runtime de combate em operacoes JSON
    # que nao envolvem o banco principal (por exemplo, match_config).
    from neural_fights.ai.personalities import PERSONALIDADES_PRESETS
    from neural_fights.core.skills import SKILL_DB

    return set(SKILL_DB), set(PERSONALIDADES_PRESETS)


def _validar_lista(documento: Any, rotulo: str) -> list[dict[str, Any]]:
    if not isinstance(documento, list):
        raise DataValidationError(f"{rotulo} deve ser uma lista JSON")
    erros = [
        f"{rotulo}[{indice}] deve ser um objeto JSON"
        for indice, item in enumerate(documento)
        if not isinstance(item, dict)
    ]
    if erros:
        raise DataValidationError(erros)
    return documento


def _nome_obrigatorio(item: Mapping[str, Any], caminho: str, erros: list[str]) -> str:
    nome = item.get("nome")
    if not isinstance(nome, str) or not nome.strip():
        erros.append(f"{caminho}.nome deve ser uma string nao vazia")
        return ""
    return nome.strip()


def _validar_numero(
    item: Mapping[str, Any],
    campo: str,
    caminho: str,
    erros: list[str],
    *,
    obrigatorio: bool = False,
    minimo: float | None = None,
    maximo: float | None = None,
    minimo_exclusivo: bool = False,
    inteiro: bool = False,
) -> float | None:
    if campo not in item:
        if obrigatorio:
            erros.append(f"{caminho}.{campo} e obrigatorio")
        return None

    valor = item[campo]
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        sufixo = " inteiro" if inteiro else " numerico"
        erros.append(f"{caminho}.{campo} deve ser{sufixo}")
        return None
    if inteiro and not isinstance(valor, int):
        erros.append(f"{caminho}.{campo} deve ser inteiro")
        return None
    try:
        numero = float(valor)
    except (OverflowError, ValueError):
        erros.append(f"{caminho}.{campo} deve ser finito")
        return None
    if not math.isfinite(numero):
        erros.append(f"{caminho}.{campo} deve ser finito")
        return None
    if minimo is not None:
        fora_do_minimo = numero <= minimo if minimo_exclusivo else numero < minimo
        if fora_do_minimo:
            operador = "maior que" if minimo_exclusivo else "maior ou igual a"
            erros.append(f"{caminho}.{campo} deve ser {operador} {minimo:g}")
    if maximo is not None and numero > maximo:
        erros.append(f"{caminho}.{campo} deve ser menor ou igual a {maximo:g}")
    return numero


def _validar_cores(
    item: Mapping[str, Any],
    campos: Sequence[str],
    caminho: str,
    erros: list[str],
) -> None:
    for campo in campos:
        if campo not in item:
            continue
        valor = item[campo]
        if isinstance(valor, bool) or not isinstance(valor, int):
            erros.append(f"{caminho}.{campo} deve ser inteiro entre 0 e 255")
        elif not 0 <= valor <= 255:
            erros.append(f"{caminho}.{campo} deve estar entre 0 e 255")


def _nomes_habilidades(
    arma: Mapping[str, Any],
    caminho: str,
    erros: list[str],
) -> set[str]:
    nomes: set[str] = set()
    habilidade_legada = arma.get("habilidade")
    if habilidade_legada not in (None, ""):
        if not isinstance(habilidade_legada, str):
            erros.append(f"{caminho}.habilidade deve ser uma string")
        elif not habilidade_legada.strip():
            erros.append(f"{caminho}.habilidade deve ser uma string nao vazia")
        else:
            nomes.add(habilidade_legada)

    habilidades = arma.get("habilidades", [])
    if habilidades is None:
        habilidades = []
    if not isinstance(habilidades, list):
        erros.append(f"{caminho}.habilidades deve ser uma lista")
        return nomes

    nomes_lista: list[str] = []
    for indice, habilidade_item in enumerate(habilidades):
        caminho_item = f"{caminho}.habilidades[{indice}]"
        if isinstance(habilidade_item, str):
            nome = habilidade_item
        elif isinstance(habilidade_item, Mapping):
            nome = habilidade_item.get("nome")
            _validar_numero(
                habilidade_item,
                "custo",
                caminho_item,
                erros,
                minimo=0,
            )
        else:
            nome = None
        if not isinstance(nome, str) or not nome.strip():
            erros.append(f"{caminho_item} nao possui nome valido")
        else:
            nomes.add(nome)
            if nome in nomes_lista:
                erros.append(f"{caminho}.habilidades possui nome duplicado: {nome!r}")
            nomes_lista.append(nome)

    if "habilidades" in arma and isinstance(habilidade_legada, str):
        habilidade_efetiva = nomes_lista[0] if nomes_lista else "Nenhuma"
        if habilidade_legada not in ("", habilidade_efetiva):
            erros.append(
                f"{caminho}.habilidade diverge da primeira habilidade da lista"
            )
    return nomes


def _validar_encantamentos(
    arma: Mapping[str, Any],
    caminho: str,
    erros: list[str],
    raridade: str,
) -> None:
    encantamentos = arma.get("encantamentos", [])
    if encantamentos is None:
        return
    if not isinstance(encantamentos, list):
        erros.append(f"{caminho}.encantamentos deve ser uma lista")
        return

    vistos: set[str] = set()
    for indice, encantamento in enumerate(encantamentos):
        caminho_item = f"{caminho}.encantamentos[{indice}]"
        if not isinstance(encantamento, str) or not encantamento.strip():
            erros.append(f"{caminho_item} deve ser uma string nao vazia")
            continue
        if encantamento not in ENCANTAMENTOS:
            erros.append(f"{caminho_item} desconhecido: {encantamento!r}")
        if encantamento in vistos:
            erros.append(
                f"{caminho}.encantamentos possui valor duplicado: {encantamento!r}"
            )
        vistos.add(encantamento)

    if raridade in LISTA_RARIDADES:
        # O catalogo historico possui um encantamento-base inclusive em armas
        # comuns, embora elas nao tenham slots *adicionais*.
        max_encantamentos = max(
            1,
            get_raridade_data(raridade)["max_encantamentos"],
        )
        if len(encantamentos) > max_encantamentos:
            erros.append(
                f"{caminho}.encantamentos excede os {max_encantamentos} "
                f"slot(s) da raridade {raridade!r}"
            )


def _validar_passiva(
    arma: Mapping[str, Any],
    caminho: str,
    erros: list[str],
) -> None:
    passiva = arma.get("passiva")
    if passiva is None:
        return
    if not isinstance(passiva, Mapping):
        erros.append(f"{caminho}.passiva deve ser um objeto ou null")
        return

    nome = passiva.get("nome")
    efeito = passiva.get("efeito")
    if not isinstance(nome, str) or not nome.strip():
        erros.append(f"{caminho}.passiva.nome deve ser uma string nao vazia")
    if not isinstance(efeito, str) or not efeito.strip():
        erros.append(f"{caminho}.passiva.efeito deve ser uma string nao vazia")
    _validar_numero(
        passiva,
        "valor",
        f"{caminho}.passiva",
        erros,
        obrigatorio=True,
    )
    if "descricao" in passiva and not isinstance(passiva["descricao"], str):
        erros.append(f"{caminho}.passiva.descricao deve ser uma string")


def _validar_geometria_arma(
    arma: Mapping[str, Any],
    caminho: str,
    tipo: str,
    erros: list[str],
) -> None:
    """Valida os campos fisicos usados pelo tipo, sem impor balanceamento."""

    campos_obrigatorios = set(TIPOS_ARMA[tipo]["geometria"])
    for campo in _CAMPOS_GEOMETRIA_ARMA:
        numero = _validar_numero(
            arma,
            campo,
            caminho,
            erros,
            obrigatorio=campo in campos_obrigatorios,
            minimo=0,
            inteiro=campo in _CAMPOS_INTEIROS_GEOMETRIA,
        )
        if campo in campos_obrigatorios and numero == 0:
            erros.append(f"{caminho}.{campo} deve ser maior que zero")


def validar_armas(
    armas: Any,
    *,
    skills_validas: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Valida estrutura, nomes unicos e referencias de skill das armas."""

    lista = _validar_lista(armas, "armas")
    if skills_validas is None:
        skills_validas, _ = _catalogos_canonicos()
    erros: list[str] = []
    nomes_vistos: set[str] = set()

    for indice, arma in enumerate(lista):
        caminho = f"armas[{indice}]"
        nome = _nome_obrigatorio(arma, caminho, erros)
        if nome in nomes_vistos:
            erros.append(f"nome de arma duplicado: {nome!r}")
        nomes_vistos.add(nome)

        tipo = arma.get("tipo")
        if tipo not in LISTA_TIPOS_ARMA:
            erros.append(f"{caminho}.tipo desconhecido: {tipo!r}")
        else:
            _validar_geometria_arma(arma, caminho, tipo, erros)
        raridade = arma.get("raridade", "Comum")
        if raridade not in LISTA_RARIDADES:
            erros.append(f"{caminho}.raridade desconhecida: {raridade!r}")

        for campo in ("dano", "peso"):
            _validar_numero(
                arma,
                campo,
                caminho,
                erros,
                obrigatorio=True,
                minimo=0,
            )

        _validar_cores(arma, ("r", "g", "b"), caminho, erros)
        _validar_numero(arma, "custo_mana", caminho, erros, minimo=0)
        # Critico do catalogo e a chance BASE em pontos percentuais; a
        # raridade soma ate +15. Acima de 15 de base o critico deixa de ser
        # evento raro e volta a ser o estado permanente que ja foi bug.
        _validar_numero(
            arma,
            "critico",
            caminho,
            erros,
            minimo=0,
            maximo=15,
        )
        _validar_numero(
            arma,
            "velocidade_ataque",
            caminho,
            erros,
            minimo=0,
            minimo_exclusivo=True,
        )
        durabilidade = _validar_numero(
            arma,
            "durabilidade",
            caminho,
            erros,
            minimo=0,
        )
        durabilidade_max = _validar_numero(
            arma,
            "durabilidade_max",
            caminho,
            erros,
            minimo=0,
            minimo_exclusivo=True,
        )
        durabilidade_efetiva = 100.0 if durabilidade is None else durabilidade
        durabilidade_max_efetiva = (
            100.0 if durabilidade_max is None else durabilidade_max
        )
        if durabilidade_efetiva > durabilidade_max_efetiva:
            erros.append(f"{caminho}.durabilidade nao pode exceder durabilidade_max")

        if "cabo_dano" in arma and not isinstance(arma["cabo_dano"], bool):
            erros.append(f"{caminho}.cabo_dano deve ser booleano")
        if "estilo" in arma and (
            not isinstance(arma["estilo"], str) or not arma["estilo"].strip()
        ):
            erros.append(f"{caminho}.estilo deve ser uma string nao vazia")
        afinidade = arma.get("afinidade_elemento")
        if afinidade is not None and (
            not isinstance(afinidade, str) or not afinidade.strip()
        ):
            erros.append(
                f"{caminho}.afinidade_elemento deve ser uma string nao vazia ou null"
            )

        _validar_encantamentos(arma, caminho, erros, raridade)
        _validar_passiva(arma, caminho, erros)

        desconhecidas = _nomes_habilidades(arma, caminho, erros) - skills_validas
        if desconhecidas:
            erros.append(
                f"{caminho} referencia skills inexistentes: {', '.join(sorted(desconhecidas))}"
            )
        habilidades = arma.get("habilidades")
        if isinstance(habilidades, list) and raridade in LISTA_RARIDADES:
            max_habilidades = get_raridade_data(raridade)["slots_habilidade"]
            if len(habilidades) > max_habilidades:
                erros.append(
                    f"{caminho}.habilidades excede os {max_habilidades} "
                    f"slot(s) da raridade {raridade!r}"
                )

    if erros:
        raise DataValidationError(erros)
    return lista


def validar_personagens(
    personagens: Any,
    *,
    nomes_armas: set[str],
    personalidades_validas: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Valida personagens e suas referencias a armas e personalidades."""

    lista = _validar_lista(personagens, "personagens")
    if personalidades_validas is None:
        _, personalidades_validas = _catalogos_canonicos()
    erros: list[str] = []
    nomes_vistos: set[str] = set()

    for indice, personagem in enumerate(lista):
        caminho = f"personagens[{indice}]"
        nome = _nome_obrigatorio(personagem, caminho, erros)
        if nome in nomes_vistos:
            erros.append(f"nome de personagem duplicado: {nome!r}")
        nomes_vistos.add(nome)

        _validar_numero(
            personagem,
            "tamanho",
            caminho,
            erros,
            obrigatorio=True,
            minimo=0,
            minimo_exclusivo=True,
        )
        _validar_numero(
            personagem,
            "forca",
            caminho,
            erros,
            obrigatorio=True,
            minimo=0,
            minimo_exclusivo=True,
        )
        _validar_numero(
            personagem,
            "mana",
            caminho,
            erros,
            obrigatorio=True,
            minimo=0,
        )
        _validar_cores(
            personagem,
            ("cor_r", "cor_g", "cor_b"),
            caminho,
            erros,
        )

        nome_arma = personagem.get("nome_arma")
        if not isinstance(nome_arma, str) or nome_arma not in nomes_armas:
            erros.append(f"{caminho}.nome_arma inexistente: {nome_arma!r}")
        personalidade = personagem.get("personalidade", "Aleatório")
        if (
            not isinstance(personalidade, str)
            or personalidade not in personalidades_validas
        ):
            erros.append(f"{caminho}.personalidade inexistente: {personalidade!r}")
        if personagem.get("classe") not in LISTA_CLASSES:
            erros.append(f"{caminho}.classe desconhecida: {personagem.get('classe')!r}")

    if erros:
        raise DataValidationError(erros)
    return lista


def validar_database(armas: Any, personagens: Any) -> None:
    """Valida os dois documentos e todas as referencias cruzadas."""

    skills_validas, personalidades_validas = _catalogos_canonicos()
    lista_armas = validar_armas(armas, skills_validas=skills_validas)
    validar_personagens(
        personagens,
        nomes_armas={arma["nome"].strip() for arma in lista_armas},
        personalidades_validas=personalidades_validas,
    )


@_serializar_persistencia
def carregar_database(
    *,
    arquivo_armas: str | None = None,
    arquivo_personagens: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Carrega e valida o snapshot coerente de armas e personagens."""

    armas_path, chars_path = resolver_database_paths(
        arquivo_armas=arquivo_armas,
        arquivo_personagens=arquivo_personagens,
    )
    raw_armas = carregar_json(armas_path)
    raw_chars = carregar_json(chars_path)
    validar_database(raw_armas, raw_chars)
    return raw_armas, raw_chars


@_serializar_persistencia
def salvar_database(
    armas: Sequence[Mapping[str, Any]],
    personagens: Sequence[Mapping[str, Any]],
    *,
    arquivo_armas: str | None = None,
    arquivo_personagens: str | None = None,
) -> None:
    """Valida e grava o par armas/personagens com rollback transacional."""

    armas_json = [dict(item) for item in armas]
    chars_json = [dict(item) for item in personagens]
    validar_database(armas_json, chars_json)
    armas_path, chars_path = resolver_database_paths(
        arquivo_armas=arquivo_armas,
        arquivo_personagens=arquivo_personagens,
        para_escrita=True,
    )
    os.makedirs(os.path.dirname(armas_path), exist_ok=True)
    os.makedirs(os.path.dirname(chars_path), exist_ok=True)
    salvar_jsons_coerentes(
        {
            armas_path: armas_json,
            chars_path: chars_json,
        }
    )


@_serializar_persistencia
def atualizar_arma(
    nome_atual: str,
    arma_atualizada: Mapping[str, Any] | Arma,
    *,
    arquivo_armas: str | None = None,
    arquivo_personagens: str | None = None,
) -> int:
    """Atualiza todos os campos e referencias da arma em uma transacao."""

    nome_atual = nome_atual.strip()
    if not nome_atual:
        raise DataValidationError("o nome atual deve ser nao vazio")
    if isinstance(arma_atualizada, Mapping):
        nova_arma = dict(arma_atualizada)
    else:
        converter = getattr(arma_atualizada, "to_dict", None)
        if not callable(converter):
            raise TypeError("arma_atualizada deve ser um mapeamento ou Arma")
        nova_arma = dict(converter())

    novo_nome = str(nova_arma.get("nome", "")).strip()
    nova_arma["nome"] = novo_nome
    if not novo_nome:
        raise DataValidationError("o novo nome deve ser nao vazio")

    armas, personagens = carregar_database(
        arquivo_armas=arquivo_armas,
        arquivo_personagens=arquivo_personagens,
    )
    nomes = {arma["nome"] for arma in armas}
    if nome_atual not in nomes:
        raise DataValidationError(f"arma inexistente: {nome_atual!r}")
    if novo_nome != nome_atual and novo_nome in nomes:
        raise DataValidationError(f"ja existe uma arma chamada {novo_nome!r}")

    armas_novas = [dict(arma) for arma in armas]
    indice = next(
        indice
        for indice, arma in enumerate(armas_novas)
        if arma["nome"] == nome_atual
    )
    armas_novas[indice] = nova_arma
    personagens_novos = [dict(personagem) for personagem in personagens]
    afetados = 0
    if novo_nome != nome_atual:
        for personagem in personagens_novos:
            if personagem["nome_arma"] == nome_atual:
                personagem["nome_arma"] = novo_nome
                afetados += 1

    salvar_database(
        armas_novas,
        personagens_novos,
        arquivo_armas=arquivo_armas,
        arquivo_personagens=arquivo_personagens,
    )
    return afetados


@_serializar_persistencia
def renomear_arma(
    nome_atual: str,
    novo_nome: str,
    *,
    arquivo_armas: str | None = None,
    arquivo_personagens: str | None = None,
) -> int:
    """Renomeia uma arma e todas as referencias de personagens na transacao."""

    nome_atual = nome_atual.strip()
    novo_nome = novo_nome.strip()
    if not nome_atual or not novo_nome:
        raise DataValidationError("os nomes atual e novo devem ser nao vazios")

    armas, personagens = carregar_database(
        arquivo_armas=arquivo_armas,
        arquivo_personagens=arquivo_personagens,
    )
    nomes = {arma["nome"] for arma in armas}
    if nome_atual not in nomes:
        raise DataValidationError(f"arma inexistente: {nome_atual!r}")
    if novo_nome != nome_atual and novo_nome in nomes:
        raise DataValidationError(f"ja existe uma arma chamada {novo_nome!r}")
    if novo_nome == nome_atual:
        return 0

    armas_novas = [dict(arma) for arma in armas]
    personagens_novos = [dict(personagem) for personagem in personagens]
    next(arma for arma in armas_novas if arma["nome"] == nome_atual)["nome"] = novo_nome
    afetados = 0
    for personagem in personagens_novos:
        if personagem["nome_arma"] == nome_atual:
            personagem["nome_arma"] = novo_nome
            afetados += 1

    salvar_database(
        armas_novas,
        personagens_novos,
        arquivo_armas=arquivo_armas,
        arquivo_personagens=arquivo_personagens,
    )
    return afetados


@_serializar_persistencia
def remover_arma(
    nome: str,
    *,
    substituir_por: str | None = None,
    arquivo_armas: str | None = None,
    arquivo_personagens: str | None = None,
) -> int:
    """Remove uma arma sem deixar personagens orfaos.

    Se houver referencias, ``substituir_por`` e obrigatorio e precisa apontar
    para outra arma existente. Retorna a quantidade de personagens migrados.
    """

    nome = nome.strip()
    substituir_por = substituir_por.strip() if substituir_por else None
    armas, personagens = carregar_database(
        arquivo_armas=arquivo_armas,
        arquivo_personagens=arquivo_personagens,
    )
    nomes = {arma["nome"] for arma in armas}
    if nome not in nomes:
        raise DataValidationError(f"arma inexistente: {nome!r}")

    afetados = sum(personagem["nome_arma"] == nome for personagem in personagens)
    if afetados:
        if substituir_por is None:
            raise DataValidationError(
                f"{afetados} personagem(ns) usam {nome!r}; informe substituir_por"
            )
        if substituir_por == nome or substituir_por not in nomes:
            raise DataValidationError(f"arma substituta invalida: {substituir_por!r}")

    armas_novas = [dict(arma) for arma in armas if arma["nome"] != nome]
    personagens_novos = [dict(personagem) for personagem in personagens]
    for personagem in personagens_novos:
        if personagem["nome_arma"] == nome:
            personagem["nome_arma"] = substituir_por

    salvar_database(
        armas_novas,
        personagens_novos,
        arquivo_armas=arquivo_armas,
        arquivo_personagens=arquivo_personagens,
    )
    return afetados


@_serializar_persistencia
def resolver_match_config_path(arquivo: str | None = None) -> str:
    """Resolve o estado local, permitindo isolamento por processo/teste."""

    caminho = arquivo or os.environ.get(MATCH_CONFIG_ENV) or ARQUIVO_MATCH
    return os.path.abspath(caminho)


@_serializar_persistencia
def carregar_match_config(arquivo: str | None = None) -> dict[str, Any]:
    """Carrega a configuracao compartilhada por todos os pontos de entrada."""

    caminho = resolver_match_config_path(arquivo)
    caminho_explicito = arquivo is not None or bool(os.environ.get(MATCH_CONFIG_ENV))
    if caminho_explicito and not os.path.exists(caminho):
        raise FileNotFoundError(f"Configuracao de luta inexistente: {caminho}")
    origem = caminho if os.path.exists(caminho) else ARQUIVO_MATCH_DEFAULT
    config = carregar_json(origem, padrao={})
    if not isinstance(config, dict):
        raise DataValidationError(f"Configuracao de luta invalida: {origem}")
    return config


@_serializar_persistencia
def salvar_match_config(
    config: Mapping[str, Any],
    preservar_existente: bool = True,
    *,
    arquivo: str | None = None,
) -> str:
    """Atualiza a configuracao canonica sem apagar opcoes de outros fluxos."""

    if not isinstance(config, Mapping):
        raise TypeError("A configuracao de luta precisa ser um mapeamento")
    caminho = resolver_match_config_path(arquivo)
    dados_finais: dict[str, Any] = {}
    if preservar_existente and os.path.exists(caminho):
        dados_finais.update(carregar_match_config(caminho))
    dados_finais.update(config)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    salvar_json(caminho, dados_finais)
    return caminho


@_serializar_persistencia
def carregar_armas(
    *,
    arquivo_armas: str | None = None,
    arquivo_personagens: str | None = None,
) -> list[Arma]:
    raw, _ = carregar_database(
        arquivo_armas=arquivo_armas,
        arquivo_personagens=arquivo_personagens,
    )
    return [Arma(**item) for item in raw]


@_serializar_persistencia
def carregar_personagens(
    *,
    arquivo_armas: str | None = None,
    arquivo_personagens: str | None = None,
) -> list[Personagem]:
    raw_armas, raw_chars = carregar_database(
        arquivo_armas=arquivo_armas,
        arquivo_personagens=arquivo_personagens,
    )
    pesos_por_nome = {
        item["nome"]: float(item.get("peso", 0))
        * get_raridade_data(item.get("raridade", "Comum"))["mod_peso"]
        for item in raw_armas
    }

    lista = []
    for item in raw_chars:
        nome_arma = item["nome_arma"]
        lista.append(
            Personagem(
                item["nome"],
                item["tamanho"],
                item["forca"],
                item["mana"],
                nome_arma,
                pesos_por_nome[nome_arma],
                item.get("cor_r", 200),
                item.get("cor_g", 50),
                item.get("cor_b", 50),
                item.get("classe", "Guerreiro (Força Bruta)"),
                item.get("personalidade", "Aleatório"),
            )
        )
    return lista


@_serializar_persistencia
def salvar_lista_armas(lista: Sequence[Arma]) -> None:
    armas = [arma.to_dict() for arma in lista]
    _, personagens = carregar_database()
    salvar_database(armas, personagens)


@_serializar_persistencia
def salvar_lista_chars(lista: Sequence[Personagem]) -> None:
    armas, _ = carregar_database()
    personagens = [personagem.to_dict() for personagem in lista]
    salvar_database(armas, personagens)


@_serializar_persistencia
def carregar_arma_por_nome(nome_arma: str) -> Arma | None:
    """Carrega uma arma especifica pelo nome."""

    return next((arma for arma in carregar_armas() if arma.nome == nome_arma), None)
