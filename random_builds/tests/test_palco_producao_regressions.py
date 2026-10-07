# -*- coding: utf-8 -*-
"""16G, segunda metade: o duelo de PRODUCAO pelo palco, atras de uma chave.

`config/palco.json -> producao.duelo_celular` ("desligado" | "sem_corrente" |
"todos") decide de onde sai o `final_celular.mp4` do duelo. O que tem de
valer sempre, e por isso esta aqui:

  - a chave vem DESLIGADA no git, e qualquer valor estranho e desligada;
  - "sem_corrente" so manda pelo palco quando NENHUM lutador usa Corrente, e
    arma que o banco nao conhece fica no pygame (nao da para garantir);
  - o B so vai para o lugar do celular depois das guardas (golpes e K.O. no
    mesmo quadro, duracao, nada preto, congelado so depois do K.O., som pela
    regua da publicacao); falha de qualquer tipo = o celular sai pelo pygame
    e nada do B fica no lugar dele;
  - o controller nunca deixa de entregar o duelo por causa do palco;
  - a geracao reserva mais tempo por duelo SO com a chave ligada.
Nada aqui abre o Godot.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from builds.palco import producao
from builds.palco.config import ErroPalco

RAIZ = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------ a chave
def test_chave_vem_desligada_no_git():
    cfg = json.loads((RAIZ / "config" / "palco.json").read_text(encoding="utf-8"))
    assert cfg["producao"]["duelo_celular"] == "desligado"
    assert producao.modo(cfg) == "desligado" and not producao.ligado(cfg)


@pytest.mark.parametrize("valor,esperado", [
    ("sem_corrente", "sem_corrente"), ("todos", "todos"), ("desligado", "desligado"),
    ("ligado", "desligado"), (True, "desligado"), (None, "desligado"), ("", "desligado")])
def test_modo_so_liga_escrito_certo(valor, esperado):
    assert producao.modo({"producao": {"duelo_celular": valor}}) == esperado


def test_modo_sem_bloco_ou_config_ilegivel_e_desligado(monkeypatch):
    assert producao.modo({}) == "desligado"
    assert producao.modo({"producao": "todos"}) == "desligado"

    def ilegivel():
        raise ErroPalco("config/palco.json ilegivel")
    monkeypatch.setattr("builds.palco.config.carregar", ilegivel)
    assert producao.modo() == "desligado" and not producao.ligado()


# ------------------------------------------------------------------ a escolha
TIPOS = {"Lamina": "Reta", "Mangual": "Corrente", "Arco Velho": "Arco"}


def _luta(arma1="Lamina", arma2="Arco Velho"):
    return {"p1": "Ana", "p2": "Bia", "p1_ficha": {"nome_arma": arma1}, "p2_ficha": {"nome_arma": arma2}}


def test_sem_corrente_vai_pelo_palco():
    assert producao.escolher(_luta(), "sem_corrente", TIPOS) == (True, "sem corrente")


@pytest.mark.parametrize("arma1,arma2,quem", [("Mangual", "Lamina", "Ana"), ("Lamina", "Mangual", "Bia")])
def test_com_corrente_fica_no_pygame_e_diz_quem(arma1, arma2, quem):
    vai, motivo = producao.escolher(_luta(arma1, arma2), "sem_corrente", TIPOS)
    assert vai is False and "corrente" in motivo and f"{quem} (Mangual)" in motivo


def test_arma_fora_do_banco_fica_no_pygame():
    vai, motivo = producao.escolher(_luta("Sumiu", "Lamina"), "sem_corrente", TIPOS)
    assert vai is False and "fora do banco" in motivo and "Sumiu" in motivo
    vai, _ = producao.escolher({"p1": "Ana", "p2": "Bia"}, "sem_corrente", TIPOS)
    assert vai is False


def test_todos_e_desligado_nao_olham_arma():
    assert producao.escolher(_luta("Mangual", "Mangual"), "todos", TIPOS)[0] is True
    assert producao.escolher(_luta(), "desligado", TIPOS)[0] is False
    assert producao.escolher(_luta(), "qualquer", TIPOS)[0] is False


# ------------------------------------------------------------------ as guardas
def _medidas_boas(**mudar):
    base = dict(
        medidas_final={"duracao": 28.1, "quadros": 843, "audio": True, "pretos": [],
                       "congelados": [[26.5, None]]},
        eventos={"momentos_a": 40, "momentos_b": 40, "so_no_a": 0, "so_no_b": 0,
                 "ko_a": 24.5, "ko_b": 24.5},
        duracao_a=28.0, hitstop_s=0.1, ko_final=24.6, luta_motivo="",
        luta_trecho={"media_db": -15.0, "calado": 0.0}, inteiro_motivo="")
    base.update(mudar)
    return base


def test_b_medido_igual_ao_a_passa():
    assert producao.conferir(**_medidas_boas()) == []


@pytest.mark.parametrize("mudar,trecho", [
    ({"eventos": {"momentos_a": 40, "so_no_a": 2, "so_no_b": 0, "ko_a": 24.5, "ko_b": 24.5}}, "golpes fora"),
    ({"eventos": {"momentos_a": 40, "so_no_a": 0, "so_no_b": 1, "ko_a": 24.5, "ko_b": 24.5}}, "golpes fora"),
    ({"eventos": {"so_no_a": 0, "so_no_b": 0, "ko_a": 24.5, "ko_b": 24.6}}, "K.O."),
    ({"eventos": {"so_no_a": 0, "so_no_b": 0, "ko_a": 24.5, "ko_b": None}}, "K.O."),
    ({"duracao_a": 27.0}, "duracao"),
    ({"medidas_final": {"duracao": 28.1, "quadros": 843, "audio": True, "pretos": [[0.0, 0.4]],
                        "congelados": []}}, "preto"),
    ({"medidas_final": {"duracao": 28.1, "quadros": 843, "audio": True, "pretos": [],
                        "congelados": [[10.0, 11.0]]}}, "congelada"),
    ({"medidas_final": {"duracao": 28.1, "quadros": 843, "audio": False, "pretos": [], "congelados": []}},
     "faixa de audio"),
    ({"luta_motivo": "media -91 dB"}, "luta esta muda"),
    ({"luta_motivo": None}, "nao consegui medir"),
    ({"inteiro_motivo": "calado em 70%"}, "video esta mudo"),
    ({"inteiro_motivo": None}, "nao consegui medir"),
    ({"luta_trecho": {"media_db": -20.0, "calado": 0.4}}, "calado 40%"),
    ({"luta_trecho": None}, "fracao calada"),
])
def test_cada_guarda_barra_o_b(mudar, trecho):
    problemas = producao.conferir(**_medidas_boas(**mudar))
    assert problemas and any(trecho in p for p in problemas), problemas


def test_congelado_depois_do_ko_e_a_cena_parada_e_nao_barra():
    # medido no A/B da 16G (duelo_00030): a cena para depois do K.O. no A e no B
    assert producao.conferir(**_medidas_boas(medidas_final={
        "duracao": 28.1, "quadros": 843, "audio": True, "pretos": [], "congelados": [[24.6, None]]})) == []
    # sem K.O. (vitoria por tempo) nenhum congelado passa
    assert producao.conferir(**_medidas_boas(ko_final=None, eventos={"so_no_a": 0, "so_no_b": 0}))


def test_duracao_e_a_da_imagem_e_nao_a_do_arquivo():
    # medido no duelo_00091 pelo palco (07/10/2026): 855 quadros (28,5 s) e o
    # arquivo com 28,6 s, porque a faixa de audio passa do ultimo quadro (o A
    # tambem: 840 quadros e 28,1 s). A 1a versao da guarda media o arquivo e
    # barrou um B perfeito.
    medido = {"duracao": 28.6, "quadros": 855, "audio": True, "pretos": [], "congelados": [[27.59, None]]}
    assert producao.conferir(**_medidas_boas(medidas_final=medido, duracao_a=28.0, hitstop_s=0.533,
                                             ko_final=25.0)) == []


def test_duracao_e_a_do_a_mais_o_hitstop_com_folga_de_tres_quadros():
    assert producao.conferir(**_medidas_boas(hitstop_s=0.0, duracao_a=28.0,
                                             medidas_final={"duracao": 28.1, "quadros": 843, "audio": True,
                                                            "pretos": [], "congelados": []})) == []
    assert producao.conferir(**_medidas_boas(hitstop_s=0.0, duracao_a=28.0,
                                             medidas_final={"duracao": 28.2, "quadros": 846, "audio": True,
                                                            "pretos": [], "congelados": []}))


# ------------------------------------------------------------------ a entrega
def _duelo(tmp_path: Path, com_pygame: bool = True) -> Path:
    out = tmp_path / "duelo_00099"
    out.mkdir()
    if com_pygame:
        (out / "final_celular.mp4").write_bytes(b"PYGAME")
        (out / "_segments_celular").mkdir()
        (out / "_segments_celular" / "seg_000.mp4").write_bytes(b"SEG PYGAME")
    return out


def _fake_montar(problemas=None, erro=None):
    def montar(out_dir, fight, edit_plan, **_kw):
        if erro is not None:
            raise erro
        pasta = Path(out_dir) / producao.PASTA
        (pasta / "_segments_celular").mkdir(parents=True)
        (pasta / "_segments_celular" / "seg_000.mp4").write_bytes(b"SEG PALCO")
        (pasta / "final_celular.mp4").write_bytes(b"PALCO")
        (pasta / "palco_celular.mp4").write_bytes(b"CLIPE")
        (pasta / "_palco_celular_trabalho").mkdir()
        (pasta / "_palco_celular_trabalho" / "palco_celular.avi").write_bytes(b"AVI" * 10)
        (pasta / "timeline.gcpf").write_bytes(b"T")
        return {"problemas": list(problemas or []), "medidas": {"duracao": 1.0}, "pasta": pasta}
    return montar


FIGHT = {"luta": _luta()}


@pytest.fixture(autouse=True)
def _sem_diario(monkeypatch):
    chamadas = []
    monkeypatch.setattr(producao, "_diario", lambda *a, **k: chamadas.append((*a, k.get("status", "log"))))
    return chamadas


@pytest.fixture(autouse=True)
def _estado_isolado(monkeypatch, tmp_path):
    arquivo = tmp_path / "_estado" / producao.ESTADO
    arquivo.parent.mkdir()
    monkeypatch.setattr(producao, "_arquivo_estado", lambda: arquivo)
    return arquivo


def test_b_aprovado_vai_para_o_lugar_do_celular(tmp_path, monkeypatch):
    out = _duelo(tmp_path)
    monkeypatch.setattr(producao, "montar_e_conferir", _fake_montar())
    feito = producao.entregar_celular(out, FIGHT, {}, modo_forcado="sem_corrente", tipos=TIPOS)
    assert feito["pelo_palco"] is True
    assert (out / "final_celular.mp4").read_bytes() == b"PALCO"
    assert (out / "_segments_celular" / "seg_000.mp4").read_bytes() == b"SEG PALCO"
    assert not (out / "_segments_celular.antes_do_palco").exists()
    registro = json.loads((out / producao.REGISTRO).read_text(encoding="utf-8"))
    assert registro["pelo_palco"] is True and registro["modo"] == "sem_corrente"
    # o que explica o B fica ao lado (a timeline, o clipe e o plano)
    assert (out / producao.PASTA / "timeline.gcpf").is_file()


@pytest.mark.parametrize("problemas,erro", [
    (["K.O. em outro quadro: A 1 s, B 2 s"], None),
    (None, ErroPalco("o palco falhou: rc 4 (janela minimizada)")),
    (None, RuntimeError("Godot sumiu")),
])
def test_b_reprovado_ou_quebrado_nao_toca_no_celular(tmp_path, monkeypatch, _sem_diario, problemas, erro):
    out = _duelo(tmp_path)
    monkeypatch.setattr(producao, "montar_e_conferir", _fake_montar(problemas, erro))
    feito = producao.entregar_celular(out, FIGHT, {}, modo_forcado="todos", tipos=TIPOS)
    assert feito["pelo_palco"] is False and feito["motivo"].startswith("falhou")
    assert (out / "final_celular.mp4").read_bytes() == b"PYGAME"
    assert (out / "_segments_celular" / "seg_000.mp4").read_bytes() == b"SEG PYGAME"
    # o peso do B nao fica (AVI e mp4s); o motivo fica, no registro e no diario
    assert not list((out / producao.PASTA).glob("**/*.avi")) if (out / producao.PASTA).exists() else True
    assert not list((out / producao.PASTA).glob("*.mp4")) if (out / producao.PASTA).exists() else True
    registro = json.loads((out / producao.REGISTRO).read_text(encoding="utf-8"))
    assert registro["pelo_palco"] is False and "falhou" in registro["motivo"]
    assert _sem_diario, "falha do palco tem de ir ao diario"


def test_com_corrente_nem_monta_o_b(tmp_path, monkeypatch):
    out = _duelo(tmp_path)
    monkeypatch.setattr(producao, "montar_e_conferir",
                        lambda *a, **k: pytest.fail("com corrente no modo sem_corrente nao monta o B"))
    feito = producao.entregar_celular(out, {"luta": _luta("Mangual")}, {}, modo_forcado="sem_corrente",
                                      tipos=TIPOS)
    assert feito["pelo_palco"] is False and "corrente" in feito["motivo"]
    assert (out / "final_celular.mp4").read_bytes() == b"PYGAME"


def test_chave_desligada_nao_monta_nem_registra(tmp_path, monkeypatch):
    out = _duelo(tmp_path)
    monkeypatch.setattr(producao, "montar_e_conferir", lambda *a, **k: pytest.fail("chave desligada"))
    feito = producao.entregar_celular(out, FIGHT, {}, modo_forcado="desligado", tipos=TIPOS)
    assert feito["pelo_palco"] is False and not (out / producao.REGISTRO).exists()


def test_duelo_novo_sem_pygame_recebe_o_b(tmp_path, monkeypatch):
    # duelo novo: o celular do palco vem ANTES de existir um do pygame
    out = _duelo(tmp_path, com_pygame=False)
    monkeypatch.setattr(producao, "montar_e_conferir", _fake_montar())
    assert producao.entregar_celular(out, FIGHT, {}, modo_forcado="todos", tipos=TIPOS)["pelo_palco"]
    assert (out / "final_celular.mp4").read_bytes() == b"PALCO"


# ------------------------------------------------------------------ o controller
class _RendererFalso:
    feitos: list = []

    def __init__(self, render_config, profile, preview):
        self.profile = profile

    def render(self, edit_plan, fight, out_dir, music):
        _RendererFalso.feitos.append(self.profile)
        final = Path(out_dir) / f"final_{self.profile}.mp4"
        final.write_bytes(b"PYGAME")
        return final


def _controller(monkeypatch, tmp_path):
    from builds.pipeline import controller as mod
    ctl = mod.PipelineController.__new__(mod.PipelineController)
    ctl.render_config = {"profiles": {"celular": {}, "normal": {}}}
    ctl.editing_config, ctl.captions = {}, None
    monkeypatch.setattr(ctl, "_musica", lambda engine: None)
    monkeypatch.setattr(mod, "VideoRenderer", _RendererFalso)
    monkeypatch.setattr("builds.publicar.capa.gerar", lambda *a, **k: "capa.png")
    _RendererFalso.feitos = []
    out = tmp_path / "duelo_00100"
    out.mkdir()
    (out / "edit_plan.json").write_text(json.dumps({"total_duration": 1.0, "events": []}), encoding="utf-8")
    return ctl, out


def test_controller_com_chave_desligada_e_o_de_sempre(monkeypatch, tmp_path):
    ctl, out = _controller(monkeypatch, tmp_path)
    (out / producao.REGISTRO).write_text("{}", encoding="utf-8")       # de um palco antigo
    monkeypatch.setattr(producao, "entregar_celular", lambda *a, **k: pytest.fail("chave desligada"))
    monkeypatch.setattr(producao, "modo", lambda cfg=None: "desligado")
    ctl._entregar_duelo(out, {"seed": 1, "luta": _luta()}, preview=False, remontar=False)
    assert _RendererFalso.feitos == ["celular", "normal"]
    assert not (out / producao.REGISTRO).exists(), "o registro antigo mentiria sobre o mp4 novo"


def test_controller_pelo_palco_so_renderiza_o_normal(monkeypatch, tmp_path):
    ctl, out = _controller(monkeypatch, tmp_path)
    monkeypatch.setattr(producao, "modo", lambda cfg=None: "todos")
    monkeypatch.setattr(producao, "entregar_celular", lambda *a, **k: {"pelo_palco": True})
    ctl._entregar_duelo(out, {"seed": 1, "luta": _luta()}, preview=False, remontar=False)
    assert _RendererFalso.feitos == ["normal"]


@pytest.mark.parametrize("entrega", [
    lambda *a, **k: {"pelo_palco": False, "motivo": "falhou: rc 4"},
    lambda *a, **k: (_ for _ in ()).throw(RuntimeError("bug no palco")),
])
def test_controller_palco_falhou_o_celular_sai_pelo_pygame(monkeypatch, tmp_path, entrega):
    ctl, out = _controller(monkeypatch, tmp_path)
    monkeypatch.setattr(producao, "modo", lambda cfg=None: "todos")
    monkeypatch.setattr(producao, "entregar_celular", entrega)
    ctl._entregar_duelo(out, {"seed": 1, "luta": _luta()}, preview=False, remontar=False)
    assert _RendererFalso.feitos == ["celular", "normal"]
    assert (out / "final_celular.mp4").read_bytes() == b"PYGAME"


def test_controller_previa_nunca_vai_pelo_palco(monkeypatch, tmp_path):
    ctl, out = _controller(monkeypatch, tmp_path)
    monkeypatch.setattr(producao, "modo", lambda cfg=None: "todos")
    monkeypatch.setattr(producao, "entregar_celular", lambda *a, **k: pytest.fail("previa"))
    ctl._entregar_duelo(out, {"seed": 1, "luta": _luta()}, preview=True, remontar=False)
    assert _RendererFalso.feitos == ["celular", "normal"]


# ------------------------------------------------------------------ a reserva
def test_reserva_do_duelo_so_cresce_com_a_chave_ligada():
    from builds.pipeline import noite
    cfg = {"minutos_por_duelo": 5, "minutos_por_duelo_palco": 8}
    assert noite.minutos_por_duelo(cfg, palco_ligado=False) == 5
    assert noite.minutos_por_duelo(cfg, palco_ligado=True) == 8
    assert noite.minutos_por_duelo({"minutos_por_duelo": 5}, palco_ligado=True) == 5
    # nunca MENOS que o duelo do pygame
    assert noite.minutos_por_duelo({"minutos_por_duelo": 5, "minutos_por_duelo_palco": 3},
                                   palco_ligado=True) == 5


def test_reserva_le_a_chave_do_palco(monkeypatch):
    from builds.pipeline import noite
    cfg = {"minutos_por_duelo": 5, "minutos_por_duelo_palco": 8}
    monkeypatch.setattr(producao, "modo", lambda cfg=None: "sem_corrente")
    assert noite.minutos_por_duelo(cfg) == 8
    monkeypatch.setattr(producao, "modo", lambda cfg=None: "desligado")
    assert noite.minutos_por_duelo(cfg) == 5


def test_geracao_json_tem_a_reserva_do_palco():
    cfg = json.loads((RAIZ / "config" / "geracao.json").read_text(encoding="utf-8"))
    assert float(cfg["minutos_por_duelo_palco"]) > float(cfg["minutos_por_duelo"])


# ------------------------------------------------------------ falhas seguidas
def _falhar(tmp_path, monkeypatch, nome: str, erro=None):
    out = tmp_path / nome
    out.mkdir()
    monkeypatch.setattr(producao, "montar_e_conferir",
                        _fake_montar(erro=erro or ErroPalco("Godot nao encontrado em X")))
    return producao.entregar_celular(out, FIGHT, {}, modo_forcado="todos", tipos=TIPOS)


def _erros(chamadas):
    return [c for c in chamadas if c[-1] == "erro"]


def test_tres_falhas_seguidas_avisam_uma_vez_com_o_motivo(tmp_path, monkeypatch, _sem_diario, _estado_isolado):
    for k in range(2):
        _falhar(tmp_path, monkeypatch, f"duelo_0000{k}")
    assert not _erros(_sem_diario), "duas falhas ainda sao silenciosas (log)"
    _falhar(tmp_path, monkeypatch, "duelo_00002")
    erros = _erros(_sem_diario)
    assert len(erros) == 1 and "3 duelos seguidos" in erros[0][0] and "Godot nao encontrado" in erros[0][0]
    for k in range(3, 6):                       # o bot nao e avisado a cada duelo
        _falhar(tmp_path, monkeypatch, f"duelo_0000{k}")
    assert len(_erros(_sem_diario)) == 1
    estado = json.loads(_estado_isolado.read_text(encoding="utf-8"))
    assert estado["falhas_seguidas"] == 6 and estado["avisado"] is True


def test_duelo_que_passa_zera_a_conta_e_diz_que_voltou(tmp_path, monkeypatch, _sem_diario, _estado_isolado):
    for k in range(3):
        _falhar(tmp_path, monkeypatch, f"duelo_0000{k}")
    out = _duelo(tmp_path)
    monkeypatch.setattr(producao, "montar_e_conferir", _fake_montar())
    assert producao.entregar_celular(out, FIGHT, {}, modo_forcado="todos", tipos=TIPOS)["pelo_palco"]
    assert json.loads(_estado_isolado.read_text(encoding="utf-8"))["falhas_seguidas"] == 0
    assert any(c[-1] == "ok" and "voltou" in c[0] for c in _sem_diario)
    # e a proxima sequencia avisa de novo
    for k in range(3, 6):
        _falhar(tmp_path, monkeypatch, f"duelo_0000{k}")
    assert len(_erros(_sem_diario)) == 2


def test_falha_sem_aviso_anterior_e_sucesso_nao_dizem_nada(tmp_path, monkeypatch, _sem_diario, _estado_isolado):
    _falhar(tmp_path, monkeypatch, "duelo_00000")
    out = _duelo(tmp_path)
    monkeypatch.setattr(producao, "montar_e_conferir", _fake_montar())
    producao.entregar_celular(out, FIGHT, {}, modo_forcado="todos", tipos=TIPOS)
    assert not any(c[-1] in ("ok", "erro") for c in _sem_diario)


def test_corrente_nao_conta_como_falha(tmp_path, monkeypatch, _estado_isolado):
    for k in range(4):
        out = tmp_path / f"duelo_c{k}"
        out.mkdir()
        producao.entregar_celular(out, {"luta": _luta("Mangual")}, {}, modo_forcado="sem_corrente", tipos=TIPOS)
    assert not _estado_isolado.exists() or \
        not json.loads(_estado_isolado.read_text(encoding="utf-8")).get("falhas_seguidas")


def test_o_limite_vem_do_config():
    assert json.loads((RAIZ / "config" / "palco.json").read_text(encoding="utf-8"))[
        "producao"]["falhas_para_avisar"] == producao.FALHAS_PARA_AVISAR == 3


# ------------------------------------------------------------ restos e Godot ausente
def test_limpar_resto_apaga_registro_e_pasta(tmp_path):
    out = _duelo(tmp_path)
    (out / producao.PASTA).mkdir()
    (out / producao.PASTA / "timeline.gcpf").write_bytes(b"T")
    (out / producao.REGISTRO).write_text("{}", encoding="utf-8")
    producao.limpar_resto(out)
    assert not (out / producao.PASTA).exists() and not (out / producao.REGISTRO).exists()
    assert (out / "final_celular.mp4").read_bytes() == b"PYGAME"


def test_controller_com_chave_desligada_nao_deixa_pasta_orfa(monkeypatch, tmp_path):
    ctl, out = _controller(monkeypatch, tmp_path)
    (out / producao.PASTA).mkdir()
    (out / producao.PASTA / "palco_celular.mp4").write_bytes(b"CLIPE")
    monkeypatch.setattr(producao, "modo", lambda cfg=None: "desligado")
    ctl._entregar_duelo(out, {"seed": 1, "luta": _luta()}, preview=False, remontar=False)
    assert not (out / producao.PASTA).exists()


def test_com_corrente_apaga_o_palco_de_antes(tmp_path):
    out = _duelo(tmp_path)
    (out / producao.PASTA).mkdir()
    producao.entregar_celular(out, {"luta": _luta("Mangual")}, {}, modo_forcado="sem_corrente", tipos=TIPOS)
    assert not (out / producao.PASTA).exists()


def test_godot_ausente_falha_antes_de_re_simular(tmp_path, monkeypatch):
    from builds.palco import edicao
    monkeypatch.setattr(edicao, "montar_sobre_o_palco",
                        lambda *a, **k: pytest.fail("re-simulou com o Godot ausente"))
    cfg = json.loads((RAIZ / "config" / "palco.json").read_text(encoding="utf-8"))
    cfg["godot"] = str(tmp_path / "nao_existe" / "Godot_console.exe")
    monkeypatch.delenv("NF_GODOT", raising=False)
    with pytest.raises(ErroPalco, match="Godot nao encontrado"):
        producao.montar_e_conferir(_duelo(tmp_path), FIGHT, {}, cfg=cfg)


# ------------------------------------------------------------ nomes no veredito
def _plano_com_veredito(duracao=28.0, de=26.8):
    return {"total_duration": duracao, "events": [{"type": "gameplay", "duration": duracao,
                                                    "veredito": {"de": de, "vencedor": "Ana"}}]}


def test_nomes_somem_no_quadro_do_veredito_do_b():
    from builds.palco import edicao
    # B com 856 quadros (A 28,0 s + 16 de hitstop): o veredito fica 1,2 s antes
    # do fim, em 27,333 s (o quadro 820); arredondado para BAIXO, o nome some
    # um quadro antes, nunca depois
    assert edicao.quadro_do_veredito(_plano_com_veredito(), 856) == 819
    # e e o mesmo instante que a edicao do B poe no plano
    plano_b, _ = edicao.edicao_sobre_o_palco(
        {**_plano_com_veredito(), "events": [{**_plano_com_veredito()["events"][0], "asset": {"path": "a"},
                                              "luta": {"clipes": {"celular": {"path": "a"}}}}]},
        {"luta": {}}, clipe="b.mp4", duracao=856 / 30, relogio=edicao.Relogio(), perfil="celular")
    assert int(plano_b["events"][0]["veredito"]["de"] * 30 + 1e-6) == 819
    assert edicao.quadro_do_veredito({"events": [{"type": "gameplay", "duration": 5.0}]}, 150) is None
    assert edicao.quadro_do_veredito({"events": []}, 150) is None


def test_nome_na_cor_do_lutador_e_anel_na_cor_do_lado():
    from builds.palco import edicao
    doc = {"lutadores": [{"slot": "p1", "cor": 0xCC00AD, "cor_lado": 0x3498DB},
                         {"slot": "p2", "cor": 0x86FFF9, "cor_lado": 0xE74C3C}]}
    edicao.nomes_na_cor_do_lutador(doc)
    assert [l["cor_nome"] for l in doc["lutadores"]] == [0xCC00AD, 0x86FFF9]
    assert [l["cor_lado"] for l in doc["lutadores"]] == [0x3498DB, 0xE74C3C]


def test_palco_gd_le_os_dois_campos_e_relata():
    gd = (RAIZ.parent / "palco" / "nucleo" / "palco.gd").read_text(encoding="utf-8")
    assert 'job.get("nomes_ate_quadro", -1)' in gd
    assert "lb.visible = not oculto and (nomes_ate < 0 or quadro < nomes_ate)" in gd
    assert '"nomes_ate_quadro": nomes_ate' in gd
    assert 'c.get("cor_nome", c.get("cor_lado"' in gd


@pytest.mark.skipif(__import__("builds.palco.config", fromlist=["x"]).godot_disponivel() is None,
                    reason="Godot nao encontrado")
@pytest.mark.skipif(25 <= __import__("time").localtime().tm_min < 55,
                    reason="render so fora de :25-:55 (janela das postagens da grade)")
def test_render_esconde_os_nomes_e_o_relatorio_confirma(tmp_path):
    from builds.palco import render, sintetica
    tl = tmp_path / "s.json"
    tl.write_text(json.dumps(sintetica.timeline_sintetica(2.0)), encoding="utf-8")
    resumo = render.renderizar(tl, tmp_path / "s.mp4", nomes_ate_quadro=30)
    assert resumo["ok"] and resumo["nomes_ate_quadro"] == 30
