"""16G, a segunda metade: o duelo de PRODUCAO pelo palco, atras de uma chave.

`config/palco.json -> producao.duelo_celular` decide de onde sai o
`final_celular.mp4` que o catalogo e a publicacao leem:

    "desligado"     o pygame, como sempre (o PADRAO; chave ilegivel = isto);
    "sem_corrente"  pelo palco SO se nenhum dos dois lutadores usa arma do tipo
                    Corrente (a corrente nova ainda nao tem arte; decisao
                    pendente no Grimorio `builds/duelo-palco-sem-corrente`);
    "todos"         todo duelo pelo palco.

So o perfil `celular` (110 de 110 publicacoes de duelo sao celular; o palco
so desenha 9:16). O `final_normal.mp4` continua no pygame.

O B e o MESMO video do A/B da 16G (`edicao.montar_sobre_o_palco`): a luta
re-simulada pela seed, o palco desenha, a edicao do duelo (HUD, identidade,
callouts, veredito, som da luta, musica) vai por cima. Ele e montado numa
pasta de trabalho (`<duelo>/palco/`) e so vai para o lugar do
`final_celular.mp4` (e do `_segments_celular/`, que a guarda da luta muda
mede) depois de passar nas guardas abaixo. Qualquer falha -> o celular sai
pelo pygame, como hoje, e o motivo fica em `<duelo>/palco_celular.json` e no
diario. O duelo NUNCA deixa de sair por causa do palco.

Guardas (medidas no arquivo, nunca presumidas):
  - a luta re-simulada bate com o fight.json (vencedor e duracao);
  - o mp4 do palco passou na conferencia do render (quadros, faixa de audio,
    volume, nenhum quadro liso, hitstop Python = Godot);
  - o gameplay composto (HUD/callouts) nao caiu no transcode simples;
  - todo momento de golpe do A existe no B no mesmo quadro (e vice-versa) e o
    K.O. cai no mesmo quadro;
  - duracao: B = A + o hitstop (decisao `hitstop`), com folga de 3 quadros;
  - nenhum trecho preto; congelado so DEPOIS do K.O. (a cena para; o A
    tambem para);
  - o trecho de luta (`_segments_celular/seg_000.mp4`) e o arquivo inteiro
    passam pela MESMA regua da publicacao (`publicar.audio.medir`), e o
    trecho fica calado no maximo `limite_calado` do tempo.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from .config import ErroPalco

MODOS = ("desligado", "sem_corrente", "todos")
PADRAO = "desligado"
TIPO_CORRENTE = "Corrente"
PERFIL = "celular"
PASTA = "palco"
REGISTRO = "palco_celular.json"
FPS = 30


# ------------------------------------------------------------------ a chave
def _cfg_producao(cfg: dict | None = None) -> dict:
    if cfg is None:
        from . import config
        try:
            cfg = config.carregar()
        except ErroPalco:
            return {}
    bloco = cfg.get("producao") if isinstance(cfg, dict) else None
    return bloco if isinstance(bloco, dict) else {}


def modo(cfg: dict | None = None) -> str:
    """O modo da chave. Qualquer coisa fora de MODOS (ou config ilegivel) e
    `desligado`: a chave so liga escrita certa."""
    valor = _cfg_producao(cfg).get("duelo_celular", PADRAO)
    return valor if valor in MODOS else PADRAO


def ligado(cfg: dict | None = None) -> bool:
    return modo(cfg) != PADRAO


def _tipos_das_armas() -> dict[str, str]:
    from ..tournament.runner import nf
    armas, _ = nf.database.carregar_database()
    return {a.get("nome"): a.get("tipo") for a in armas or [] if isinstance(a, dict)}


def armas_da_luta(luta: dict, tipos: dict[str, str] | None = None) -> dict[str, tuple]:
    """{lutador: (arma, tipo)} pela ficha gravada no fight.json e o tipo do banco
    vivo. Tipo None = arma que o banco nao conhece."""
    tipos = _tipos_das_armas() if tipos is None else tipos
    saida = {}
    for lado in ("p1", "p2"):
        ficha = luta.get(f"{lado}_ficha") or {}
        arma = ficha.get("nome_arma")
        saida[luta.get(lado) or lado] = (arma, tipos.get(arma) if arma else None)
    return saida


def escolher(luta: dict, modo_atual: str, tipos: dict[str, str] | None = None) -> tuple[bool, str]:
    """(sai pelo palco?, por que). So `sem_corrente` olha as armas."""
    if modo_atual not in MODOS or modo_atual == PADRAO:
        return False, "chave desligada"
    if modo_atual == "todos":
        return True, "chave em todos"
    armas = armas_da_luta(luta, tipos)
    desconhecidas = [f"{quem} ({arma})" for quem, (arma, tipo) in armas.items() if not tipo]
    if desconhecidas:
        # sem saber o tipo, nao da para garantir que nao e corrente
        return False, "arma fora do banco: " + ", ".join(desconhecidas)
    com_corrente = [f"{quem} ({arma})" for quem, (arma, tipo) in armas.items() if tipo == TIPO_CORRENTE]
    if com_corrente:
        return False, "corrente: " + ", ".join(com_corrente)
    return True, "sem corrente"


# ------------------------------------------------------------------ guardas
def conferir(*, medidas_final: dict, eventos: dict, duracao_a: float, hitstop_s: float,
             ko_final: float | None, luta_motivo, luta_trecho: dict | None, inteiro_motivo,
             limite_calado: float = 0.25, folga_quadros: int = 3) -> list[str]:
    """Os problemas do B (lista vazia = pode ir para o lugar do celular).

    Pura: recebe o que foi medido. `luta_motivo`/`inteiro_motivo` sao as
    respostas da `publicar.audio.medir` ("" = tem som, texto = mudo, None =
    nao mediu, que AQUI barra: na producao "nao sei" fica no pygame)."""
    problemas = []
    # golpes e K.O. no mesmo quadro
    if eventos.get("so_no_a") or eventos.get("so_no_b"):
        problemas.append(f"golpes fora do quadro: {eventos.get('so_no_a')} so no A, "
                         f"{eventos.get('so_no_b')} so no B (de {eventos.get('momentos_a')})")
    ko_a, ko_b = eventos.get("ko_a"), eventos.get("ko_b")
    if ko_a is not None and (ko_b is None or abs(float(ko_a) - float(ko_b)) > 1.0 / FPS + 1e-6):
        problemas.append(f"K.O. em outro quadro: A {ko_a} s, B {ko_b} s")
    # duracao: a da IMAGEM (quadros / 30). A do arquivo e a da faixa mais
    # longa, e a mixagem deixa o audio ~0,1 s alem do ultimo quadro (o A
    # tambem: duelo_00091 com 840 quadros = 28,0 s e arquivo de 28,1 s).
    quadros = int(medidas_final.get("quadros") or 0)
    dur_b = quadros / FPS if quadros else float(medidas_final.get("duracao") or 0.0)
    esperado = float(duracao_a) + float(hitstop_s)
    if abs(dur_b - esperado) > folga_quadros / FPS + 1e-6:
        problemas.append(f"duracao {dur_b:.3f} s ({quadros} quadros), esperado {esperado:.3f} s "
                         f"(A {duracao_a} + hitstop {hitstop_s})")
    # imagem
    pretos = medidas_final.get("pretos") or []
    if pretos:
        problemas.append(f"trecho preto: {pretos}")
    for inicio, _fim in medidas_final.get("congelados") or []:
        if ko_final is None or float(inicio) < float(ko_final) - 1.0 / FPS:
            problemas.append(f"imagem congelada em {inicio} s, antes do K.O. ({ko_final})")
    # som, pela regua da publicacao
    if not medidas_final.get("audio"):
        problemas.append("o final nao tem faixa de audio")
    if luta_motivo is None:
        problemas.append("nao consegui medir o som do trecho de luta")
    elif luta_motivo:
        problemas.append(f"a luta esta muda ({luta_motivo})")
    if inteiro_motivo is None:
        problemas.append("nao consegui medir o som do video inteiro")
    elif inteiro_motivo:
        problemas.append(f"o video esta mudo ({inteiro_motivo})")
    calado = (luta_trecho or {}).get("calado")
    if calado is None:
        problemas.append("sem a fracao calada do trecho de luta")
    elif float(calado) > float(limite_calado):
        problemas.append(f"trecho de luta calado {float(calado):.0%} (limite {float(limite_calado):.0%})")
    return problemas


# ------------------------------------------------------------------ troca
def _trocar_no_lugar(pasta_b: Path, out_dir: Path) -> None:
    """O B vai para o lugar do celular: `_segments_celular/` e depois o mp4.

    Os segmentos primeiro: a guarda da publicacao mede o `seg_000` do lado
    do mp4, e o mp4 so aparece quando o trecho dele ja esta la. O mp4 vai
    por `os.replace` (atomico no mesmo disco)."""
    seg_b = pasta_b / f"_segments_{PERFIL}"
    seg_dest = out_dir / f"_segments_{PERFIL}"
    if seg_dest.exists():
        velho = out_dir / f"_segments_{PERFIL}.antes_do_palco"
        shutil.rmtree(velho, ignore_errors=True)
        os.replace(seg_dest, velho)
        shutil.rmtree(velho, ignore_errors=True)
    os.replace(seg_b, seg_dest)
    os.replace(pasta_b / f"final_{PERFIL}.mp4", out_dir / f"final_{PERFIL}.mp4")


def _limpar_falha(pasta_b: Path) -> None:
    """Na falha fica o que explica (jsons, logs, timeline), nao o peso:
    o AVI do Godot (100-260 MB) e os mp4 do B."""
    for avi in pasta_b.glob("**/*.avi"):
        avi.unlink(missing_ok=True)
    for mp4 in pasta_b.glob("*.mp4"):
        mp4.unlink(missing_ok=True)
    shutil.rmtree(pasta_b / f"_segments_{PERFIL}", ignore_errors=True)


def _registrar(out_dir: Path, registro: dict) -> None:
    try:
        (out_dir / REGISTRO).write_text(json.dumps(registro, ensure_ascii=False, indent=1, default=str),
                                        encoding="utf-8")
    except OSError:
        pass


def _diario(detalhe: str, ref: str, dur_s: float | None = None, status: str = "log") -> None:
    # Cada falha e "log": o duelo saiu (pelo pygame) e uma falha solta nao e
    # alerta. O "erro" (que o bot avisa) e so o da sequencia, em
    # `_contar_falha`.
    try:
        from .. import atividade
        atividade.registrar("arena", status, detalhe, "builds", etapa="palco", ref=ref, dur_s=dur_s)
    except Exception:                                          # noqa: BLE001
        pass


# ------------------------------------------------------------ falhas seguidas
# Uma falha do palco e silenciosa por desenho (o celular sai pelo pygame). Mas
# o palco quebrado de vez (Godot sumiu, palco.gd com erro, sessao bloqueada)
# faria TODO duelo sair pelo pygame sem ninguem saber. Com N falhas seguidas o
# bot avisa, UMA vez, com o motivo; um duelo que passa zera a conta.
ESTADO = "palco_producao.json"
FALHAS_PARA_AVISAR = 3


def _arquivo_estado() -> Path:
    from ..contas import runtime_dir
    return Path(runtime_dir()) / ESTADO


def _ler_estado() -> dict:
    try:
        dados = json.loads(_arquivo_estado().read_text(encoding="utf-8"))
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        return {}


def _gravar_estado(estado: dict) -> None:
    try:
        arquivo = _arquivo_estado()
        temporario = arquivo.with_suffix(".tmp")
        temporario.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporario, arquivo)
    except OSError:
        pass


def _contar_falha(motivo: str, ref: str, cfg: dict | None = None) -> dict:
    estado = _ler_estado()
    estado["falhas_seguidas"] = int(estado.get("falhas_seguidas") or 0) + 1
    estado.setdefault("desde", time.strftime("%Y-%m-%dT%H:%M:%S"))
    estado["ultimo_motivo"], estado["ultimo_duelo"] = motivo[:500], ref
    limite = int(_cfg_producao(cfg).get("falhas_para_avisar", FALHAS_PARA_AVISAR))
    if estado["falhas_seguidas"] >= limite and not estado.get("avisado"):
        _diario(f"palco: {estado['falhas_seguidas']} duelos seguidos falharam no palco e sairam pelo "
                f"pygame (desde {estado['desde']}); ultimo {ref}: {motivo[:180]}", ref, status="erro")
        estado["avisado"] = True
    _gravar_estado(estado)
    return estado


def _zerar_falhas(ref: str) -> None:
    estado = _ler_estado()
    if not estado.get("falhas_seguidas"):
        return
    if estado.get("avisado"):
        _diario(f"palco voltou: {ref} saiu pelo palco depois de {estado['falhas_seguidas']} falha(s) seguidas",
                ref, status="ok")
    _gravar_estado({"falhas_seguidas": 0})


def limpar_resto(out_dir: Path) -> None:
    """O que um palco anterior deixou no duelo (`palco_celular.json` e
    `<duelo>/palco/`). Para quando o celular volta a sair pelo pygame: o
    registro mentiria sobre o mp4 e a pasta ficaria orfa."""
    out_dir = Path(out_dir)
    (out_dir / REGISTRO).unlink(missing_ok=True)
    shutil.rmtree(out_dir / PASTA, ignore_errors=True)


def montar_e_conferir(out_dir: Path, fight: dict, edit_plan: dict, *, render_config: dict | None = None,
                      musica: dict | None = None, cfg: dict | None = None) -> dict:
    """Monta o B em `<out_dir>/palco/` e mede. NAO troca nada no lugar.

    Devolve {"problemas": [...], "medidas": {...}, "pasta": Path}. Levanta
    ErroPalco se o B nem chegou a existir."""
    from ..publicar import audio
    from ..pipeline import sonorizar
    from . import config, edicao

    cfg = config.carregar() if cfg is None else cfg
    # Godot e projeto ANTES de re-simular: sem eles a falha e na hora, e nao
    # depois da timeline (medido na conferencia: 5,5 s para descobrir)
    config.godot(cfg)
    config.projeto(cfg)
    out_dir = Path(out_dir)
    pasta_b = out_dir / PASTA
    shutil.rmtree(pasta_b, ignore_errors=True)
    b = edicao.montar_sobre_o_palco(fight, edit_plan, pasta_b, perfil=PERFIL, musica=musica,
                                    render_config=render_config, cfg=cfg, rotulo=out_dir.name)
    final_b = b["final"]
    seg_b = pasta_b / f"_segments_{PERFIL}" / "seg_000.mp4"
    inicio = time.time()
    medidas_final = edicao.medir_video(final_b)
    eventos = edicao.comparar_eventos(fight, b["doc"], b["remap"])
    luta_trecho = sonorizar.medir_trecho(seg_b)
    luta_motivo = audio.medir(seg_b, fracao=False)
    inteiro_motivo = audio.medir(final_b)
    relogio = b["relogio"]
    ko_a = fight["luta"].get("ko_em_clipe")
    ko_final = relogio(ko_a) if ko_a is not None else None
    duracao_a = float(edit_plan.get("total_duration") or 0.0)
    regras = _cfg_producao(cfg)
    problemas = conferir(medidas_final=medidas_final, eventos=eventos, duracao_a=duracao_a,
                         hitstop_s=relogio.extra_s, ko_final=ko_final, luta_motivo=luta_motivo,
                         luta_trecho=luta_trecho, inteiro_motivo=inteiro_motivo,
                         limite_calado=float(regras.get("limite_calado", 0.25)),
                         folga_quadros=int(regras.get("folga_quadros", 3)))
    tempos = dict(b["tempos"])
    tempos["medidas_s"] = round(time.time() - inicio, 1)
    medidas = {"final": medidas_final, "eventos": eventos, "luta": {**(luta_trecho or {}),
                                                                    "regua_da_publicacao": luta_motivo},
               "inteiro_regua_da_publicacao": inteiro_motivo, "duracao_a": duracao_a,
               "hitstop_quadros": sum(relogio.paradas.values()), "hitstop_s": round(relogio.extra_s, 3),
               "ko_final": ko_final, "quadros_do_palco": b["resumo"].get("quadros"),
               "sons_do_palco": b["resumo"].get("sons"), "pecas": b["resumo"].get("pecas"),
               "reservas": b["resumo"].get("reservas"), "tempos": tempos,
               "nomes_ate_quadro": b["resumo"].get("nomes_ate_quadro"),
               "musica": (b["musica"] or {}).get("path")}
    (pasta_b / "medidas.json").write_text(json.dumps(medidas, ensure_ascii=False, indent=1, default=str),
                                          encoding="utf-8")
    return {"problemas": problemas, "medidas": medidas, "pasta": pasta_b}


def entregar_celular(out_dir: Path, fight: dict, edit_plan: dict, *, render_config: dict | None = None,
                     musica: dict | None = None, cfg: dict | None = None, modo_forcado: str | None = None,
                     tipos: dict[str, str] | None = None) -> dict:
    """O `final_celular.mp4` do duelo pelo palco, se a chave mandar e o B passar.

    Nunca levanta: devolve {"pelo_palco": bool, "motivo": str, ...}. Com
    `pelo_palco` False o chamador renderiza o celular pelo pygame, como hoje.
    `modo_forcado` e para a prova (A/B), nunca para a producao."""
    out_dir = Path(out_dir)
    inicio = time.time()
    registro = {"perfil": PERFIL, "em": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        modo_atual = modo_forcado if modo_forcado is not None else modo(cfg)
        registro["modo"] = modo_atual
        if modo_atual == PADRAO:
            # chave desligada: nem registro, o duelo e o de sempre
            return {**registro, "pelo_palco": False, "motivo": "chave desligada"}
        vai, por_que = escolher(fight.get("luta") or {}, modo_atual, tipos)
        registro["escolha"] = por_que
        if not vai:
            registro.update({"pelo_palco": False, "motivo": por_que})
            shutil.rmtree(out_dir / PASTA, ignore_errors=True)       # de um palco anterior
            _registrar(out_dir, registro)
            print(f"[palco] {out_dir.name}: celular pelo pygame ({por_que})", flush=True)
            return registro
        resultado = montar_e_conferir(out_dir, fight, edit_plan, render_config=render_config,
                                      musica=musica, cfg=cfg)
        registro["medidas"] = resultado["medidas"]
        if resultado["problemas"]:
            raise ErroPalco("; ".join(resultado["problemas"]))
        _trocar_no_lugar(resultado["pasta"], out_dir)
        registro.update({"pelo_palco": True, "motivo": por_que, "dur_s": round(time.time() - inicio, 1)})
        _registrar(out_dir, registro)
        _zerar_falhas(out_dir.name)
        print(f"[palco] {out_dir.name}: celular PELO PALCO ({por_que}, {registro['dur_s']} s)", flush=True)
        return registro
    except Exception as erro:                                  # noqa: BLE001
        # O duelo nao para por causa do palco: o celular sai pelo pygame.
        motivo = f"{type(erro).__name__}: {erro}"
        registro.update({"pelo_palco": False, "motivo": f"falhou: {motivo}"[:2000],
                         "dur_s": round(time.time() - inicio, 1)})
        _limpar_falha(out_dir / PASTA)
        _registrar(out_dir, registro)
        print(f"[palco] {out_dir.name}: o palco falhou ({motivo[:300]}); celular pelo pygame", flush=True)
        _diario(f"{out_dir.name}: palco falhou, celular saiu pelo pygame ({motivo[:200]})", out_dir.name,
                registro["dur_s"])
        try:
            _contar_falha(motivo, out_dir.name, cfg)
        except Exception:                                      # noqa: BLE001
            pass
        return registro


__all__ = ["MODOS", "PADRAO", "armas_da_luta", "conferir", "entregar_celular", "escolher", "ligado",
           "limpar_resto", "modo", "montar_e_conferir"]
