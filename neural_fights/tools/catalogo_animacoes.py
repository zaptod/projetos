"""Catalogo das animacoes que a arte do palco pode fornecer.

O catalogo nao e uma segunda lista do jogo: ele le os catalogos da engine e
os mesmos JSONs que a interface carrega.  A unica excecao deliberada e
``sem_animacao``: eventos que a decisao de produto manda nao desenhar.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Iterable

from neural_fights.core.skills import SKILL_DB
from neural_fights.core.status_runtime import BUFF_EFFECT_RUNTIME, STATUS_RUNTIME
from neural_fights.data import database
from neural_fights.models.constants import CLASSES_DATA, TIPOS_ARMA
from neural_fights.recording import timeline
EXPRESSOES = (
    "neutro", "focado", "glacial", "determinado", "furia", "berserk", "confiante", "animado",
    "euforico", "extase", "panico", "nervoso", "desespero", "tedio", "tristeza", "morto",
    "tonto", "dor", "esforco", "firmeza", "alerta", "confuso", "limite", "concentrado",
)


def slug(texto: str) -> str:
    de, para = "áàâãäåéèêëíìîïóòôõöúùûüçñý", "aaaaaaeeeeiiiiooooouuuucny"
    saida = ""
    for letra in str(texto or "").strip().lower():
        indice = de.find(letra)
        letra = para[indice] if indice >= 0 else letra
        if "a" <= letra <= "z" or "0" <= letra <= "9":
            saida += letra
        elif saida and not saida.endswith("_"):
            saida += "_"
    return saida.rstrip("_")


def texto_humano(chave: str) -> str:
    palavras = {"gravitacao": "gravitação", "critico": "crítico", "projetil": "projétil",
                "colisao": "colisão", "obstaculo": "obstáculo", "explosao": "explosão",
                "agarrao": "agarrão", "vulneravel": "vulnerável", "relogio": "relógio",
                "paralisia": "paralisia", "lancado": "lançado", "magica": "mágica"}
    texto = " ".join(palavras.get(p, p) for p in str(chave).lower().replace("_", " ").split())
    return texto[:1].upper() + texto[1:]


RAIZ = Path(__file__).resolve().parents[2]
PADRAO = RAIZ / "palco" / "biblioteca" / "catalogo_animacoes.json"
DOCUMENTO = RAIZ / "docs" / "sprites" / "CATALOGO_ANIMACOES.md"
VERSAO = 1

# Estes eventos carregam informacao para a interface, mas nao sao arte do
# combate. A lista e publica no JSON para que nenhum evento seja esquecido.
SEM_ANIMACAO = {
    "plano": "sinal para a narrativa; nao e uma peca do combate",
    "refletido": "troca o dono da trilha existente; nao cria uma peca nova",
    "tell": "sinal da IA para a narrativa; sem desenho no palco",
    "texto": "decisao do jogo: numeros de dano nao entram no palco",
    "virada": "marcacao da narrativa; sem desenho no combate",
}


def _eventos_da_timeline() -> tuple[str, ...]:
    """Le os nomes usados pela sonda, sem manter uma copia aqui."""
    arvore = ast.parse(Path(timeline.__file__).read_text(encoding="utf-8"))
    encontrados = set(timeline.CAMPOS_EVENTOS_R3)
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Attribute):
            continue
        if no.func.attr != "_evento" or len(no.args) < 2:
            continue
        tipo = no.args[1]
        if isinstance(tipo, ast.Constant) and isinstance(tipo.value, str):
            encontrados.add(tipo.value)
    return tuple(sorted(encontrados))


def gatilhos_do_jogo() -> frozenset[str]:
    """Vocabulário que pode aparecer em ``gatilho`` no catalogo."""
    eventos = _eventos_da_timeline()
    canais = {nome for nome, _unidade, _descricao in timeline.CANAIS_LUTADOR}
    return frozenset({"ocioso", "expr"} | set(eventos) | set(timeline.FLAGS)
                     | canais | set(timeline.CANAIS_OBJETO)
                     | set(timeline.CANAIS_EFEITO) | set(timeline.GATILHOS_MOVIMENTO)
                     | set(timeline.NOMES_CANAIS_BOLA))


def _rotulo(valor: str) -> str:
    valor = str(valor or "")
    return texto_humano(valor) if valor.isupper() or "_" in valor else valor


def _ids_por_nome(nomes: Iterable[str]) -> dict[str, str]:
    """Slug legivel, com sufixo estavel apenas quando dois nomes colidem."""
    nomes = tuple(str(nome) for nome in nomes)
    quantidade = {nome: sum(slug(outro) == slug(nome) for outro in nomes) for nome in nomes}
    return {
        nome: slug(nome) if quantidade[nome] == 1 else
        f"{slug(nome)}_{hashlib.sha1(nome.encode('utf-8')).hexdigest()[:8]}"
        for nome in nomes
    }


def _animacao(identificador: str, rotulo: str, gatilho: str, *, loop: bool,
              fps: int = 12, quadros: int = 6, ancora: str = "centro",
              camada: int = 20, segue: str = "lutador",
              tamanho: str = "1,0 do corpo", intervalo_ocioso: dict | None = None) -> dict:
    animacao = {
        "id": identificador,
        "rotulo": rotulo,
        "gatilho": gatilho,
        "loop": loop,
        "fps_padrao": fps,
        "quadros_sugeridos": quadros,
        "ancora_padrao": ancora,
        "camada": camada,
        "segue": segue,
        "tamanho_padrao": tamanho,
    }
    if intervalo_ocioso is not None:
        animacao["intervalo_ocioso"] = intervalo_ocioso
    return animacao


def _peca(identificador: str, grupo: str, rotulo: str, origem: str,
           estados: list[dict], heranca: Iterable[str]) -> dict:
    return {
        "id": identificador,
        "grupo": grupo,
        "rotulo": rotulo,
        "origem": origem,
        "estados": estados,
        "heranca": list(heranca),
    }


def _estado(identificador: str, rotulo: str, *animacoes: dict) -> dict:
    return {"id": identificador, "rotulo": rotulo, "animacoes": list(animacoes)}


def _animacao_arma(identificador: str, rotulo: str, gatilho: str, *, loop: bool = False,
                   fps: int = 14, quadros: int = 6) -> dict:
    return _animacao(identificador, rotulo, gatilho, loop=loop, fps=fps, quadros=quadros,
                     ancora="mao", camada=30, segue="mao do lutador", tamanho="1,0 do corpo")


def _estados_arma(tipo: str) -> list[dict]:
    """Estados que a timeline realmente permite observar para cada tipo."""
    parada = _estado("parada", "Parada", _animacao_arma("ociosa", "Parada", "ocioso", loop=True,
                                                         fps=8, quadros=4))
    golpe = _estado("golpe", "Golpe", _animacao_arma("golpe", "Golpe", "golpe_fase",
                                                       fps=16, quadros=8))
    if tipo == "Arco":
        return [parada,
                _estado("puxar", "Puxar a corda", _animacao_arma("puxar", "Puxar", "arma_puxada")),
                _estado("disparo", "Disparo", _animacao_arma("disparo", "Disparo", "projetil_arma"))]
    if tipo == "Corrente":
        return [parada,
                _estado("girando", "Girando", _animacao_arma("girar", "Girar", "golpe_fase", loop=True)),
                _estado("arremesso", "Arremesso", _animacao_arma("arremessar", "Arremessar", "bola_x"))]
    if tipo == "Orbital":
        return [_estado("orbitando", "Orbitando", _animacao_arma("orbitar", "Orbitar", "orbe", loop=True))]
    if tipo == "Mágica":
        return [
            _estado("orbitando", "Orbitando", _animacao_arma("orbitar", "Orbitar", "orbe", loop=True)),
            _estado("carregando", "Carregando", _animacao_arma("carregar", "Carregar", "orbe", loop=True)),
            _estado("disparando", "Disparando", _animacao_arma("disparar", "Disparar", "orbe")),
        ]
    if tipo == "Arremesso":
        return [parada,
                _estado("lancar", "Lançar", _animacao_arma("lancar", "Lançar", "golpe_fase")),
                _estado("projetil_voando", "Projétil voando", _animacao_arma(
                    "voando", "Voando", "projetil_arma", loop=True)),
                _estado("retorno", "Retorno", _animacao_arma("retorno", "Retorno", "projetil_fim"))]
    if tipo == "Transformável":
        return [parada, golpe,
                _estado("forma_1", "Forma 1", _animacao_arma("forma_1", "Forma 1", "ocioso", loop=True)),
                _estado("forma_2", "Forma 2", _animacao_arma("forma_2", "Forma 2", "ocioso", loop=True)),
                _estado("transformar", "Transformar", _animacao_arma("transformar", "Transformar", "transformado"))]
    return [parada, golpe]


def _estados_skill(tipo: str) -> list[dict]:
    objeto = {
        "PROJETIL": "projetil", "AREA": "area", "BEAM": "beam",
        "SUMMON": "summon", "TRAP": "trap", "CHANNEL": "canal",
        "TRANSFORM": "transformacao", "BUFF": "buff", "DASH": "dash",
    }.get(tipo, "skill")
    segue = "fixo no mundo" if objeto in timeline.CANAIS_OBJETO else "lutador"
    return [
        _estado("conjuracao", "Conjuração", _animacao("conjurar", "Conjurar", "skill",
                                                        loop=False, fps=12, quadros=6,
                                                        ancora="mao", camada=35,
                                                        segue="lutador", tamanho="0,6 do corpo")),
        _estado("efeito", "Efeito", _animacao("efeito", "Efeito", objeto,
                                                loop=objeto not in {"dash", "skill"}, fps=12,
                                                quadros=8, ancora="ponto do evento", camada=45,
                                                segue=segue, tamanho="1,0 do corpo")),
    ]


def _estados_objeto(tipo: str) -> list[dict]:
    """Ciclo de vida exposto pelas trilhas de objeto da timeline."""
    comum = [
        _estado("surgir", "Surgir", _animacao("surgir", "Surgir", "skill", loop=False,
                                                 fps=14, quadros=5, ancora="ponto do evento",
                                                 camada=45, segue="fixo no mundo", tamanho="1,0 do corpo")),
        _estado("ativo", "Ativo", _animacao("ativo", "Ativo", tipo, loop=True,
                                               fps=12, quadros=8, ancora="ponto do evento",
                                               camada=45, segue="fixo no mundo", tamanho="1,0 do corpo")),
    ]
    if tipo in {"projetil", "projetil_arma"}:
        comum[1] = _estado("voando", "Voando", _animacao(
            "voando", "Voando", tipo, loop=True, fps=16, quadros=6,
            ancora="centro do projétil", camada=45, segue="fixo no mundo", tamanho="0,4 do corpo"))
        comum.extend([
            _estado("impacto", "Impacto", _animacao("impacto", "Impacto", "acerto", loop=False,
                                                       fps=18, quadros=5, ancora="ponto do evento",
                                                       camada=70, segue="fixo no mundo", tamanho="0,7 do corpo")),
            _estado("sumir", "Sumir", _animacao("sumir", "Sumir", "projetil_fim", loop=False,
                                                    fps=14, quadros=4, ancora="ponto do evento",
                                                    camada=45, segue="fixo no mundo", tamanho="0,4 do corpo")),
        ])
    elif tipo == "area":
        comum.append(_estado("impacto", "Impacto", _animacao(
            "impacto", "Impacto", "explosao", loop=False, fps=16, quadros=6,
            ancora="ponto do evento", camada=70, segue="fixo no mundo", tamanho="1,0 do corpo")))
    elif tipo == "orbe":
        comum[1] = _estado("orbitando", "Orbitando", _animacao(
            "orbitar", "Orbitar", "orbe", loop=True, fps=12, quadros=8,
            ancora="centro do orbe", camada=45, segue="fixo no mundo", tamanho="0,5 do corpo"))
    return comum


def _dados(arquivo_armas: str | Path | None, arquivo_personagens: str | Path | None):
    """Carrega a mesma dupla coerente usada pelas telas, sempre por caminho."""
    if arquivo_armas is None:
        arquivo_armas = database.ARQUIVO_ARMAS
    if arquivo_personagens is None:
        arquivo_personagens = database.ARQUIVO_CHARS
    armas = database.carregar_armas(arquivo_armas=str(arquivo_armas),
                                    arquivo_personagens=str(arquivo_personagens))
    personagens = database.carregar_personagens(arquivo_armas=str(arquivo_armas),
                                                 arquivo_personagens=str(arquivo_personagens))
    return armas, personagens


def gerar_catalogo(*, arquivo_armas: str | Path | None = None,
                   arquivo_personagens: str | Path | None = None) -> dict:
    """Monta o documento em memoria; parametros permitem testar uma copia."""
    armas, _personagens = _dados(arquivo_armas, arquivo_personagens)
    pecas: list[dict] = []

    pecas.append(_peca("lutador.corpo", "lutador", "Corpo e pele", "manifesto.parte=pele", [
        _estado("parado", "Parado", _animacao("parado", "Parado", "ocioso", loop=True,
                                                  fps=8, quadros=4, ancora="centro do corpo",
                                                  camada=20, segue="lutador", tamanho="1,0 do corpo")),
        _estado("dano", "Dano", _animacao("dano", "Dano", "acerto", loop=False,
                                              fps=16, quadros=4, ancora="centro do corpo",
                                              camada=20, segue="lutador", tamanho="1,0 do corpo")),
        _estado("ko", "Nocaute", _animacao("ko", "Nocaute", "ko", loop=False,
                                                fps=12, quadros=8, ancora="centro do corpo",
                                                camada=20, segue="lutador", tamanho="1,0 do corpo")),
    ], ["lutador.generico"]))

    # Rosto: a lista vem do mesmo manifesto que o palco usa para resolver a arte.
    for parte, camada in (("olhos", 40), ("sobrancelhas", 45), ("boca", 50),
                          ("detalhe_rosto", 55)):
        estados = []
        for expressao in EXPRESSOES:
            parado = _animacao("parado", "Parado", "expr", loop=True, fps=8, quadros=1,
                                ancora=f"centro do {parte} no gabarito do rosto", camada=camada,
                                segue="lutador", tamanho="fração do rosto")
            if parte == "olhos":
                estados.append(_estado(expressao, _rotulo(expressao), parado, _animacao(
                    "piscar", "Piscar", "ocioso", loop=False, fps=12, quadros=3,
                    ancora="centro dos olhos no gabarito do rosto", camada=camada,
                    segue="lutador", tamanho="fração do rosto",
                    intervalo_ocioso={"min_s": 2, "max_s": 5, "semente": "slot+expressao"})))
            elif parte == "boca":
                estados.append(_estado(expressao, _rotulo(expressao), parado, _animacao(
                    "grito", "Grito", "golpe_fase", loop=False, fps=14, quadros=4,
                    ancora="centro da boca no gabarito do rosto", camada=camada,
                    segue="lutador", tamanho="fração do rosto")))
            else:
                estados.append(_estado(expressao, _rotulo(expressao), parado))
        pecas.append(_peca(f"lutador.rosto.{parte}", "lutador", _rotulo(parte),
                            f"manifesto.expressao={parte}", estados,
                            [f"lutador.rosto.{parte}.generico"]))

    # Classes sao a ultima variacao de arte do lutador; nomes de personagem nao entram aqui.
    classes = sorted(CLASSES_DATA)
    ids_classe = _ids_por_nome(classes)
    for classe in classes:
        ident = f"classe.{ids_classe[classe]}"
        pecas.append(_peca(ident, "lutador", classe, f"classe={classe}", [
            _estado("base", "Base", _animacao("ociosa", "Ociosa", "ocioso", loop=True,
                                                 fps=8, quadros=4, ancora="centro do corpo",
                                                 camada=20, segue="lutador", tamanho="1,0 do corpo"))],
                            ["lutador.generico"]))
    tipos = sorted(TIPOS_ARMA)
    ids_tipo = _ids_por_nome(tipos)
    estilos_por_tipo = {tipo: set() for tipo in TIPOS_ARMA}
    for arma in armas:
        estilos_por_tipo[arma.tipo].add(arma.estilo)
    estilos = sorted(estilo for estilos_do_tipo in estilos_por_tipo.values() for estilo in estilos_do_tipo)
    ids_estilo = _ids_por_nome(estilos)
    for tipo in tipos:
        ident = f"arma.tipo.{ids_tipo[tipo]}"
        pecas.append(_peca(ident, "arma", f"Arma {tipo}", f"arma.tipo={tipo}",
                            _estados_arma(tipo), ["arma.generica"]))
    for tipo in tipos:
        for estilo in sorted(estilos_por_tipo[tipo]):
            pecas.append(_peca(f"arma.estilo.{ids_estilo[estilo]}", "arma", estilo,
                                f"arma.estilo={estilo}; arma.tipo={tipo}", _estados_arma(tipo),
                                [f"arma.tipo.{ids_tipo[tipo]}", "arma.generica"]))
    if "Corrente" in ids_tipo:
        pecas.append(_peca("arma.tipo.corrente.cabeca", "arma", "Cabeça da corrente",
                            "timeline.corrente.bola_x; arma.tipo=Corrente", [
                                _estado("parada", "Parada", _animacao(
                                    "parada", "Parada", "ocioso", loop=True, fps=8, quadros=4,
                                    ancora="bola da corrente", camada=31, segue="corrente", tamanho="0,4 do corpo")),
                                _estado("girando", "Girando", _animacao(
                                    "girando", "Girando", "bola_x", loop=True, fps=16, quadros=8,
                                    ancora="bola da corrente", camada=31, segue="corrente", tamanho="0,4 do corpo")),
                                _estado("arremesso", "Arremesso", _animacao(
                                    "arremesso", "Arremesso", "bola_x", loop=False, fps=16, quadros=6,
                                    ancora="bola da corrente", camada=31, segue="corrente", tamanho="0,4 do corpo")),
                            ], ["arma.tipo.corrente", "arma.generica"]))

    skills = [(nome, dados) for nome, dados in SKILL_DB.items() if nome != "Nenhuma"]
    tipos_skill = sorted({str(dados.get("tipo", "NADA")) for _nome, dados in skills})
    ids_tipo_skill = _ids_por_nome(tipos_skill)
    for tipo in tipos_skill:
        pecas.append(_peca(f"skill.tipo.{ids_tipo_skill[tipo]}", "skill", _rotulo(tipo),
                            f"skill.tipo={tipo}", _estados_skill(tipo), ["skill.generica"]))
    skills.sort(key=lambda item: item[0].casefold())
    ids_skill = _ids_por_nome(nome for nome, _dados in skills)
    for nome, dados in skills:
        tipo = str(dados.get("tipo", "NADA"))
        pecas.append(_peca(f"skill.{ids_skill[nome]}", "skill", nome,
                            f"skill={nome}; skill.tipo={tipo}", _estados_skill(tipo),
                            [f"skill.tipo.{ids_tipo_skill[tipo]}", "skill.generica"]))

    elementos = sorted({str(dados.get("elemento", "")) for _nome, dados in skills if dados.get("elemento")})
    ids_elemento = _ids_por_nome(elementos)
    for elemento in elementos:
        pecas.append(_peca(f"elemento.{ids_elemento[elemento]}", "elemento", _rotulo(elemento),
                            f"skill.elemento={elemento}", [
                                _estado("ativo", "Ativo", _animacao(
                                    "brilho", "Brilho", "skill", loop=True, fps=10, quadros=6,
                                    ancora="ponto do evento", camada=42, segue="fixo no mundo",
                                    tamanho="0,8 do corpo"))], ["elemento.generico"]))

    status_ids = sorted(STATUS_RUNTIME)
    ids_status = _ids_por_nome(status_ids)
    for status in status_ids:
        pecas.append(_peca(f"estado.{ids_status[status]}", "estado_personagem", _rotulo(status),
                            f"status={status}", [
                                _estado("ativo", "Ativo", _animacao(
                                    "ativo", "Ativo", "status", loop=True, fps=10, quadros=6,
                                    ancora="centro do corpo", camada=65, segue="lutador",
                                    tamanho="1,15 do corpo"))], ["estado.generico"]))
    buffs = sorted(BUFF_EFFECT_RUNTIME)
    ids_buff = _ids_por_nome(buffs)
    for buff in buffs:
        pecas.append(_peca(f"buff.{ids_buff[buff]}", "buff", _rotulo(buff), f"buff={buff}", [
            _estado("ativo", "Ativo", _animacao("ativo", "Ativo", "buff", loop=True,
                                                   fps=10, quadros=6, ancora="centro do corpo",
                                                   camada=64, segue="lutador", tamanho="1,2 do corpo"))],
                            ["buff.generico"]))
    ids_flags = _ids_por_nome(timeline.FLAGS)
    for estado in timeline.FLAGS:
        pecas.append(_peca(f"estado_lutador.{ids_flags[estado]}", "estado_personagem", _rotulo(estado),
                            f"timeline.flags={estado}", [
                                _estado("ativo", "Ativo", _animacao(
                                    "ativo", "Ativo", estado, loop=True, fps=10, quadros=6,
                                    ancora="centro do corpo", camada=63, segue="lutador",
                                    tamanho="1,0 do corpo"))], ["estado.generico"]))

    objetos = sorted(timeline.CANAIS_OBJETO)
    ids_objeto = _ids_por_nome(objetos)
    for tipo in objetos:
        pecas.append(_peca(f"efeito.{ids_objeto[tipo]}", "efeito", _rotulo(tipo),
                            f"timeline.objeto={tipo}", _estados_objeto(tipo), ["efeito.generico"]))
    ids_movimento = _ids_por_nome(timeline.GATILHOS_MOVIMENTO)
    for movimento in timeline.GATILHOS_MOVIMENTO:
        pecas.append(_peca(f"movimento.{ids_movimento[movimento]}", "efeito", _rotulo(movimento),
                            f"movimento.gatilho={movimento}", [
                                _estado("acao", "Ação", _animacao(
                                    "acao", _rotulo(movimento), movimento, loop=False, fps=14,
                                    quadros=6, ancora="ponto do evento", camada=15,
                                    segue="lutador", tamanho="1,0 do corpo"))], ["movimento.generico"]))
    eventos = _eventos_da_timeline()
    ids_evento = _ids_por_nome(eventos)
    for evento in eventos:
        if evento in SEM_ANIMACAO:
            continue
        pecas.append(_peca(f"evento.{ids_evento[evento]}", "efeito", _rotulo(evento),
                            f"evento={evento}", [
                                _estado("disparo", "Disparo", _animacao(
                                    "disparo", _rotulo(evento), evento, loop=False, fps=14,
                                    quadros=6, ancora="ponto do evento", camada=70,
                                    segue="fixo no mundo", tamanho="0,8 do corpo"))],
                            ["evento.generico"]))

    pecas.sort(key=lambda peca: peca["id"])
    return {
        "versao": VERSAO,
        "descricao": "Catalogo de animacoes derivado das definicoes do Neural Fights.",
        "sobrescrita_opcional": {
            "arma": "Uma arma do banco pode ganhar arte propria em arma.<id_da_arma>; se faltar, usa estilo, tipo e generica.",
            "personagem": "Um personagem pode ganhar arte propria em lutador.<id_do_personagem>; se faltar, usa classe e generica.",
        },
        "pecas": pecas,
        "sem_animacao": [
            {"id": evento, "origem": f"evento={evento}", "motivo": motivo}
            for evento, motivo in sorted(SEM_ANIMACAO.items()) if evento in eventos
        ],
    }


def bytes_catalogo(catalogo: dict) -> bytes:
    return (json.dumps(catalogo, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def validar_catalogo(catalogo: dict) -> list[str]:
    """Retorna problemas que impediriam o palco de saber quando tocar."""
    problemas = []
    conhecidos = gatilhos_do_jogo()
    ids = set()
    for peca in catalogo.get("pecas", []):
        ident = peca.get("id")
        if not ident or ident in ids:
            problemas.append(f"id de peca invalido ou duplicado: {ident!r}")
        ids.add(ident)
        for estado in peca.get("estados", []):
            for animacao in estado.get("animacoes", []):
                gatilho = animacao.get("gatilho")
                if gatilho not in conhecidos:
                    problemas.append(f"gatilho orfao {gatilho!r} em {ident}")
    animados = {animacao["gatilho"] for peca in catalogo.get("pecas", [])
                for estado in peca.get("estados", [])
                for animacao in estado.get("animacoes", [])}
    cobertos = animados | {item["id"] for item in catalogo.get("sem_animacao", [])}
    for evento in _eventos_da_timeline():
        if evento not in cobertos:
            problemas.append(f"evento sem animacao ou motivo: {evento}")
    for estado in timeline.FLAGS:
        if estado not in cobertos:
            problemas.append(f"estado sem animacao ou motivo: {estado}")
    return problemas


def gerar_documentacao(catalogo: dict) -> str:
    resumo = {}
    for peca in catalogo["pecas"]:
        grupo = resumo.setdefault(peca["grupo"], [0, 0, 0])
        grupo[0] += 1
        grupo[1] += len(peca["estados"])
        grupo[2] += sum(len(estado["animacoes"]) for estado in peca["estados"])
    linhas = [
        "# Catálogo de animações", "",
        "Gerado por `python -m neural_fights.tools.catalogo_animacoes`. Não edite esta lista à mão.",
        "", "O catálogo traz a hierarquia estável do jogo. Armas e personagens do banco usam a "
        "arte do estilo/classe; só recebem uma sobrescrita quando o Adrian decidir criar uma.",
        "", "## Resumo", "",
        "| Grupo | Peças | Estados | Animações |",
        "| --- | ---: | ---: | ---: |",
    ]
    for grupo, (pecas, estados, animacoes) in sorted(resumo.items()):
        linhas.append(f"| {grupo} | {pecas} | {estados} | {animacoes} |")
    for grupo in sorted(resumo):
        linhas.extend([
            "", f"## {grupo}", "",
            "| Peça | Estado | Animação | Quando toca | Loop | Tamanho / âncora |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        for peca in (peca for peca in catalogo["pecas"] if peca["grupo"] == grupo):
            for estado in peca["estados"]:
                for animacao in estado["animacoes"]:
                    intervalo = animacao.get("intervalo_ocioso")
                    quando = f"`{animacao['gatilho']}`"
                    if intervalo:
                        quando += f"; a cada {intervalo['min_s']}–{intervalo['max_s']} s"
                    linhas.append("| {} | {} | {} | {} | {} | {} / {} |".format(
                        peca["rotulo"], estado["rotulo"], animacao["rotulo"], quando,
                        "sim" if animacao["loop"] else "não", animacao["tamanho_padrao"],
                        animacao["ancora_padrao"]))
    linhas.extend(["", "## Sem animação", "",
                    "Estes sinais existem no jogo, mas não pedem arte no palco:", ""])
    for item in catalogo["sem_animacao"]:
        linhas.append(f"- `{item['id']}`: {item['motivo']}.")
    linhas.extend([
        "", "## Como acrescentar uma animação nova", "",
        "1. Acrescente o tipo, estilo, classe, skill, elemento ou estado na definição do jogo.",
        "2. Gere o catálogo. A nova peça aparece com a herança de arte (estilo, tipo e genérica).",
        "3. No Ateliê, escolha a peça, o estado e a animação; envie a folha, fatie e ajuste a âncora.",
        "4. Uma arma ou personagem específico só ganha arte própria como sobrescrita opcional; não entra nesta lista.",
        "5. Se o sinal novo não deve desenhar nada, registre o motivo em `sem_animacao` no gerador.",
        "",
    ])
    return "\n".join(linhas)


def gravar(caminho: str | Path = PADRAO, *, documento: str | Path | None = DOCUMENTO,
           arquivo_armas: str | Path | None = None,
           arquivo_personagens: str | Path | None = None) -> dict:
    """Grava o catalogo sem tocar nos ajustes do Atelie."""
    catalogo = gerar_catalogo(arquivo_armas=arquivo_armas, arquivo_personagens=arquivo_personagens)
    problemas = validar_catalogo(catalogo)
    if problemas:
        raise ValueError("\n".join(problemas))
    Path(caminho).write_bytes(bytes_catalogo(catalogo))
    if documento is not None:
        Path(documento).write_text(gerar_documentacao(catalogo), encoding="utf-8", newline="\n")
    return catalogo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera o catalogo de animacoes do palco.")
    parser.add_argument("--saida", type=Path, default=PADRAO, help="arquivo JSON de saida")
    parser.add_argument("--verificar", action="store_true", help="falha se a saida estiver desatualizada")
    args = parser.parse_args(argv)
    catalogo = gerar_catalogo()
    problemas = validar_catalogo(catalogo)
    if problemas:
        parser.error("; ".join(problemas))
    conteudo = bytes_catalogo(catalogo)
    if args.verificar:
        atual = args.saida.read_bytes() if args.saida.is_file() else b""
        if atual != conteudo:
            print(f"catalogo desatualizado: {args.saida}")
            return 1
        print(f"catalogo atualizado: {args.saida}")
        return 0
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    args.saida.write_bytes(conteudo)
    if args.saida.resolve() == PADRAO.resolve():
        DOCUMENTO.write_text(gerar_documentacao(catalogo), encoding="utf-8", newline="\n")
    print(f"catalogo gerado: {args.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
