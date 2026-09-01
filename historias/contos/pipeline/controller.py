# -*- coding: utf-8 -*-
"""A pipeline da historia, de ponta a ponta.

    gerar   -> o browser abre o ChatGPT/Gemini e conduz a conversa inteira
               (biblia da historia, depois cada parte), sem copiar e colar
    imagens -> uma imagem por cena, em todas as partes, no PicassoIA
    video   -> narracao medida, plano, voz e um mp4 POR PARTE

Uma PARTE e um video. Historia curta e uma serie de uma parte so — o resto
da pipeline nao precisa saber a diferenca.

A ORDEM do video nao e negociavel: a voz e MEDIDA antes de o plano existir,
porque a cena espera a fala. Cronometrar a cena primeiro e espremer a voz
depois foi o bug mais caro do outro projeto.
"""
from __future__ import annotations

import json
from pathlib import Path

import builds.atividade as _rb_atividade
from builds.content import voz as _rb_content_voz
from builds.video import trilha as _rb_video_trilha
from ..imagens import fila
from ..roteiro import modelo as modelo_roteiro
from ..roteiro import roteiro as R
from ..video import renderer as render_mod
from ..video import timeline

RAIZ = Path(__file__).resolve().parents[2]
OUTPUTS = RAIZ / "outputs"
ASSETS = RAIZ / "assets"
CACHE_VOZ = OUTPUTS / "_voz_cache"


def carregar_config(nome: str) -> dict:
    with open(RAIZ / "config" / nome, encoding="utf-8-sig") as fh:
        return json.load(fh)


class Pipeline:
    def __init__(self):
        self.render_config = carregar_config("render.json")
        self.roteiro_config = carregar_config("roteiro.json")

    @property
    def perfis(self) -> tuple:
        ativos = self.render_config.get("perfis_ativos")
        return tuple(ativos or self.render_config["profiles"])

    # ------------------------------------------------------------- roteiro
    def prompt(self, modelo: str | None = None, *, tema: str | None = None,
               cenas: int | None = None, arquivo: str | None = None) -> dict:
        dados = modelo_roteiro.prompt_mestre(modelo, tema=tema, cenas=cenas,
                                             arquivo=arquivo,
                                             config=self.roteiro_config)
        dados["arquivo"] = str(modelo_roteiro.salvar(dados))
        return dados

    def importar(self, texto: str, *, modelo: str = "", tema: str = "",
                 historia_id: str | None = None) -> dict:
        """Resposta do LLM (colada a mao) -> roteiro.json."""
        roteiro = R.parse(texto)
        problemas, erros = R.validar(roteiro, self.roteiro_config)
        if erros:
            return {"ok": False, "problemas": problemas, "erros": erros,
                    "cenas": len(roteiro.get("cenas") or [])}
        caminho = R.salvar(roteiro, historia_id, modelo=modelo, tema=tema,
                           bruto=texto)
        dados = R.carregar(caminho.parent.name)
        return {"ok": True, "historia_id": dados["historia_id"],
                "titulo": dados["titulo"], "cenas": dados["total_cenas"],
                "problemas": problemas, "erros": [], "caminho": str(caminho)}

    def gerar(self, *, provedor: str = "chatgpt", partes: int = 6,
              cenas_por_parte: int = 14, tema: str | None = None,
              headless: bool = False, log=print) -> dict:
        """Automatico: o browser abre o LLM e escreve a serie inteira."""
        from ..roteiro import gerar as gerador
        atividade = _rb_atividade
        atividade.registrar(provedor, "inicio",
                            f"serie de {partes} parte(s)", "historias")
        try:
            resultado = gerador.gerar_serie(
                provedor=provedor, partes=partes,
                cenas_por_parte=cenas_por_parte, tema=tema, headless=headless,
                config=self.roteiro_config, log=log)
        except Exception as exc:
            atividade.registrar(provedor, "erro", str(exc)[:200], "historias")
            raise
        atividade.registrar(provedor, "ok",
                            f"{resultado['historia_id']}: {resultado['partes']} "
                            f"parte(s), {resultado['cenas']} cenas", "historias")
        return resultado

    # ------------------------------------------------------------- imagens
    def imagens(self, historia_id: str, *, limite: int | None = None,
                headless: bool = False, parte: int | None = None,
                log=print) -> dict:
        from ..imagens import worker
        atividade = _rb_atividade
        atividade.registrar("picasso", "inicio", historia_id, "historias")
        try:
            resultado = worker.gerar(historia_id, limite=limite,
                                     headless=headless, parte=parte, log=log)
        except Exception as exc:
            atividade.registrar("picasso", "erro", str(exc)[:200], "historias")
            raise
        atividade.registrar(
            "picasso", "erro" if resultado["erros"] else "ok",
            f"{historia_id}: {resultado['geradas']} gerada(s), "
            f"{resultado['faltam']} pendente(s)"
            + (f"; 1o erro: {resultado['erros'][0][:100]}"
               if resultado["erros"] else ""), "historias")
        return resultado

    # --------------------------------------------------------------- video
    @staticmethod
    def pasta_da_parte(historia_id: str, parte: int) -> Path:
        """Cada parte tem a propria pasta de trabalho.

        Necessario, nao organizacao: `voz_palavras.json` tem nome fixo ao lado
        do wav, entao duas partes na mesma pasta sobrescreveriam a legenda uma
        da outra.
        """
        return OUTPUTS / historia_id / "partes" / f"p{int(parte):02d}"

    def nome_do_video(self, roteiro: dict, perfil: str, parte: int) -> str:
        if not roteiro.get("serie"):
            return f"final_{perfil}.mp4"
        return f"final_{perfil}_p{int(parte):02d}.mp4"

    def render(self, historia_id: str, *, preview: bool = False,
               parte: int | None = None, log=print) -> dict:
        """Renderiza uma parte (ou todas). Um mp4 por parte, por perfil."""
        roteiro = R.carregar(historia_id)
        pasta = OUTPUTS / historia_id
        pasta.mkdir(parents=True, exist_ok=True)
        alvos = ([int(parte)] if parte
                 else [bloco["n"] for bloco in roteiro["partes"]])

        voz_mod = _rb_content_voz
        # A voz sai do ROTEIRO, nao do config: quem narra em primeira pessoa
        # define o timbre. Sem isto, toda historia saia na mesma voz
        # masculina, inclusive as narradas por mulheres.
        from ..roteiro import narrador
        cfg_voz = voz_mod.config(narrador.voz_para(
            roteiro, (self.render_config.get("audio") or {}).get("voz")))
        log(f"[voz] narrador: {cfg_voz.get('narrador', '?')} "
            f"({cfg_voz.get('voz')}, tom {cfg_voz.get('tom', '+0Hz')})")
        taxa = int((self.render_config.get("audio") or {}).get("sample_rate", 44100))
        musica = self._musica(log)
        saida = []
        atividade = _rb_atividade
        atividade.registrar("estudio", "inicio",
                            f"{historia_id}: {len(alvos)} parte(s)", "historias")

        for numero in alvos:
            trabalho = self.pasta_da_parte(historia_id, numero)
            trabalho.mkdir(parents=True, exist_ok=True)
            rotulo = (f"parte {numero}/{len(roteiro['partes'])}"
                      if roteiro.get("serie") else "video")

            # 1) A NARRACAO PRIMEIRO — e, de preferencia, de uma vez so.
            #
            # A leitura continua le a parte inteira numa sintese unica: a
            # entonacao atravessa as cenas em vez de reiniciar a cada uma.
            # Era esse recorte (14 sinteses de ~14 s) que fazia o narrador
            # soar robotico, nao a voz em si. O caminho antigo (medir cena a
            # cena) fica como reserva para quando a leitura continua nao
            # puder acontecer.
            linhas = timeline.linhas_de_narracao(roteiro, numero)
            medidas, leitura = {}, None
            if cfg_voz.get("ativa", True):
                if cfg_voz.get("leitura_continua", True):
                    leitura = voz_mod.narrar_continuo(
                        linhas, trabalho / "voz.wav", cfg_voz, taxa=taxa,
                        cache=CACHE_VOZ, log=log)
                if leitura is None:
                    medidas = voz_mod.medir(linhas, cfg_voz, taxa=taxa,
                                            cache=CACHE_VOZ, log=log)
                    log(f"[voz] {rotulo}: {len(medidas)}/{len(linhas)} "
                        "fala(s) medidas (leitura cena a cena)")

            # 2) O plano: recorte do audio (continua) ou previsao dele.
            plano = timeline.montar(roteiro, medidas,
                                    marcos=(leitura or {}).get("marcos"),
                                    duracao_audio=(leitura or {}).get("duracao"),
                                    config_roteiro=self.roteiro_config,
                                    config_render=self.render_config,
                                    pasta=pasta, parte=numero)
            plano["historia_id"] = historia_id
            self._gravar(trabalho / "edit_plan.json", plano)
            (trabalho / "legendas.srt").write_text(timeline.legenda_srt(plano),
                                                   encoding="utf-8")

            # 3) A voz. Na leitura continua ela JA existe (o plano nasceu
            #    dela); no caminho antigo, e montada agora no relogio do plano.
            voz_wav = palavras = None
            if leitura is not None:
                voz_wav = leitura["wav"]
                palavras = voz_mod.caminho_palavras(voz_wav)
            elif cfg_voz.get("ativa", True):
                voz_wav = voz_mod.montar(timeline.linhas_do_plano(plano),
                                         trabalho / "voz.wav", cfg_voz,
                                         taxa=taxa, cache=CACHE_VOZ, log=log)
                if voz_wav is not None:
                    palavras = voz_mod.caminho_palavras(voz_wav)

            for perfil in self.perfis:
                renderer = render_mod.VideoRenderer(self.render_config, perfil,
                                                    preview)
                final = renderer.render(
                    plano, trabalho, voz=voz_wav, palavras=palavras,
                    musica=musica,
                    out_name=str(pasta / self.nome_do_video(roteiro, perfil,
                                                            numero)))
                saida.append(str(final))
                log(f"[render:{perfil}] {rotulo}: {final} "
                    f"({plano['total_duration']}s)")
        atividade.registrar("estudio", "ok",
                            f"{historia_id}: {len(saida)} video(s)", "historias")
        return {"historia_id": historia_id, "videos": saida,
                "partes": len(alvos)}

    def tudo(self, historia_id: str, *, preview: bool = False,
             headless: bool = False, log=print) -> dict:
        """Imagens que faltam + video de todas as partes."""
        resumo = fila.resumo(historia_id)
        imagens = {"geradas": 0, "faltam": resumo["faltam"], "erros": []}
        if resumo["faltam"]:
            try:
                imagens = self.imagens(historia_id, headless=headless, log=log)
            except Exception as exc:
                log(f"[imagens] nao rodou: {exc}")
                imagens = {"geradas": 0, "faltam": resumo["faltam"],
                           "erros": [str(exc)]}
        video = self.render(historia_id, preview=preview, log=log)
        return {"imagens": imagens, "video": video}

    # -------------------------------------------------------------- estado
    def status(self, historia_id: str) -> dict:
        roteiro = R.carregar(historia_id)
        pasta = OUTPUTS / historia_id
        partes = []
        for bloco in roteiro["partes"]:
            numero = bloco["n"]
            trabalho = self.pasta_da_parte(historia_id, numero)
            videos = {perfil: (pasta / self.nome_do_video(roteiro, perfil, numero))
                      for perfil in self.perfis}
            duracao = None
            plano = trabalho / "edit_plan.json"
            if plano.is_file():
                try:
                    with open(plano, encoding="utf-8-sig") as fh:
                        duracao = json.load(fh).get("total_duration")
                except (OSError, ValueError):
                    duracao = None
            partes.append({
                "parte": numero,
                "titulo": R.titulo_da_parte(roteiro, numero),
                "cenas": len(bloco["cenas"]),
                "imagens": fila.resumo(historia_id, roteiro, numero),
                "voz": (trabalho / "voz.wav").is_file(),
                "videos": {p: c.is_file() for p, c in videos.items()},
                "duracao": duracao,
            })
        resumo = fila.resumo(historia_id, roteiro)
        completo = all(all(p["videos"].values()) for p in partes)
        return {
            "historia_id": historia_id,
            "titulo": roteiro.get("titulo", ""),
            "serie": bool(roteiro.get("serie")),
            "partes": partes,
            "n_partes": len(partes),
            "cenas": roteiro.get("total_cenas", 0),
            "imagens": resumo,
            "videos_prontos": sum(1 for p in partes if all(p["videos"].values())),
            "duracao": sum(p["duracao"] or 0 for p in partes) or None,
            "pasta": str(pasta),
            "proximo_passo": self._proximo_passo(resumo, partes, completo),
        }

    @staticmethod
    def _proximo_passo(resumo: dict, partes: list, completo: bool) -> str:
        if resumo["faltam"]:
            faltando = [p["parte"] for p in partes if p["imagens"]["faltam"]]
            return (f"faltam {resumo['faltam']} imagem(ns) "
                    f"(parte(s) {', '.join(map(str, faltando))}) - "
                    "rode: main.py imagens <id>")
        if not completo:
            pendentes = [p["parte"] for p in partes if not all(p["videos"].values())]
            return (f"imagens prontas - falta o video da(s) parte(s) "
                    f"{', '.join(map(str, pendentes))}: main.py video <id>")
        return f"pronta: {len(partes)} video(s) para publicar"

    def listar(self) -> list:
        saida = []
        for roteiro in R.listar():
            try:
                saida.append(self.status(roteiro["historia_id"]))
            except (OSError, ValueError, KeyError):
                continue
        return saida

    # ------------------------------------------------------------ internos
    def _musica(self, log=print):
        """A trilha sintetizada deste canal (nasce sozinha na 1a vez)."""
        if not (self.render_config.get("audio") or {}).get("trilha_procedural", True):
            return None
        pasta = ASSETS / "music"
        pasta.mkdir(parents=True, exist_ok=True)
        existentes = [p for p in pasta.iterdir()
                      if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".m4a", ".flac")]
        if existentes:
            return existentes[0]
        trilha = _rb_video_trilha
        if not trilha.disponivel():
            return None
        # Semente propria: a trilha do canal de historias nao pode ser a
        # mesma do canal de builds.
        # `trilha()` e a batida do canal de BUILDS (bumbo, caixa, chimbal,
        # 808). Debaixo de um desabafo em primeira pessoa ela vira
        # videoclipe e compete com a fala; `ambiente()` e a cama certa.
        # 16 compassos davam 62 s, repetidos 3,4x numa parte de 210 s — e
        # com LRA de 1,2 LU a repeticao fica obvia. 48 cobrem a parte
        # inteira sem dar a volta.
        caminho = trilha.gravar_wav(pasta / "trilha_historias.wav",
                                    trilha.ambiente(seed=21, compassos=48))
        log(f"[trilha] {caminho.name} (sintetizada em assets/music)")
        return caminho

    @staticmethod
    def _gravar(caminho: Path, dados) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as fh:
            json.dump(dados, fh, ensure_ascii=False, indent=2)
