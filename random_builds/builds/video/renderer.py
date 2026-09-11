"""VideoRenderer: edit_plan.json -> final_celular.mp4 (9:16) e
final_normal.mp4 (16:9).

Cada evento da timeline vira um segmento mp4 normalizado (frames PIL via pipe
para o ffmpeg, ou clipe de reacao real transcodificado em crop-para-preencher
mantendo o audio), depois os segmentos sao concatenados. O renderer nao toma
NENHUMA decisao criativa — so executa o plano, no layout do perfil escolhido.
"""
from __future__ import annotations

import json
import math
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from . import roleta_som, trilha
from ..visualization.draw_common import (fit_font, fit_font_wrap, gradient,
                                         hex_rgb, load_font, stat_bar)

# nao abrir janelas de console para os processos ffmpeg no Windows
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _entrada_de_som(som: Path | None, taxa: int) -> list[str]:
    """A entrada de audio de um clipe silenciado.

    O `anullsrc` existe porque o `concat -c copy` descarta a faixa de
    audio quando um segmento nao tem nenhuma. Ele nao precisa ser
    SILENCIO: quando a direcao sintetizou um som para o evento, e ele
    que entra — mesma posicao, mesmo mapeamento.
    """
    if som is not None and Path(som).is_file():
        return ["-i", str(som)]
    return ["-f", "lavfi", "-i", f"anullsrc=r={taxa}:cl=stereo"]

from . import medidas  # noqa: E402  (depois de NO_WINDOW)


class VideoRenderer:
    def __init__(self, render_config: dict, profile: str = "celular",
                 preview: bool = False):
        prof = render_config["profiles"][profile]
        scale = render_config.get("preview", {}).get("scale", 0.5) if preview else 1.0
        self.profile = profile
        self.horizontal = prof.get("layout") == "horizontal"
        self.width = int(prof["width"] * scale) // 2 * 2
        self.height = int(prof["height"] * scale) // 2 * 2
        base = {k: render_config[k] for k in ("fps", "crf", "preset")}
        if preview:
            base.update({k: v for k, v in render_config.get("preview", {}).items()
                         if k in ("fps", "crf", "preset")})
        self.fps = base["fps"]
        self.crf = base["crf"]
        self.preset = base["preset"]
        self.colors = render_config["colors"]
        self.fonts = render_config["fonts"]
        self.audio_cfg = render_config.get("audio", {})
        self.ref = min(self.width, self.height)   # base para fontes nos 2 layouts
        self._bg_cache: Image.Image | None = None

    # ------------------------------------------------------------------ public
    def render(self, edit_plan: dict, generation: dict, out_dir: Path,
               music_asset: dict | None = None,
               out_name: str | None = None, voz: Path | None = None,
               gancho_b: dict | None = None, palavras: Path | None = None) -> Path:
        """Executa o plano. `voz` e a trilha falada (voz.wav) e `gancho_b` o
        evento alternativo de abertura: quando existe, sai tambem um
        `final_<perfil>_ganchoB.mp4` que so difere no primeiro segmento."""
        seg_dir = out_dir / f"_segments_{self.profile}"
        seg_dir.mkdir(parents=True, exist_ok=True)
        segments: list[Path] = []
        # Camada por cima de toda cena desenhada: avatar do personagem
        # (depois de revelado) e a legenda karaoke da voz.
        self._palavras = self._carregar_palavras(palavras)
        self._avatar_cache: dict[str, Image.Image] = {}

        total = len(edit_plan["events"])
        for i, event in enumerate(edit_plan["events"]):
            seg = seg_dir / f"seg_{i:03d}.mp4"
            # Teste de CAPACIDADE, nao de tipo: qualquer evento que aponte para
            # um arquivo de video no disco entra por aqui (reacao, gameplay, o
            # que vier). Antes isso era um `if type == "reaction"` e por isso
            # nenhum outro tipo conseguia usar video real.
            if self._asset_de_video(event):
                self._transcode_asset(event, seg)
            else:
                self._encode_frames(
                    self._com_overlay(self._frames_for(event, generation, out_dir), event),
                    seg, self._audio_do_evento(event, seg))
            segments.append(seg)
            print(f"[progresso] {self.profile} {i + 1}/{total}", flush=True)

        concat = seg_dir / "concat.mp4"
        self._concat(segments, concat)
        final = out_dir / (out_name or f"final_{self.profile}.mp4")
        musica = Path(music_asset["path"]) if music_asset else None
        self._mix_final(concat, musica, voz, final)
        self.ultimo_gancho_b = None
        if gancho_b and segments:
            # Gancho alternativo (A/B): so o PRIMEIRO segmento muda; o resto
            # do video e a mixagem sao os mesmos. Custa um segmento e um
            # concat, e da o dado que decide qual abertura segura mais.
            seg_b = seg_dir / "seg_000_ganchoB.mp4"
            evento_b = dict(gancho_b)
            evento_b.setdefault("duration", edit_plan["events"][0]["duration"])
            self._encode_frames(
                self._com_overlay(self._frames_for(evento_b, generation, out_dir), evento_b),
                seg_b, self._audio_do_evento(evento_b, seg_b))
            concat_b = seg_dir / "concat_ganchoB.mp4"
            self._concat([seg_b, *segments[1:]], concat_b)
            final_b = final.with_name(f"{final.stem}_ganchoB{final.suffix}")
            self._mix_final(concat_b, musica, voz, final_b)
            self.ultimo_gancho_b = final_b
        return final

    # ------------------------------------------------------------------ ffmpeg
    def _encode_frames(self, frames, out_path: Path, audio: Path | None = None) -> None:
        taxa = self.audio_cfg.get("sample_rate", 44100)
        # Sem trilha o segmento continua nascendo com silencio: o concat exige
        # que TODOS tenham faixa de audio, senao ele descarta a dos outros.
        entrada_audio = (["-i", str(audio)] if audio is not None
                         else ["-f", "lavfi", "-i",
                               f"anullsrc=r={taxa}:cl=stereo"])
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{self.width}x{self.height}", "-r", str(self.fps), "-i", "pipe:",
               *entrada_audio,
               "-shortest", "-c:v", "libx264", "-preset", self.preset,
               "-crf", str(self.crf), "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", str(out_path)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, creationflags=NO_WINDOW)
        try:
            for frame in frames:
                proc.stdin.write(frame.tobytes())
        finally:
            proc.stdin.close()
            proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg falhou no segmento {out_path.name}")

    def _asset_de_video(self, event: dict) -> bool:
        """O evento aponta para um arquivo de VIDEO utilizavel?

        A ausencia da chave `media` continua significando video: e o que
        mantem a doutrina de capacidade valendo para todo asset que existia
        antes de existir imagem (reacao, gameplay, clipe de geracao antiga).
        Uma imagem tem que sair por aqui com False, senao ela iria parar no
        ffmpeg como se fosse filme.
        """
        asset = event.get("asset")
        if not isinstance(asset, dict) or asset.get("synthetic", True):
            return False
        if (asset.get("media") or "video") != "video":
            return False
        caminho = self._caminho_do_asset(event)
        return bool(caminho) and Path(caminho).is_file()

    def _caminho_do_asset(self, event: dict) -> str | None:
        """Caminho do video para ESTE perfil.

        Gameplay e gravado uma vez em paisagem e serve aos dois formatos, mas
        o contrato aceita um arquivo por perfil (`path_celular`/`path_normal`)
        para quando valer a pena gravar enquadramentos diferentes.
        """
        asset = event.get("asset") or {}
        especifico = asset.get(f"path_{self.profile}")
        return especifico or asset.get("path")

    def _fade_da_placa(self, duration: float) -> str:
        """Filtro da placa: entra, fica pouco, sai. Nunca o clipe inteiro.

        Texto parado sobre o personagem durante os 5 s do clipe e exatamente o
        que a secao 15 pede para nao fazer - a informacao passa, o personagem
        fica.
        """
        saida = max(0.9, min(duration - 0.6, 2.6))
        return ("format=rgba,fade=in:st=0.25:d=0.35:alpha=1,"
                f"fade=out:st={saida:.2f}:d=0.4:alpha=1")

    def _placa_png(self, event: dict, out_path: Path) -> Path | None:
        """A placa gravada em disco, para o ffmpeg sobrepor no clipe de video.

        Desenhar com PIL e sobrepor como imagem evita `drawtext`, que no
        Windows exige escapar o caminho da fonte e nao sabe compor emoji.
        """
        img = self._placa_imagem(event)
        if img is None:
            return None
        destino = out_path.with_name(out_path.stem + "_placa.png")
        img.save(destino)
        return destino

    def _placa_imagem(self, event: dict):
        """RGBA do tamanho do quadro com nome e linha de dado, ou None.

        A still compoe esta imagem quadro a quadro em PIL; o clipe de video
        manda a mesma imagem para o ffmpeg. Uma fonte so para os dois: a
        revelacao tem que parecer a mesma, venha de imagem ou de video.
        """
        # O print do comentario nao leva placa: a cortina do terco de baixo
        # cobriria justamente o texto que a tela existe para mostrar. O
        # credito vira uma etiqueta pequena no topo.
        if event.get("type") == "comentario":
            return self._etiqueta_imagem(event)
        if event.get("type") == "reaction":
            return self._etiqueta_imagem(event) if event.get("badge") else None
        placa = event.get("nameplate")
        # Onda 11D: o skill_card da estreia usa a MESMA placa da revelação —
        # nome grande + descrição — sobre o clipe de demonstração.
        if not placa or event.get("type") not in ("identity", "skill_card"):
            return None
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))

        # Cortina de baixo: sem ela, texto claro sobre um clipe claro some.
        altura = int(self.height * 0.34)
        cortina = Image.new("RGBA", (1, altura))
        pixels = cortina.load()
        for y in range(altura):
            pixels[0, y] = (15, 12, 30, int(205 * (y / max(1, altura - 1)) ** 1.6))
        img.alpha_composite(cortina.resize((self.width, altura)),
                            (0, self.height - altura))

        draw = ImageDraw.Draw(img)
        accent = self.colors["accent_weapon"] if event.get("slot") == "weapon" \
            else self.colors["accent_character"]
        if event.get("type") == "skill_card":
            cor_skill = (event.get("skill") or {}).get("cor")
            if cor_skill:
                accent = "#%02x%02x%02x" % tuple(int(c) for c in cor_skill[:3])
        largura = int(self.width * (0.55 if self.horizontal else 0.86))
        titulo_font = fit_font_wrap(placa["titulo"], self.fonts["black"],
                                    largura, int(self.ref * 0.072))
        self._wrapped_center(draw, placa["titulo"], titulo_font,
                             self.height * 0.845, fill=(245, 242, 255),
                             stroke=4, max_width=largura)
        if placa.get("subtitulo"):
            sub_font = fit_font(placa["subtitulo"], self.fonts["bold"],
                                largura, int(self.ref * 0.04))
            draw.text((self.width / 2, self.height * 0.895), placa["subtitulo"],
                      font=sub_font, fill=hex_rgb(accent), anchor="mm",
                      stroke_width=3, stroke_fill=(15, 12, 30))

        return img

    def _etiqueta_imagem(self, event: dict):
        """Pilula pequena no topo: de quem veio o pedido. RGBA, ou None.

        Fica em cima, e nao embaixo como a placa da revelacao, porque o que
        esta sob ela e um print de comentario: qualquer cortina no rodape
        engoliria o texto. Largura pela FONTE, nao fixa, senao um @ longo
        estoura a pilula.
        """
        texto = str(event.get("badge") or "").strip()
        if not texto:
            return None
        img = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        fonte = fit_font(texto, self.fonts["black"],
                         int(self.width * 0.78), int(self.ref * 0.036))
        caixa = draw.textbbox((0, 0), texto, font=fonte)
        largura, altura = caixa[2] - caixa[0], caixa[3] - caixa[1]
        folga_x, folga_y = int(self.ref * 0.03), int(self.ref * 0.022)
        cx, cy = self.width / 2, self.height * 0.085
        draw.rounded_rectangle(
            [cx - largura / 2 - folga_x, cy - altura / 2 - folga_y,
             cx + largura / 2 + folga_x, cy + altura / 2 + folga_y],
            radius=int(altura / 2 + folga_y), fill=(15, 12, 30, 225),
            outline=hex_rgb(self.colors["accent_character"]) + (255,), width=3)
        draw.text((cx, cy), texto, font=fonte,
                  fill=hex_rgb(self.colors["accent_character"]), anchor="mm")
        return img

    def _transcode_asset(self, event: dict, out_path: Path) -> None:
        """Clipe de video real (reacao ou gameplay) normalizado para o perfil.

        `fit: "contain"` encaixa o clipe inteiro sobre o fundo do video (usado
        pelo gameplay no formato vertical, onde recortar 1200x800 em 9:16
        comeria ~62% da largura). O padrao continua sendo crop-para-preencher.
        """
        duration = event["duration"]
        sr = self.audio_cfg.get("sample_rate", 44100)
        caminho = self._caminho_do_asset(event)
        # Onda 9: gameplay com HUD do video e callouts e COMPOSTO quadro a
        # quadro em PIL (o clipe vem sem o HUD do jogo). Qualquer falha cai no
        # transcode simples de sempre — a luta nunca deixa de entrar.
        if event.get("type") == "gameplay" and (event.get("hud") or event.get("callouts")):
            try:
                # O terceiro argumento e o que faltava: o clipe da luta vem
                # do gravador com trilha SILENCIOSA (`anullsrc`), entao ate
                # aqui o unico caminho de som do video passava longe do
                # gameplay — a luta inteira saia sem golpe, magia nem KO.
                self._encode_frames(
                    self._com_overlay(self._gameplay_frames_compostos(event), event),
                    out_path, self._audio_do_evento(event, out_path))
                return
            except Exception as exc:
                print(f"[render] gameplay composto falhou ({exc}); transcode simples",
                      flush=True)
        # Recorte fixo pedido pelo asset (gameplay: apara as faixas vazias que
        # sobram porque a camera fica travada na arena). Vem antes do scale.
        recorte = event.get(f"crop_{self.profile}") or event.get("crop")
        pre = ""
        if recorte and len(recorte) == 4:
            x, y, largura, altura = (int(v) for v in recorte)
            pre = f"crop={largura}:{altura}:{x}:{y},"
        # O clipe do payoff vem com o audio que o site gerou, e ele briga com
        # a trilha do video. Silenciar aqui, e nao no fim, evita ter que baixar
        # o volume da musica so por causa de 8 s.
        mudo = bool(event.get("sem_som"))
        # Clipe silenciado nao precisa virar SILENCIO. Medido antes desta
        # onda: no video de build, 4 segmentos (reacao, luta, payoff e CTA)
        # estavam em -70 LUFS — 25,9 s dos 61,8 s dependiam so da musica.
        # Se a direcao tem um som para este evento, ele entra no lugar do
        # `anullsrc`.
        som = self._audio_do_evento(event, out_path) if mudo else None

        if event.get("fit") == "contain":
            # O que sobra ao redor do clipe e o PROPRIO clipe, coberto,
            # borrado e escurecido — a mesma regra da still (secao 15):
            # barra chapada ao lado de um meme entrega que o video foi
            # montado; o borrado nao.
            vf = (f"{pre}split[bgi][fgi];"
                  f"[bgi]scale={self.width}:{self.height}:"
                  f"force_original_aspect_ratio=increase:flags=bilinear,"
                  f"crop={self.width}:{self.height},gblur=sigma=28,"
                  f"eq=brightness=-0.22:saturation=0.85[bg];"
                  f"[fgi]scale={self.width}:{self.height}:"
                  f"force_original_aspect_ratio=decrease:flags=lanczos[fg];"
                  f"[bg][fg]overlay=(W-w)/2:(H-h)/2,fps={self.fps},setsar=1")
        else:
            vf = (f"{pre}scale={self.width}:{self.height}:"
                  f"force_original_aspect_ratio=increase:flags=lanczos,"
                  f"crop={self.width}:{self.height},fps={self.fps},setsar=1")
        # -ss ANTES do -i: seek rapido, necessario para pegar so os melhores
        # momentos de uma luta longa.
        seek = ["-ss", str(event["start_offset"])] if event.get("start_offset") else []
        saida = ["-c:v", "libx264", "-preset", self.preset, "-crf", str(self.crf),
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", str(sr), "-ac", "2",
                 "-b:a", "128k", str(out_path)]

        # Nome sobre o clipe (secao 15): entra e sai sozinho, sem cobrir o
        # personagem. Sem placa, o caminho continua sendo o -vf simples de
        # sempre - reacao e gameplay nao pagam nada por isto existir.
        placa = self._placa_png(event, out_path)
        if placa is None:
            entrada, filtro, mapas = ["-i", caminho], ["-vf", vf], []
            entrada_muda = ["-i", caminho, *_entrada_de_som(som, sr)]
            filtro_mudo, mapas_mudo = ["-vf", vf], ["-map", "0:v", "-map", "1:a"]
        else:
            complexo = (f"[1:v]{self._fade_da_placa(duration)}[placa];"
                        f"[0:v]{vf}[base];[base][placa]overlay=0:0[v]")
            entrada = ["-i", caminho, "-loop", "1", "-i", str(placa)]
            filtro, mapas = ["-filter_complex", complexo], ["-map", "[v]", "-map", "0:a"]
            entrada_muda = ["-i", caminho, "-loop", "1", "-i", str(placa),
                            *_entrada_de_som(som, sr)]
            filtro_mudo = ["-filter_complex", complexo]
            mapas_mudo = ["-map", "[v]", "-map", "2:a"]

        if mudo:
            entrada, filtro, mapas = entrada_muda, filtro_mudo, mapas_mudo
        cmd = ["ffmpeg", "-y", "-loglevel", "error", *seek, *entrada,
               "-t", str(duration), *filtro, *mapas,
               "-af", f"aresample={sr},apad", "-shortest", *saida]
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW)
        if result.returncode != 0:
            # clipe sem audio? tenta com trilha silenciosa
            cmd_noaudio = ["ffmpeg", "-y", "-loglevel", "error", *seek,
                           *entrada_muda, "-t", str(duration),
                           *filtro_mudo, *mapas_mudo, "-shortest", *saida]
            result = subprocess.run(cmd_noaudio, capture_output=True, text=True, creationflags=NO_WINDOW)
            if result.returncode != 0:
                # nunca derruba o render inteiro por um arquivo ruim
                event["asset"]["synthetic"] = True
                if event.get("type") == "gameplay":
                    fallback = self._gameplay_indisponivel_frames(event)
                elif event.get("type") in ("identity", "nameplate"):
                    # Clipe ilegivel: cai no nameplate, nunca num cartao de
                    # reacao no lugar da revelacao do personagem.
                    fallback = self._nameplate_frames(event)
                elif event.get("type") == "skill_card":
                    fallback = self._skill_card_frames(event)
                else:
                    fallback = self._reaction_frames(event)
                self._encode_frames(fallback, out_path)

    # ------------------------------------------------------ gameplay composto
    def _gameplay_frames_compostos(self, event: dict):
        """Frames do clipe da luta com HUD e callouts desenhados por cima.

        O gameplay chega SEM o HUD do jogo (gravado com --sem-hud): as barras
        de vida sao desenhadas aqui, na tipografia do canal, a partir da serie
        de HP que a gravacao exportou. Os callouts (PARRY!, COMBO x4, K.O.)
        entram no instante do evento, com pop-in e fade — a mesma linguagem
        das rolagens extremas.

        O mp4 e decodificado em rgb24 por pipe, ja no tamanho do perfil; a
        composicao e em PIL e a saida volta pelo `_encode_frames` de sempre.
        """
        caminho = self._caminho_do_asset(event)
        duracao = float(event["duration"])
        total = self._n_frames(duracao)
        fundo = self.colors["bg_bottom"].lstrip("#")
        recorte = event.get(f"crop_{self.profile}") or event.get("crop")
        pre = ""
        if recorte and len(recorte) == 4:
            x, y, largura, altura = (int(v) for v in recorte)
            pre = f"crop={largura}:{altura}:{x}:{y},"
        vf = (f"{pre}scale={self.width}:{self.height}:"
              f"force_original_aspect_ratio=decrease:flags=lanczos,"
              f"pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:color=0x{fundo},"
              f"fps={self.fps},setsar=1")
        # -ss ANTES do -i (seek rapido): a luta no fim do video de build entra
        # so pelo trecho decisivo, com HUD e callouts ja no relogio dele.
        seek = ["-ss", str(event["start_offset"])] if event.get("start_offset") else []
        cmd = ["ffmpeg", "-loglevel", "error", *seek, "-i", str(caminho),
               "-t", str(duracao), "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24",
               "pipe:"]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, creationflags=NO_WINDOW)
        tamanho = self.width * self.height * 3
        hud = self._hud_preparado(event)
        callouts = self._callouts_preparados(event)
        # Onda 15B (duelo): identidade e veredito sao SOBREPOSICAO, nao cena.
        # Ausentes nos outros formatos — o build e a estreia nao mudam.
        identidade = self._identidade_preparada(event)
        veredito = self._veredito_preparado(event)
        ultimo: bytes | None = None
        try:
            for i in range(total):
                raw = proc.stdout.read(tamanho)
                if len(raw) == tamanho:
                    ultimo = raw
                elif ultimo is None:
                    raise RuntimeError("clipe de gameplay vazio ou ilegivel")
                img = Image.frombytes("RGB", (self.width, self.height), ultimo)
                t = i / self.fps
                if hud is not None:
                    self._desenhar_hud(img, hud, t)
                if identidade is not None:
                    self._desenhar_identidade(img, identidade, t)
                for callout in callouts:
                    self._desenhar_callout(img, callout, t)
                if veredito is not None:
                    self._desenhar_veredito(img, veredito, t)
                yield img
        finally:
            try:
                proc.stdout.close()
            except OSError:
                pass
            proc.wait()

    def _hud_preparado(self, event: dict) -> dict | None:
        """Camada estatica (nomes + molduras) e a serie de HP para consulta."""
        hud = event.get("hud") or {}
        serie_bruta = hud.get("serie_hp") or []
        if not serie_bruta:
            return None
        luta = event.get("luta") or {}
        if luta.get("p1_ficha") is not None and luta.get("p2_ficha") is not None:
            cor1, cor2 = self._cores_do_confronto(luta)
        else:
            cor1, cor2 = (0, 217, 255), (233, 69, 96)
        serie = sorted((float(a[0]), float(a[1]), float(a[2])) for a in serie_bruta)

        if self.horizontal:
            largura = int(self.width * 0.30)
            y = int(self.height * 0.055)
            x1 = int(self.width * 0.035)
        else:
            largura = int(self.width * 0.43)
            y = int(self.height * 0.052)
            x1 = int(self.width * 0.04)
        x2 = self.width - x1 - largura
        altura = max(14, int(self.ref * 0.026))
        raio = altura // 2

        camada = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(camada)
        for x, nome, cor, ancora in ((x1, hud.get("p1", ""), cor1, "ls"),
                                     (x2 + largura, hud.get("p2", ""), cor2, "rs")):
            draw.rounded_rectangle([x - 4 if ancora == "ls" else x - largura - 4, y - 4,
                                    x + largura + 4 if ancora == "ls" else x + 4,
                                    y + altura + 4],
                                   radius=raio + 4, fill=(12, 10, 24, 210))
            if hud.get("nomes", True) and nome:
                fonte = fit_font(str(nome), self.fonts["black"], largura,
                                 int(self.ref * 0.036))
                draw.text((x, y - int(self.ref * 0.012)), str(nome), font=fonte,
                          fill=cor, anchor=ancora, stroke_width=3,
                          stroke_fill=(15, 12, 30))
        # Onda 10C: serie do plano (t, rotulo_p1, prog_p1, rotulo_p2, prog_p2).
        serie_plano = sorted(
            (float(a[0]), str(a[1] or ""), float(a[2] or 0.0), str(a[3] or ""), float(a[4] or 0.0))
            for a in (hud.get("serie_plano") or []) if len(a) >= 5
        )
        return {
            "camada": camada,
            "serie": serie,
            "tempos": [a[0] for a in serie],
            "barras": ((x1, y, largura, altura, cor1, "esq"),
                       (x2, y, largura, altura, cor2, "dir")),
            "serie_plano": serie_plano,
            "tempos_plano": [a[0] for a in serie_plano],
            "fonte_plano": fit_font("QUEBRAR GUARDA", self.fonts["black"], largura,
                                    int(self.ref * 0.024)),
        }

    @staticmethod
    def _plano_em(hud: dict, t: float) -> tuple[str, float, str, float]:
        import bisect
        tempos = hud.get("tempos_plano") or []
        if not tempos:
            return "", 0.0, "", 0.0
        indice = bisect.bisect_right(tempos, t) - 1
        amostra = hud["serie_plano"][max(0, indice)]
        return amostra[1], amostra[2], amostra[3], amostra[4]

    @staticmethod
    def _hp_em(hud: dict, t: float) -> tuple[float, float]:
        import bisect
        indice = bisect.bisect_right(hud["tempos"], t) - 1
        amostra = hud["serie"][max(0, indice)]
        return amostra[1], amostra[2]

    def _desenhar_hud(self, img: Image.Image, hud: dict, t: float) -> None:
        img.paste(hud["camada"], (0, 0), hud["camada"])
        draw = ImageDraw.Draw(img)
        hp1, hp2 = self._hp_em(hud, t)
        for (x, y, largura, altura, cor, lado), hp in zip(hud["barras"], (hp1, hp2)):
            raio = altura // 2
            draw.rounded_rectangle([x, y, x + largura, y + altura], radius=raio,
                                   fill=(40, 36, 60))
            pct = max(0.0, min(100.0, float(hp)))
            if pct <= 0:
                continue
            cheio = max(altura, int(largura * pct / 100))
            caixa = ([x, y, x + cheio, y + altura] if lado == "esq"
                     else [x + largura - cheio, y, x + largura, y + altura])
            draw.rounded_rectangle(caixa, radius=raio, fill=cor)
            if pct <= 25:
                # vida critica pisca: o mesmo sinal que o jogo da
                if int(t * 6) % 2 == 0:
                    draw.rounded_rectangle(caixa, radius=raio, outline=(255, 255, 255),
                                           width=3)
        # Onda 10C: o PLANO de cada lado, vivo, sob a barra — o espectador ve
        # a intencao mudar ("PRESSAO" -> "PRA PAREDE" -> "ACABAR").
        if hud.get("tempos_plano"):
            r1, g1, r2, g2 = self._plano_em(hud, t)
            fonte = hud["fonte_plano"]
            for (x, y, largura, altura, cor, lado), rotulo, prog in zip(
                hud["barras"], (r1, r2), (g1, g2)
            ):
                if not rotulo:
                    continue
                yy = y + altura + int(self.ref * 0.008)
                xx = x if lado == "esq" else x + largura
                draw.text((xx, yy), rotulo, font=fonte, fill=(245, 240, 255),
                          anchor="la" if lado == "esq" else "ra",
                          stroke_width=2, stroke_fill=(15, 12, 30))
                # barrinha de progresso do objetivo do plano
                bw = int(largura * 0.35)
                by = yy + int(self.ref * 0.024) + 3
                bx = x if lado == "esq" else x + largura - bw
                draw.rounded_rectangle([bx, by, bx + bw, by + 4], radius=2, fill=(40, 36, 60))
                cheio = int(bw * max(0.0, min(1.0, prog)))
                if cheio > 0:
                    cx0 = bx if lado == "esq" else bx + bw - cheio
                    draw.rounded_rectangle([cx0, by, cx0 + cheio, by + 4], radius=2, fill=cor)

    # ------------------------------------------- duelo: identidade/veredito
    # Estas duas camadas so existem no formato DUELO (Onda 15B). Elas sao a
    # resposta a uma medicao: a curva de retencao de 11/09/2026 mostra o
    # publico caindo de 86% para 60% durante as cenas paradas que existiam
    # para apresentar o lutador. Apresentar SOBRE a luta custa zero segundo.
    def _identidade_preparada(self, event: dict) -> dict | None:
        ident = event.get("identidade")
        if not ident:
            return None
        luta = event.get("luta") or {}
        cor1, cor2 = self._cores_do_confronto(luta) if luta.get("p1_ficha") \
            else ((230, 90, 90), (90, 150, 230))
        # O NOME nao entra aqui: o HUD ja o desenha, na cor do lutador, no
        # video inteiro. Repetir logo abaixo (como saiu no primeiro duelo,
        # 11/09/2026) gasta a unica faixa livre do topo dizendo o que ja
        # esta dito. Esta camada acrescenta o que falta — arma e classe.
        margem = int(self.width * 0.04)
        y = int(self.height * (0.105 if not self.horizontal else 0.155))
        # Cada lado tem METADE da tela, menos a margem e uma calha no meio.
        # Sem esse teto os dois textos se encontram no centro e viram uma
        # linha ilegivel (foi o que saiu no primeiro duelo, 11/09/2026).
        cabe = max(1, self.width // 2 - margem - int(self.width * 0.02))
        lados = []
        for slot, cor, lado in (("p1", cor1, "esq"), ("p2", cor2, "dir")):
            dados = ident.get(slot) or {}
            # "Berserker (Furia)" vira "Berserker": o parenteses e taxonomia
            # do motor, e em 1,5 s de leitura so a primeira palavra chega.
            classe = str(dados.get("classe") or "").split("(")[0].strip()
            texto = " · ".join(p for p in (str(dados.get("arma") or "").strip(),
                                           classe) if p)
            if not texto:
                continue
            lados.append({
                "x": margem if lado == "esq" else self.width - margem,
                "y": y, "cor": cor, "texto": texto,
                "fonte": fit_font(texto, self.fonts["bold"], cabe,
                                  int(self.ref * 0.026)),
                "anchor": "la" if lado == "esq" else "ra",
            })
        if not lados:
            return None
        return {"ate": float(ident.get("ate", 1.5)), "lados": lados}

    def _desenhar_identidade(self, img: Image.Image, ident: dict, t: float) -> None:
        ate = ident["ate"]
        if t > ate:
            return
        # Sem pop-in: a identidade tem que estar LEGIVEL no frame 0, porque
        # e nele que o espectador decide ficar. Só o fim tem fade.
        alfa = 1.0 if t < ate - 0.35 else max(0.0, (ate - t) / 0.35)
        camada = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(camada)
        for lado in ident["lados"]:
            draw.text((lado["x"], lado["y"]), lado["texto"], font=lado["fonte"],
                      fill=lado["cor"], anchor=lado["anchor"],
                      stroke_width=max(2, int(self.ref * 0.004)),
                      stroke_fill=(12, 10, 24))
        if alfa < 1.0:
            camada = self._com_alfa(camada, alfa)
        img.paste(camada, (0, 0), camada)

    def _veredito_preparado(self, event: dict) -> dict | None:
        ver = event.get("veredito")
        if not ver or not str(ver.get("vencedor") or "").strip():
            return None
        vencedor = str(ver["vencedor"]).strip()
        fonte = fit_font(vencedor, self.fonts["black"], int(self.width * 0.86),
                         int(self.ref * 0.085))
        fonte_ko = load_font(self.fonts["bold"], int(self.ref * 0.034))
        return {"de": float(ver.get("de", 0.0)), "nome": vencedor,
                "ko": str(ver.get("ko_type") or "").strip(),
                "fonte": fonte, "fonte_ko": fonte_ko}

    def _desenhar_veredito(self, img: Image.Image, ver: dict, t: float) -> None:
        if t < ver["de"]:
            return
        # Sobe em 0,25 s sobre o ultimo frame da luta, em vez de virar um
        # cartao depois dela: o formato nunca para o jogo para falar.
        alfa = min(1.0, (t - ver["de"]) / 0.25)
        camada = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(camada)
        cy = int(self.height * 0.5)
        draw.text((self.width // 2, cy), ver["nome"], font=ver["fonte"],
                  fill=(255, 255, 255), anchor="mm",
                  stroke_width=max(4, int(self.ref * 0.008)), stroke_fill=(12, 10, 24))
        if ver["ko"]:
            draw.text((self.width // 2, cy + int(self.ref * 0.075)), ver["ko"],
                      font=ver["fonte_ko"], fill=(255, 214, 92), anchor="mm",
                      stroke_width=3, stroke_fill=(12, 10, 24))
        if alfa < 1.0:
            camada = self._com_alfa(camada, alfa)
        img.paste(camada, (0, 0), camada)

    def _callouts_preparados(self, event: dict) -> list[dict]:
        saida = []
        stroke = max(3, int(self.ref * 0.006))
        for callout in event.get("callouts") or []:
            texto = str(callout.get("texto") or "").strip()
            if not texto:
                continue
            cor_hex = str(callout.get("cor") or "#ffffff")
            cor = hex_rgb(cor_hex) if cor_hex.startswith("#") and len(cor_hex) == 7 \
                else (255, 255, 255)
            fonte = fit_font(texto, self.fonts["black"], int(self.width * 0.9),
                             int(self.ref * 0.115))
            caixa = fonte.getbbox(texto, stroke_width=stroke)
            largura = caixa[2] - caixa[0] + stroke * 2 + 8
            altura = caixa[3] - caixa[1] + stroke * 2 + 8
            camada = Image.new("RGBA", (max(1, largura), max(1, altura)), (0, 0, 0, 0))
            ImageDraw.Draw(camada).text((largura / 2, altura / 2), texto, font=fonte,
                                        fill=cor, anchor="mm", stroke_width=stroke,
                                        stroke_fill=(15, 12, 30))
            saida.append({"t": float(callout.get("t", 0.0)),
                          "dur": float(callout.get("duracao", 0.9)),
                          "camada": camada})
        return saida

    def _desenhar_callout(self, img: Image.Image, callout: dict, t: float) -> None:
        idade = t - callout["t"]
        if idade < 0 or idade > callout["dur"]:
            return
        escala = 1.0 + 0.35 * max(0.0, 1.0 - idade / 0.12)      # pop-in
        alfa = 1.0 if idade < callout["dur"] - 0.25 \
            else max(0.0, (callout["dur"] - idade) / 0.25)        # fade-out
        camada = callout["camada"]
        if abs(escala - 1.0) > 0.01:
            camada = camada.resize((max(1, int(camada.width * escala)),
                                    max(1, int(camada.height * escala))),
                                   Image.BILINEAR)
        if alfa < 1.0:
            camada = self._com_alfa(camada, alfa)
        cx = self.width // 2
        cy = int(self.height * (0.20 if self.horizontal else 0.22))
        img.paste(camada, (cx - camada.width // 2, cy - camada.height // 2), camada)

    def _concat(self, segments: list[Path], out_path: Path) -> None:
        """Junta os segmentos e CONFERE que juntou todos.

        O `returncode` do ffmpeg mente aqui: com um segmento ilegivel no meio
        da lista ele imprime "Error during demuxing" e sai **0**, entregando
        um video que comeca certo e acaba cedo. Descoberto em 31/08/2026 no
        projeto de historias (11,8 s no lugar de 193 s, com o log dizendo
        "pronto"); a montagem daqui tinha exatamente o mesmo furo.
        """
        ruins = medidas.quebrados(segments)
        if ruins:
            raise RuntimeError(
                "segmento(s) ilegivel(is) antes de juntar: "
                + ", ".join(p.name for p in ruins)
                + ". Apague a pasta _segments_* e renderize de novo.")
        esperado = sum(medidas.duracao(s) or 0.0 for s in segments)

        list_file = out_path.with_suffix(".txt")
        list_file.write_text(
            "".join(f"file '{s.as_posix()}'\n" for s in segments), encoding="utf-8")
        base = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                "-i", str(list_file)]
        tentativas = (
            base + ["-c", "copy", str(out_path)],
            base + ["-c:v", "libx264", "-preset", self.preset,
                    "-crf", str(self.crf), "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(out_path)],
        )
        erro = ""
        for cmd in tentativas:
            result = subprocess.run(cmd, capture_output=True, text=True,
                                    creationflags=NO_WINDOW)
            saiu = medidas.duracao(out_path)
            if result.returncode == 0 and saiu is not None \
                    and saiu >= esperado - 0.5:
                return
            erro = (result.stderr or "")[-400:] or (
                f"saiu com {saiu:.1f}s de {esperado:.1f}s esperados"
                if saiu else "o arquivo nao abre")
            print(f"[render] concat incompleto ({erro}); tentando recodificar",
                  flush=True)
        raise RuntimeError(
            f"Concat falhou: {erro}. Esperava {esperado:.1f}s de "
            f"{len(segments)} segmento(s).")

    def _mix_final(self, video: Path, music: Path | None, voz: Path | None,
                   out_path: Path) -> None:
        """Mixagem final: som dos segmentos + trilha (em loop) + voz, normalizado.

        A trilha e ABAIXADA sob a fala (sidechain): sem isso a voz briga com
        a musica e o espectador sobe o volume para entender. `loudnorm` no
        fim poe o arquivo no nivel que as plataformas esperam (-14 LUFS): o
        video saia a -30 dB de media, que no celular e "mudo". Qualquer
        falha do ffmpeg entrega o concat como esta — o video nunca deixa de
        existir por causa da mixagem.
        """
        sr = int(self.audio_cfg.get("sample_rate", 44100))
        alvo = float(self.audio_cfg.get("loudnorm", -14))
        tem_voz = voz is not None and Path(voz).is_file()
        tem_musica = music is not None and Path(music).is_file()
        ducking = tem_voz and tem_musica and bool(self.audio_cfg.get("ducking", True))

        entradas = ["-i", str(video)]
        cadeia = [f"[0:a]aresample={sr},aformat=channel_layouts=stereo[base]"]
        mix = ["[base]"]
        indice = 1
        if tem_voz:
            vv = float((self.audio_cfg.get("voz") or {}).get("volume", 1.0))
            entradas += ["-i", str(voz)]
            if ducking:
                cadeia.append(f"[{indice}:a]aresample={sr},volume={vv},asplit=2[v1][v2]")
            else:
                cadeia.append(f"[{indice}:a]aresample={sr},volume={vv}[v1]")
            indice += 1
        if tem_musica:
            mv = float(self.audio_cfg.get("music_volume", 0.22))
            entradas += ["-stream_loop", "-1", "-i", str(music)]
            cadeia.append(f"[{indice}:a]aresample={sr},volume={mv}[m]")
            if ducking:
                cadeia.append("[m][v2]sidechaincompress=threshold=0.03:ratio=6:"
                              "attack=40:release=400:makeup=1[md]")
                mix.append("[md]")
            else:
                mix.append("[m]")
            indice += 1
        if tem_voz:
            mix.append("[v1]")

        if len(mix) > 1:
            cadeia.append("".join(mix) + f"amix=inputs={len(mix)}:duration=first:"
                          "dropout_transition=0:normalize=0[mx]")
            ultimo = "[mx]"
        else:
            ultimo = "[base]"
        cadeia.append(f"{ultimo}alimiter=limit=0.89,loudnorm=I={alvo}:TP=-1.5:LRA=11,"
                      f"aresample={sr}[out]")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", *entradas,
               "-filter_complex", ";".join(cadeia),
               "-map", "0:v", "-map", "[out]", "-c:v", "copy",
               "-c:a", "aac", "-b:a", "160k", "-ar", str(sr), str(out_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW)
        if result.returncode != 0:
            print(f"[render] mixagem final falhou ({result.stderr[-300:]}); "
                  "o video sai sem trilha/voz", flush=True)
            out_path.write_bytes(video.read_bytes())

    # ------------------------------------------------------------------ frames
    def _bg(self) -> Image.Image:
        if self._bg_cache is None:
            self._bg_cache = gradient(self.width, self.height,
                                      self.colors["bg_top"], self.colors["bg_bottom"])
        return self._bg_cache

    def _frames_for(self, event: dict, generation: dict, out_dir: Path):
        kind = event["type"]
        if kind in ("hook", "outro") and                 (event.get("asset") or {}).get("media") == "imagem":
            # O outro entra aqui pelo mesmo caminho do gancho: e nele que a
            # pessoa decide curtir, e ate 31/08 ele era um cartao de texto
            # sobre fundo quase preto — a ULTIMA coisa do video era uma tela
            # morta. Com a imagem do build atras, o pedido de like acontece
            # olhando para o que o video prometeu.
            return self._hook_frames(event)
        if kind == "roulette":
            return self._roulette_frames(event)
        if kind == "reaction":
            return self._reaction_frames(event)
        if kind in ("identity", "comentario") and \
                (event.get("asset") or {}).get("media") == "imagem":
            return self._still_frames(event)
        if kind == "comentario":
            # Print ilegivel: o video segue sem a prova, nunca quebra por ela.
            return self._caption_frames(event)
        if kind in ("nameplate", "identity"):
            # `identity` so chega aqui quando o mp4 do clipe faltou ou nao pode
            # ser lido: o caminho normal dele e o transcode, nao o desenho.
            return self._nameplate_frames(event)
        if kind == "stinger":
            return self._stinger_frames(event)
        if kind in ("reveal_character", "reveal_weapon"):
            # Formato antigo. Continua desenhavel para `--rerender` sem
            # `--refazer-edicao` conseguir refazer um plano ja gravado.
            return self._reveal_frames(event, out_dir)
        if kind == "synergy":
            return self._synergy_frames(event, generation)
        if kind == "final":
            return self._final_frames(event)
        # --- telas de torneio ---
        if kind == "participantes":
            return self._participantes_frames(event)
        if kind == "round_title":
            return self._round_title_frames(event)
        if kind == "fight_card":
            return self._fight_card_frames(event)
        if kind == "skill_card":
            # so chega aqui sem demo gravada: o card sintético fala sozinho
            return self._skill_card_frames(event)
        if kind == "round_result":
            return self._round_result_frames(event)
        if kind == "fight_result":
            return self._fight_result_frames(event)
        if kind == "gameplay":
            # so chega aqui se o mp4 da luta faltou ou nao pode ser lido
            return self._gameplay_indisponivel_frames(event)
        if kind == "champion":
            return self._champion_frames(event)
        if kind == "tournament_stats":
            return self._tournament_stats_frames(event)
        return self._caption_frames(event)  # hook / outro

    def _n_frames(self, duration: float) -> int:
        return max(1, round(duration * self.fps))

    def _caption_frames(self, event: dict):
        total = self._n_frames(event["duration"])
        caption = event.get("caption", "")
        font = fit_font_wrap(caption, self.fonts["black"], int(self.width * 0.9),
                             int(self.ref * 0.085), max_lines=3)
        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            pulse = 1 + 0.03 * math.sin(i / self.fps * 6)
            self._wrapped_center(draw, caption, font, self.height * 0.5,
                                 fill=(245, 242, 255), stroke=4, scale=pulse)
            yield img
        return

    # ------------------------------------------------------------ wheel frames
    def _roulette_frames(self, event: dict):
        """Roleta visual: roda com TODOS os resultados possiveis, girando com
        desaceleracao ate o ponteiro parar no vencedor. Layout vertical (roda
        em cima, resultado embaixo) ou horizontal (roda a esquerda, resultado
        a direita)."""
        roll = event["roll"]
        wheel_data = roll.get("wheel") or {"labels": [str(roll["display_value"])], "winner": 0}
        labels, encurtou = self._curtos(wheel_data["labels"])
        # O numerao e a roda mostram a MESMA forma do resultado: se a roda
        # precisou manter o nome longo, ele fica longo em cima tambem.
        valor = (self._curto(roll["display_value"]) if encurtou
                 else str(roll["display_value"]))
        winner = wheel_data["winner"]
        total = self._n_frames(event["duration"])
        spin_frames = min(total - 1, self._n_frames(event["spin_duration"]))
        accent = self.colors["accent_character"] if roll["entity"] == "character" \
            else self.colors["accent_weapon"]
        tier_rgb = hex_rgb(roll["tier_color"])
        effects = event.get("effects", [])
        rng = random.Random(f"{roll['entity']}:{roll['roulette_id']}:anim")

        # Secao 1: TITULO CURTO -> RESULTADO -> ROLETA GRANDE, e o resto da
        # tela limpo. Saiu a barra de atributo e saiu o rotulo de tier: eram
        # eles que faziam cada rolagem virar uma tela de interface (secao 2).
        # Quem carrega a qualidade do resultado agora e a cor do numero.
        if self.horizontal:
            # No 16:9 a roda vive a esquerda e o texto a direita; a coluna de
            # texto para antes da roda para a legenda nao cair em cima dela.
            radius = int(self.height * 0.40)
            cx, cy = int(self.width * 0.24), int(self.height * 0.52)
            px_info = self.width * 0.70
            info_max_w = int(self.width * 0.44)
            y_header, y_value = self.height * 0.24, self.height * 0.46
            y_caption = self.height * 0.74
        else:
            radius = int(self.width * 0.46)
            cx, cy = self.width // 2, int(self.height * 0.575)
            px_info = self.width / 2
            info_max_w = int(self.width * 0.88)
            y_header, y_value = self.height * 0.085, self.height * 0.185
            # Acima do rodape: no celular o app cobre a faixa de baixo com
            # legenda e botoes, e a piada nao pode nascer atras deles.
            y_caption = self.height * 0.895

        giro = self._giro(event, labels, winner)
        total_rotation = giro["rotacao_total"]

        # A roda inteira e girada por `total_rotation` na hora de colar, entao
        # a orientacao de cada rotulo precisa ser decidida contra o angulo em
        # que ele vai PARAR - nao contra a posicao dele no desenho. As duas
        # imagens usam a mesma orientacao de proposito: orientacoes diferentes
        # fariam metade dos rotulos virar de cabeca para baixo no exato frame
        # em que a roda para.
        wheel_img = self._build_wheel(labels, radius, accent,
                                      offset_giro=total_rotation)
        highlight_img = self._build_wheel(labels, radius, accent,
                                          highlight=winner,
                                          offset_giro=total_rotation)
        # Brilho na cor do tier atras da roda quando ela para: o olho le a
        # qualidade do resultado antes de ler o numero.
        brilho = self._brilho_do_tier(radius, tier_rgb, roll.get("tier", "AVERAGE"))

        header_font = load_font(self.fonts["black"], int(self.ref * 0.075))
        header_max_w = info_max_w
        if event.get("avatares") and not self.horizontal:
            # Com os avatares nos cantos, o titulo cabe entre eles: encolhe a
            # fonte em vez de deixar o "E" de ENCANTAMENTO atras do rosto.
            header_max_w = int(self.width * 0.58)
            header_font = fit_font(roll["category"], self.fonts["black"],
                                   header_max_w, int(self.ref * 0.075))
        value_font = fit_font_wrap(valor, self.fonts["black"], info_max_w,
                                   int(self.ref * 0.145))
        caption_font = fit_font_wrap(event.get("caption", ""), self.fonts["bold"],
                                     info_max_w, int(self.ref * 0.046))
        caption_spin = str(event.get("caption_spin") or "")
        spin_font = (fit_font_wrap(caption_spin, self.fonts["black"], info_max_w,
                                   int(self.ref * 0.05)) if caption_spin else None)

        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            self._wrapped_center(draw, roll["category"], header_font, y_header,
                                 fill=hex_rgb(accent), stroke=3,
                                 center_x=px_info, max_width=header_max_w)

            if i < spin_frames:
                angle = giro["angulo_em"](i / self.fps)
                frame_wheel, stopped = wheel_img, False
            else:
                angle, frame_wheel, stopped = total_rotation, highlight_img, True
                if brilho is not None:
                    entrada = min(1.0, (i - spin_frames + 1) / (self.fps * 0.2))
                    camada = brilho if entrada >= 1 else self._com_alfa(brilho, entrada)
                    img.paste(camada, (cx - camada.width // 2, cy - camada.height // 2),
                              camada)

            # BICUBIC: com BILINEAR o texto das fatias cintila a cada quadro,
            # que e o que faz o giro parecer "picotado" mesmo a 30 fps.
            rotated = frame_wheel.rotate(angle, resample=Image.BICUBIC)
            img.paste(rotated, (cx - radius, cy - radius), rotated)

            hub_r = int(radius * 0.22)
            draw.ellipse([cx - hub_r, cy - hub_r, cx + hub_r, cy + hub_r],
                         fill=(24, 20, 44), outline=hex_rgb(accent), width=6)
            pw = int(radius * 0.09)
            draw.polygon([(cx - pw, cy - radius - pw), (cx + pw, cy - radius - pw),
                          (cx, cy - radius + int(pw * 1.4))],
                         fill=(255, 255, 255), outline=(15, 12, 30))

            if not stopped:
                draw.text((cx, cy), "?", font=load_font(self.fonts["black"], hub_r),
                          fill=(200, 195, 230), anchor="mm")
                # O lugar do resultado ja existe durante o giro, marcado com
                # "?": a expectativa mora nesse espaco reservado.
                draw.text((px_info, y_value), "?", font=value_font,
                          fill=(96, 90, 126), anchor="mm")
                if spin_font is not None:
                    # A tensao ANTES do resultado: o que esta em jogo nesta
                    # roda, no lugar onde a legenda vai aparecer depois.
                    self._wrapped_center(draw, caption_spin, spin_font, y_caption,
                                         fill=(214, 208, 240), stroke=3,
                                         center_x=px_info, max_width=info_max_w)
            else:
                j = i - spin_frames
                dx = dy = 0
                if "screen_shake" in effects or "shake_small" in effects:
                    amp = (10 if "screen_shake" in effects else 4) * max(0.0, 1 - j / (self.fps * 0.5))
                    dx, dy = rng.randint(-1, 1) * amp, rng.randint(-1, 1) * amp
                # Todo resultado "cai" na tela (pop curto); os extremos
                # ganham o soco maior de sempre.
                scale = 1.0 + 0.16 * max(0.0, 1 - j / (self.fps * 0.16))
                if "punch_zoom" in effects:
                    scale = 1.25 - 0.25 * min(1.0, j / (self.fps * 0.25))
                self._wrapped_center(draw, valor, value_font,
                                     y_value + dy, fill=tier_rgb, stroke=5,
                                     scale=scale, x_offset=dx,
                                     center_x=px_info, max_width=info_max_w)
                self._wrapped_center(draw, event.get("caption", ""), caption_font,
                                     y_caption, fill=(245, 242, 255), stroke=3,
                                     center_x=px_info, max_width=info_max_w)
                if "flash" in effects and j < self.fps * 0.12:
                    white = Image.new("RGB", img.size, (255, 255, 255))
                    img = Image.blend(img, white, 0.55 * (1 - j / (self.fps * 0.12)))
                if "desaturate" in effects and roll["tier"] == "TERRIBLE":
                    img = ImageEnhance.Color(img).enhance(0.35)
            yield img
        return

    def _brilho_do_tier(self, radius: int, cor, tier: str):
        """RGBA borrado na cor do tier, ou None para resultado mediano."""
        if tier in ("AVERAGE", "WEAK"):
            return None
        forte = tier in ("INSANE", "TERRIBLE")
        # Maior que a roda de proposito: o que aparece e o HALO em volta dela.
        lado = int(radius * 2.8)
        base = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
        d = ImageDraw.Draw(base)
        margem = int(radius * 0.22)
        d.ellipse([margem, margem, lado - margem, lado - margem],
                  fill=(*cor, 150 if forte else 95))
        return base.filter(ImageFilter.GaussianBlur(int(radius * 0.22)))

    # ------------------------------------------------------- camada de overlay
    # None = SEM karaoke naquele tipo. Nestes eventos a narracao E a legenda
    # grande da tela (`build_script` fala o proprio `caption`), entao o
    # karaoke escrevia a mesma frase duas vezes, uma embaixo da outra —
    # ocupava tela, nao acrescentava informacao e fazia o video parecer
    # amador. Medido em 31/08 nos frames de gen_00080/76/82.
    KARAOKE_Y = {"roulette": 0.238, "hook": None, "identity": 0.15,
                 "comentario": None, "gameplay": 0.17, "nameplate": None,
                 "stinger": None, "final": None, "outro": None,
                 "synergy": 0.74}

    @staticmethod
    def _carregar_palavras(caminho: Path | None) -> list[dict]:
        if caminho is None or not Path(caminho).is_file():
            return []
        try:
            with open(caminho, encoding="utf-8") as fh:
                dados = json.load(fh)
        except (OSError, ValueError):
            return []
        return sorted((d for d in dados if d.get("texto")), key=lambda d: float(d["t0"]))

    def _com_overlay(self, frames, event: dict):
        """Avatar do personagem/arma e legenda karaoke sobre cada quadro.

        E uma camada, nao um tipo de evento: qualquer cena desenhada ganha
        as duas sem saber que elas existem. O tempo absoluto vem do plano
        (`start` + quadro/fps) — e o que casa a legenda com a voz.
        """
        avatares = event.get("avatares") or {}
        y_karaoke = self.KARAOKE_Y.get(event.get("type"), 0.72)
        if self.horizontal and event.get("type") == "roulette":
            # no 16:9 a coluna de texto fica a direita: entre o valor e a legenda
            y_karaoke = 0.615
        tem_palavras = bool(self._palavras) and y_karaoke is not None
        if not avatares and not tem_palavras:
            yield from frames
            return
        inicio = float(event.get("start") or 0.0)
        for i, img in enumerate(frames):
            if avatares:
                self._desenhar_avatares(img, avatares)
            if tem_palavras:
                self._desenhar_karaoke(img, event, inicio + i / self.fps, y_karaoke)
            yield img

    def _avatar(self, caminho: str, diametro: int, cor) -> Image.Image | None:
        chave = f"{caminho}|{diametro}"
        if chave in self._avatar_cache:
            return self._avatar_cache[chave]
        try:
            fonte = Image.open(caminho)
            fonte.load()
            fonte = fonte.convert("RGB")
        except Exception:
            self._avatar_cache[chave] = None
            return None
        # recorte quadrado pelo terco de cima (onde fica o rosto), circular
        lado = min(fonte.width, fonte.height)
        x0 = (fonte.width - lado) // 2
        y0 = int((fonte.height - lado) * 0.15)
        quadrado = fonte.crop((x0, y0, x0 + lado, y0 + lado)).resize(
            (diametro, diametro), Image.LANCZOS)
        mascara = Image.new("L", (diametro, diametro), 0)
        ImageDraw.Draw(mascara).ellipse([0, 0, diametro - 1, diametro - 1], fill=255)
        anel = int(max(3, diametro * 0.05))
        saida = Image.new("RGBA", (diametro + anel * 2, diametro + anel * 2), (0, 0, 0, 0))
        ImageDraw.Draw(saida).ellipse([0, 0, saida.width - 1, saida.height - 1],
                                      fill=(*cor, 255))
        saida.paste(quadrado, (anel, anel), mascara)
        self._avatar_cache[chave] = saida
        return saida

    def _desenhar_avatares(self, img: Image.Image, avatares: dict) -> None:
        diametro = int(self.ref * 0.15)
        margem_x = int(self.width * 0.035)
        margem_y = int(self.height * (0.03 if self.horizontal else 0.022))
        fonte = load_font(self.fonts["bold"], int(self.ref * 0.026))
        draw = ImageDraw.Draw(img)
        for slot, lado in (("character", "esq"), ("weapon", "dir")):
            dado = avatares.get(slot)
            if not dado:
                continue
            cor = hex_rgb(self.colors["accent_character" if slot == "character"
                                      else "accent_weapon"])
            avatar = self._avatar(dado.get("path", ""), diametro, cor)
            if avatar is None:
                continue
            x = margem_x if lado == "esq" else self.width - margem_x - avatar.width
            img.paste(avatar, (x, margem_y), avatar)
            nome = str(dado.get("nome") or "").split(" ")[0].upper()
            if nome:
                draw.text((x + avatar.width / 2, margem_y + avatar.height + 4), nome,
                          font=fonte, fill=(235, 230, 250), anchor="ma",
                          stroke_width=2, stroke_fill=(15, 12, 30))

    def _linha_ativa(self, t: float) -> list[dict] | None:
        """As palavras da fala que esta soando em `t` (ou acabou de soar)."""
        atual = None
        for palavra in self._palavras:
            if float(palavra["t0"]) - 0.05 <= t:
                atual = palavra
            else:
                break
        if atual is None:
            return None
        linha = [p for p in self._palavras if p.get("linha") == atual.get("linha")]
        fim = max(float(p["t1"]) for p in linha)
        if t > fim + 0.35:
            return None
        return linha

    def _desenhar_karaoke(self, img: Image.Image, event: dict, t: float,
                          y_rel: float) -> None:
        linha = self._linha_ativa(t)
        if not linha:
            return
        entidade = (event.get("roll") or {}).get("entity") or event.get("entity")
        accent = hex_rgb(self.colors["accent_weapon" if entidade == "weapon"
                                     else "accent_character"])
        if self.horizontal and event.get("type") == "roulette":
            cx, largura_max = self.width * 0.70, int(self.width * 0.44)
        else:
            cx, largura_max = self.width / 2, int(self.width * 0.9)
        tamanho = int(self.ref * 0.046)
        espaco = int(tamanho * 0.45)
        palavras = [str(p["texto"]) for p in linha]
        while tamanho > int(self.ref * 0.028):
            fonte = load_font(self.fonts["black"], tamanho)
            larguras = [fonte.getlength(p) for p in palavras]
            total = sum(larguras) + espaco * (len(palavras) - 1)
            if total <= largura_max:
                break
            tamanho = int(tamanho * 0.9)
        draw = ImageDraw.Draw(img)
        x = cx - total / 2
        y = self.height * y_rel
        stroke = max(2, tamanho // 12)
        for palavra, largura, dado in zip(palavras, larguras, linha):
            ativa = float(dado["t0"]) <= t < float(dado["t1"]) + 0.05
            passada = t >= float(dado["t1"]) + 0.05
            if ativa:
                caixa = [x - espaco * 0.4, y - tamanho * 0.15,
                         x + largura + espaco * 0.4, y + tamanho * 1.05]
                draw.rounded_rectangle(caixa, radius=int(tamanho * 0.25), fill=accent)
            cor = (255, 255, 255) if (ativa or passada) else (200, 195, 230)
            draw.text((x, y), palavra, font=fonte, fill=cor, anchor="la",
                      stroke_width=0 if ativa else stroke, stroke_fill=(15, 12, 30))
            x += largura + espaco

    # Expoente da desaceleracao. Quanto maior, mais a roda RASTEJA no fim —
    # e o rastejo e o que da suspense. 4 foi escolhido olhando: com 3 ela
    # ainda chega rapido demais na fatia vencedora.
    EXPOENTE_DA_FREADA = 4

    def _giro(self, event: dict, labels: list[str], winner: int) -> dict:
        """Tudo que descreve o giro. Imagem e SOM leem daqui, nunca cada um do
        seu jeito: se as duas curvas divergirem, o estalo sai fora do lugar."""
        fatias = max(1, len(labels))
        angulo_da_fatia = 360.0 / fatias
        centro = winner * angulo_da_fatia + angulo_da_fatia / 2
        final = (centro - 270.0) % 360.0
        voltas = 3 + (winner % 3)
        rotacao = final + 360.0 * voltas
        duracao = float(event.get("spin_duration") or 1.0)
        expoente = self.EXPOENTE_DA_FREADA

        def angulo_em(segundos: float) -> float:
            t = min(1.0, max(0.0, segundos / duracao))
            return rotacao * (1 - (1 - t) ** expoente)

        return {"fatias": fatias, "angulo_da_fatia": angulo_da_fatia,
                "rotacao_total": rotacao, "duracao": duracao,
                "angulo_em": angulo_em}

    def _audio_do_evento(self, event: dict, destino: Path) -> Path | None:
        """Trilha de efeitos deste evento, ou None se ele nao tem som proprio.

        Roleta: os estalos do giro mais o som do resultado (`_audio_da_roleta`).
        Gancho, stinger, nota final e revelacoes ganham riser/hit/whoosh
        sintetizados (src/video/trilha.py). Sem numpy, sobra o que sempre
        houve: os estalos.
        """
        taxa = int(self.audio_cfg.get("sample_rate", 44100))
        volume = float(self.audio_cfg.get("sfx_volume", 0.9))
        camadas = trilha.sfx_do_evento(event, taxa)
        if event.get("type") == "roulette":
            return self._audio_da_roleta(event, destino, camadas)
        if not camadas:
            return None
        return trilha.gravar_mono(destino.with_suffix(".wav"),
                                  float(event["duration"]), camadas, taxa,
                                  volume=volume * 0.8)

    def _audio_da_roleta(self, event: dict, destino: Path,
                         camadas: list | None = None) -> Path | None:
        """Trilha de estalos deste giro (+ o som do resultado), ou None se o
        evento nao e roleta. Som e imagem leem da MESMA curva (`_giro`)."""
        if event.get("type") != "roulette":
            return None
        taxa = int(self.audio_cfg.get("sample_rate", 44100))
        volume = float(self.audio_cfg.get("sfx_volume", 0.9))
        roll = event.get("roll") or {}
        roda = roll.get("wheel") or {}
        rotulos = roda.get("labels") or [""]
        giro = self._giro(event, rotulos, int(roda.get("winner", 0)))
        tempos = roleta_som.tempos_de_estalo(
            giro["angulo_em"], giro["duracao"], giro["fatias"])
        if not tempos and not camadas:
            return None
        return roleta_som.gravar(
            destino.with_suffix(".wav"), float(event["duration"]), tempos,
            taxa=taxa, volume=volume * 0.55, clack_em=giro["duracao"],
            camadas=[(q, a, g * volume) for q, a, g in (camadas or [])])

    def _build_wheel(self, labels: list[str], radius: int, accent: str,
                     highlight: int | None = None,
                     offset_giro: float = 0.0) -> Image.Image:
        size = radius * 2
        wheel = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(wheel)
        n = len(labels)
        seg = 360.0 / n
        accent_rgb = hex_rgb(accent)
        shades = [
            tuple(int(c * 0.32) for c in accent_rgb) + (255,),
            tuple(int(c * 0.55) for c in accent_rgb) + (255,),
            tuple(min(255, int(c * 0.42 + 30)) for c in accent_rgb) + (255,),
        ]
        box = [0, 0, size - 1, size - 1]
        for i in range(n):
            start = i * seg
            fill = shades[i % 2] if n % 2 == 0 or i < n - 1 else shades[2]
            if highlight is not None and i == highlight:
                fill = tuple(min(255, int(c * 1.6 + 60)) for c in accent_rgb) + (255,)
            draw.pieslice(box, start, start + seg, fill=fill,
                          outline=(15, 12, 30, 255), width=3)
        draw.ellipse(box, outline=accent_rgb + (255,), width=8)

        label_len = int(radius * 0.62)
        label_h = max(20, min(int(2 * math.pi * radius * 0.6 / n * 0.72),
                              int(radius * 0.13)))
        for i, label in enumerate(labels):
            text = label if len(label) <= 16 else label[:15] + "…"
            font = fit_font(text, self.fonts["bold"], label_len - 8, label_h)
            strip = Image.new("RGBA", (label_len, label_h * 2), (0, 0, 0, 0))
            sdraw = ImageDraw.Draw(strip)
            center_angle = i * seg + seg / 2
            # Na metade esquerda da roda, girar o rotulo pelo mesmo angulo o
            # deixa de cabeca para baixo. La ele e escrito para o outro lado e
            # girado 180 graus a menos - o texto sai do centro para fora nos
            # dois lados, sempre legivel.
            # Angulo em que este rotulo vai aparecer na tela depois do giro.
            na_tela = (center_angle - offset_giro) % 360.0
            invertido = 90 < na_tela < 270
            ancora, x_texto = ("lm", 4) if invertido else ("rm", label_len - 4)
            sdraw.text((x_texto, label_h), text, font=font,
                       fill=(245, 242, 255, 255), anchor=ancora,
                       stroke_width=2, stroke_fill=(15, 12, 30, 200))
            giro = (180 - center_angle) if invertido else -center_angle

            rotated = strip.rotate(giro, expand=True, resample=Image.BICUBIC)
            rad = math.radians(center_angle)
            px = radius + math.cos(rad) * radius * 0.60 - rotated.width / 2
            py = radius + math.sin(rad) * radius * 0.60 - rotated.height / 2
            wheel.paste(rotated, (int(px), int(py)), rotated)
        return wheel

    def _reaction_frames(self, event: dict):
        """Cartao sintetico usado quando nao ha clipe real na categoria."""
        total = self._n_frames(event["duration"])
        positive = event["sentiment"] == "positive"
        intensity = event.get("intensity", 0.5)
        base_color = (36, 120, 66) if positive else (130, 34, 34)
        rng = random.Random(event["asset"]["id"])
        label = "INSANO!!!" if positive and intensity > 0.8 else \
            "MUITO BOM!" if positive else \
            "DESASTRE..." if intensity > 0.7 else "RUIM DEMAIS"
        font = load_font(self.fonts["black"], int(self.ref * 0.11))
        for i in range(total):
            t = i / self.fps
            pulse = 0.5 + 0.5 * math.sin(t * (10 if intensity > 0.7 else 5))
            color = tuple(min(255, round(c * (0.8 + 0.4 * pulse))) for c in base_color)
            img = Image.new("RGB", (self.width, self.height), color)
            draw = ImageDraw.Draw(img)
            cx, cy = self.width / 2, self.height * 0.40
            r = self.ref * (0.16 + 0.02 * pulse)
            dx = rng.randint(-6, 6) * intensity if intensity > 0.6 else 0
            draw.ellipse([cx - r + dx, cy - r, cx + r + dx, cy + r],
                         fill=(255, 224, 130), outline=(40, 30, 10), width=8)
            eye_dy = -r * 0.25
            for side in (-1, 1):
                draw.ellipse([cx + side * r * 0.4 - r * 0.09 + dx, cy + eye_dy - r * 0.12,
                              cx + side * r * 0.4 + r * 0.09 + dx, cy + eye_dy + r * 0.12],
                             fill=(40, 30, 10))
            mouth_y = cy + r * 0.30
            if positive:
                draw.arc([cx - r * 0.5 + dx, mouth_y - r * 0.35, cx + r * 0.5 + dx, mouth_y + r * 0.25],
                         start=10, end=170, fill=(40, 30, 10), width=14)
            else:
                draw.arc([cx - r * 0.5 + dx, mouth_y, cx + r * 0.5 + dx, mouth_y + r * 0.6],
                         start=190, end=350, fill=(40, 30, 10), width=14)
            draw.text((self.width / 2, self.height * 0.72), label, font=font,
                      fill=(255, 255, 255), anchor="mm", stroke_width=6,
                      stroke_fill=(20, 15, 10))
            yield img
        return

    def _nameplate_frames(self, event: dict):
        """Nome grande e uma linha de dado. Sem avatar, sem cartao, sem barra.

        E o que ocupa o lugar de um clipe que ainda nao chegou, e tambem o que
        aparece por cima do clipe quando ele chega (secao 15). Tipografia pura:
        a regra de nao usar boneco generico (secao 3) vale nos dois casos.
        """
        placa = event.get("nameplate") or {"titulo": event.get("caption", ""),
                                           "subtitulo": ""}
        total = self._n_frames(event["duration"])
        accent = self.colors["accent_weapon"] if event.get("slot") == "weapon"             else self.colors["accent_character"]
        largura = int(self.width * (0.5 if self.horizontal else 0.9))
        titulo_font = fit_font_wrap(placa["titulo"], self.fonts["black"],
                                    largura, int(self.ref * 0.12))
        sub_font = fit_font(placa["subtitulo"], self.fonts["bold"],
                            int(largura * 0.9), int(self.ref * 0.052))
        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            t = min(1.0, i / max(1, self.fps * 0.22))
            escala = 0.9 + 0.1 * (1 - (1 - t) ** 3)
            self._wrapped_center(draw, placa["titulo"], titulo_font,
                                 self.height * 0.46, fill=(245, 242, 255),
                                 stroke=5, scale=escala)
            if placa.get("subtitulo"):
                draw.text((self.width / 2, self.height * 0.56),
                          placa["subtitulo"], font=sub_font,
                          fill=hex_rgb(accent), anchor="mm",
                          stroke_width=3, stroke_fill=(15, 12, 30))
            yield img
        return

    # ------------------------------------------------------- imagem que anda
    @staticmethod
    def _interp(inicio, fim, t: float):
        return inicio + (fim - inicio) * t

    def _hook_frames(self, event: dict):
        """Gancho por cima da IMAGEM do personagem pronto (cold open).

        O primeiro segundo do video decidia tudo e mostrava um cartao de
        texto sobre fundo liso. Agora ele mostra o que o espectador vai
        ganhar: a imagem do payoff com push-in, uma cortina escura embaixo e
        o gancho em cima dela. Imagem ilegivel cai no cartao de texto de
        sempre — o video nunca abre com tela preta.
        """
        total = self._n_frames(event["duration"])
        caminho = self._caminho_do_asset(event)
        try:
            fonte = Image.open(caminho)
            fonte.load()
            fonte = fonte.convert("RGB")
        except Exception:
            yield from self._caption_frames(event)
            return

        movimento = event.get("motion") or {}
        zoom_ini, zoom_fim = (movimento.get("zoom") or [1.0, 1.14])[:2]
        centros = movimento.get("centro") or [[0.5, 0.45], [0.5, 0.38]]
        (cx0, cy0), (cx1, cy1) = centros[0], centros[-1]
        escala = min(self.width / fonte.width, self.height / fonte.height)
        destino = (max(1, int(fonte.width * escala)), max(1, int(fonte.height * escala)))
        canto = ((self.width - destino[0]) // 2, (self.height - destino[1]) // 2)
        fundo = (self._fundo_da_still(fonte) if destino != (self.width, self.height)
                 else None)

        # Cortina: escurece o terco de baixo para o texto nascer legivel
        # sobre qualquer imagem, sem tarja chapada.
        cortina = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        faixa = ImageDraw.Draw(cortina)
        topo = int(self.height * (0.5 if self.horizontal else 0.55))
        for y in range(topo, self.height):
            alfa = int(205 * ((y - topo) / max(1, self.height - topo)) ** 0.8)
            faixa.line([(0, y), (self.width, y)], fill=(8, 6, 16, alfa))

        caption = str(event.get("caption") or "")
        font = fit_font_wrap(caption, self.fonts["black"],
                             int(self.width * (0.6 if self.horizontal else 0.9)),
                             int(self.ref * 0.11), max_lines=3)
        y_texto = self.height * (0.78 if self.horizontal else 0.8)

        for i in range(total):
            t = i / max(1, total - 1)
            suave = t * t * (3 - 2 * t)
            zoom = max(1.0, self._interp(zoom_ini, zoom_fim, suave))
            cx = self._interp(cx0, cx1, suave)
            cy = self._interp(cy0, cy1, suave)
            largura, altura = fonte.width / zoom, fonte.height / zoom
            x0 = min(max(cx * fonte.width - largura / 2, 0.0), fonte.width - largura)
            y0 = min(max(cy * fonte.height - altura / 2, 0.0), fonte.height - altura)
            quadro = fonte.resize(destino, Image.LANCZOS,
                                  box=(x0, y0, x0 + largura, y0 + altura))
            img = fundo.copy() if fundo is not None else self._bg().copy()
            img.paste(quadro, canto)
            img = Image.alpha_composite(img.convert("RGBA"), cortina).convert("RGB")
            draw = ImageDraw.Draw(img)
            # o texto "cai" na tela nos primeiros quadros e fica pulsando leve
            entrada = min(1.0, i / max(1.0, self.fps * 0.15))
            escala_txt = 1.3 - 0.3 * (1 - (1 - entrada) ** 3)
            escala_txt *= 1 + 0.02 * math.sin(i / self.fps * 6)
            self._wrapped_center(draw, caption, font, y_texto,
                                 fill=(245, 242, 255), stroke=6, scale=escala_txt)
            yield img
        return

    def _still_frames(self, event: dict):
        """Imagem de recompensa como CENA, nunca como cartao parado.

        Imagem sem movimento num video vertical e morte por retencao (secoes 9
        e 20): a cena inteira vira um card estatico no meio de uma sequencia de
        rolagens de 2 s. Entao a camera anda por cima dela.

        Feito em PIL, e nao com o `zoompan` do ffmpeg, por tres motivos: o
        recorte pode ser FRACIONARIO (`Image.resize(box=...)` amostra em
        subpixel, e o pan nao treme como o zoompan em passo de pixel inteiro),
        a placa e composta aqui mesmo com o resto do desenho, e o caminho de
        saida passa a ser o mesmo `_encode_frames` que ja renderiza a roleta.
        """
        total = self._n_frames(event["duration"])
        caminho = self._caminho_do_asset(event)
        try:
            fonte = Image.open(caminho)
            fonte.load()
            fonte = fonte.convert("RGB")
        except Exception:
            # Imagem ilegivel (download truncado, formato exotico) nunca
            # derruba o render: a revelacao cai na placa tipografica, que e o
            # mesmo lugar onde ela cai quando o arquivo nem existe. O print do
            # comentario nao tem placa — cai no texto da etiqueta.
            event.setdefault("asset", {})["synthetic"] = True
            if event.get("type") == "comentario":
                yield from self._caption_frames(
                    {**event, "caption": event.get("badge", "")})
            else:
                yield from self._nameplate_frames(event)
            return

        movimento = event.get("motion") or {}
        zoom_ini, zoom_fim = (movimento.get("zoom") or [1.0, 1.08])[:2]
        centros = movimento.get("centro") or [[0.5, 0.5], [0.5, 0.5]]
        (cx0, cy0), (cx1, cy1) = centros[0], centros[-1]

        # Encaixe "contain": a imagem inteira aparece. O que sobra e preenchido
        # com ela mesma, borrada e escurecida — tarja preta ao lado do
        # personagem entrega que o video foi montado, e o borrado nao.
        escala = min(self.width / fonte.width, self.height / fonte.height)
        destino = (max(1, int(fonte.width * escala)),
                   max(1, int(fonte.height * escala)))
        canto = ((self.width - destino[0]) // 2, (self.height - destino[1]) // 2)
        fundo = self._fundo_da_still(fonte) if destino != (self.width, self.height)             else None

        placa = self._placa_imagem(event)
        estalo = int(event.get("flash_frames", 2))
        duracao = float(event["duration"])
        entra, sai = 0.25, max(0.9, min(duracao - 0.6, 2.6))

        for i in range(total):
            t = i / max(1, total - 1)
            suave = t * t * (3 - 2 * t)          # smoothstep: sem solavanco nas pontas
            zoom = max(1.0, self._interp(zoom_ini, zoom_fim, suave))
            cx = self._interp(cx0, cx1, suave)
            cy = self._interp(cy0, cy1, suave)

            # Recorte em FLOAT: e daqui que vem o movimento liso.
            largura, altura = fonte.width / zoom, fonte.height / zoom
            x0 = min(max(cx * fonte.width - largura / 2, 0.0), fonte.width - largura)
            y0 = min(max(cy * fonte.height - altura / 2, 0.0), fonte.height - altura)
            quadro = fonte.resize(destino, Image.LANCZOS,
                                  box=(x0, y0, x0 + largura, y0 + altura))

            img = fundo.copy() if fundo is not None else self._bg().copy()
            img.paste(quadro, canto)

            if placa is not None:
                alfa = self._alfa_da_placa(i / self.fps, entra, sai)
                if alfa > 0:
                    camada = placa if alfa >= 1 else self._com_alfa(placa, alfa)
                    img = Image.alpha_composite(img.convert("RGBA"), camada).convert("RGB")

            # Estalo de entrada: marca o corte, do mesmo jeito que o efeito
            # `flash` marca uma rolagem extrema. Quantos quadros e decisao do
            # plano (config/editing.json), nao do renderer.
            if i < estalo:
                branco = Image.new("RGB", img.size, (255, 255, 255))
                img = Image.blend(img, branco, 0.35 * (1 - i / max(1, estalo)))
            yield img
        return

    def _fundo_da_still(self, fonte: Image.Image) -> Image.Image:
        """A propria imagem, cobrindo o quadro, borrada e escurecida."""
        escala = max(self.width / fonte.width, self.height / fonte.height)
        tamanho = (max(1, int(fonte.width * escala)), max(1, int(fonte.height * escala)))
        coberto = fonte.resize(tamanho, Image.BILINEAR)
        x = (tamanho[0] - self.width) // 2
        y = (tamanho[1] - self.height) // 2
        recorte = coberto.crop((x, y, x + self.width, y + self.height))
        borrado = recorte.filter(ImageFilter.GaussianBlur(int(self.ref * 0.05)))
        return ImageEnhance.Brightness(borrado).enhance(0.45)

    @staticmethod
    def _alfa_da_placa(segundos: float, entra: float, sai: float) -> float:
        """Mesma curva do fade que o ffmpeg aplica no clipe de video."""
        if segundos < entra:
            return 0.0
        if segundos < entra + 0.35:
            return (segundos - entra) / 0.35
        if segundos < sai:
            return 1.0
        if segundos < sai + 0.4:
            return max(0.0, 1 - (segundos - sai) / 0.4)
        return 0.0

    @staticmethod
    def _com_alfa(camada: Image.Image, alfa: float) -> Image.Image:
        copia = camada.copy()
        canal = copia.getchannel("A").point(lambda v: int(v * alfa))
        copia.putalpha(canal)
        return copia

    def _stinger_frames(self, event: dict):
        """Batida de virada: uma linha, na cor da metade que comeca."""
        total = self._n_frames(event["duration"])
        accent = self.colors["accent_weapon"] if event.get("entity") == "weapon"             else self.colors["accent_character"]
        texto = event.get("caption", "")
        font = fit_font_wrap(texto, self.fonts["black"],
                             int(self.width * (0.6 if self.horizontal else 0.92)),
                             int(self.ref * 0.095))
        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            t = min(1.0, i / max(1, self.fps * 0.18))
            self._wrapped_center(draw, texto, font, self.height * 0.5,
                                 fill=hex_rgb(accent), stroke=5,
                                 scale=1.18 - 0.18 * (1 - (1 - t) ** 3))
            yield img
        return

    def _reveal_frames(self, event: dict, out_dir: Path):
        total = self._n_frames(event["duration"])
        card_path = out_dir / event["image"]
        card = Image.open(card_path).convert("RGB") if card_path.exists() else None
        if card is not None:
            if self.horizontal:
                target_h = int(self.height * 0.82)
                card = card.resize((int(card.width * target_h / card.height), target_h))
                card_x = int(self.width * 0.08)
                final_y = int(self.height * 0.09)
            else:
                target_w = int(self.width * 0.88)
                card = card.resize((target_w, int(card.height * target_w / card.width)))
                card_x = int((self.width - card.width) / 2)
                final_y = int(self.height * 0.16)
        caption_font = fit_font(event.get("caption", ""), self.fonts["black"],
                                int((self.width * 0.42) if self.horizontal
                                    else (self.width * 0.9)),
                                int(self.ref * 0.06))
        for i in range(total):
            img = self._bg().copy()
            t = min(1.0, i / (self.fps * 0.4))
            ease = 1 - (1 - t) ** 3
            if card is not None:
                y = int(self.height - (self.height - final_y) * ease)
                img.paste(card, (card_x, y))
            draw = ImageDraw.Draw(img)
            if self.horizontal:
                self._wrapped_center(draw, event.get("caption", ""), caption_font,
                                     self.height * 0.45, fill=(245, 242, 255), stroke=4,
                                     center_x=self.width * 0.70,
                                     max_width=int(self.width * 0.44))
            else:
                self._wrapped_center(draw, event.get("caption", ""), caption_font,
                                     self.height * 0.09, fill=(245, 242, 255), stroke=4)
            yield img
        return

    def _synergy_frames(self, event: dict, generation: dict):
        total = self._n_frames(event["duration"])
        compat = event["compatibility"]
        score = compat["compatibility_score"]
        tier_color = compat.get("tier_color", "#d9d9d9")
        tier_rgb = hex_rgb(tier_color)
        bar_x = int(self.width * (0.30 if self.horizontal else 0.15))
        bar_w = int(self.width * (0.40 if self.horizontal else 0.70))
        line_max = int(self.width * (0.60 if self.horizontal else 0.86))
        header_font = load_font(self.fonts["black"], int(self.ref * 0.07))
        score_font = load_font(self.fonts["black"], int(self.ref * 0.16))
        caption_font = fit_font(event.get("caption", ""), self.fonts["black"],
                                int(self.width * 0.9), int(self.ref * 0.055))
        lines = ([("+ " + s["label"], (126, 217, 87)) for s in compat.get("synergies", [])]
                 + [("- " + c["label"], (255, 99, 99)) for c in compat.get("conflicts", [])])[:5]
        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            draw.text((self.width / 2, self.height * 0.12), "COMPATIBILIDADE",
                      font=header_font, fill=(245, 242, 255), anchor="mm",
                      stroke_width=3, stroke_fill=(15, 12, 30))
            t = min(1.0, i / (self.fps * 1.2))
            shown = round(score * (1 - (1 - t) ** 2))
            draw.text((self.width / 2, self.height * 0.28), f"{shown}/100",
                      font=score_font, fill=tier_rgb, anchor="mm", stroke_width=5,
                      stroke_fill=(15, 12, 30))
            stat_bar(draw, bar_x, int(self.height * 0.38), bar_w,
                     max(14, int(self.ref * 0.024)), shown, tier_color)
            y = self.height * 0.48
            for text, color in lines:
                font = fit_font(text, self.fonts["bold"], line_max, int(self.ref * 0.038))
                draw.text((self.width / 2, y), text, font=font, fill=color, anchor="mm")
                y += self.height * 0.055
            self._wrapped_center(draw, event.get("caption", ""), caption_font,
                                 self.height * 0.85, fill=(245, 242, 255), stroke=3)
            yield img
        return

    def _final_frames(self, event: dict):
        total = self._n_frames(event["duration"])
        build = event["build"]
        score = build["final_score"]
        color = "#b26bff" if score >= 76 else "#7ed957" if score >= 61 else \
            "#d9d9d9" if score >= 46 else "#ff7a45" if score >= 16 else "#ff3b3b"
        # Secao 8: a nota passa RAPIDO. As tres barras de subnota saiam com a
        # tela de estatisticas: elas repetiam, paradas, o que o video acabou de
        # mostrar rolando. Sobrou o que e novidade - o numero e o veredito.
        header_font = load_font(self.fonts["black"], int(self.ref * 0.062))
        score_font = load_font(self.fonts["black"], int(self.ref * 0.28))
        verdict_font = fit_font(build["verdict_label"], self.fonts["black"],
                                int(self.width * 0.88), int(self.ref * 0.1))
        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            draw.text((self.width / 2, self.height * 0.29), "NOTA FINAL",
                      font=header_font, fill=(154, 147, 184), anchor="mm")
            # Contagem em ~0,5 s: no ritmo novo a cena inteira dura 1,7 s.
            t = min(1.0, i / (self.fps * 0.5))
            shown = round(score * (1 - (1 - t) ** 3))
            draw.text((self.width / 2, self.height * 0.44), str(shown),
                      font=score_font, fill=hex_rgb(color), anchor="mm",
                      stroke_width=6, stroke_fill=(15, 12, 30))
            self._wrapped_center(draw, build["verdict_label"], verdict_font,
                                 self.height * 0.62, fill=hex_rgb(color),
                                 stroke=4)
            yield img
        return

    # ============================================================== TORNEIO ==
    @staticmethod
    def _cor_lutador(ficha: dict, padrao=(155, 89, 255)) -> tuple:
        if not ficha:
            return padrao
        return (ficha.get("cor_r", padrao[0]), ficha.get("cor_g", padrao[1]),
                ficha.get("cor_b", padrao[2]))

    # Distancia L1 minima entre as cores dos dois lados. Abaixo disto o
    # espectador nao separa quem e quem — dois verdes viram um borrao.
    DISTANCIA_MINIMA_DE_COR = 140

    @staticmethod
    def _girar_matiz(cor: tuple, nome: str) -> tuple:
        """Desloca o MATIZ de uma cor por um giro derivado do nome.

        Determinístico e estavel: o mesmo lutador recebe sempre o mesmo
        deslocamento, contra qualquer adversario. Ate 11/09/2026 o desempate
        de cor trocava o lado 2 pelo laranja do ecossistema, entao a cor de
        um personagem DEPENDIA de quem estava do outro lado — ele saia verde
        num video e laranja no seguinte. Identidade que muda nao e
        identidade, e e identidade que transforma fisica aleatoria em
        torcida (a licao do marble racing).
        """
        import colorsys
        import zlib
        h, l, s = colorsys.rgb_to_hls(*[c / 255.0 for c in cor])
        # crc32, nao `hash()`: o hash de str do Python e randomizado por
        # processo (PYTHONHASHSEED), e a cor do lutador mudaria a cada
        # render. Determinismo e doutrina aqui — o mesmo padrao de
        # `identity/prompt.py`.
        semente = zlib.crc32(nome.encode("utf-8"))
        # 0,28 a 0,72 de volta: longe o bastante para separar, e sem chegar
        # perto de uma volta inteira (que devolveria a cor original).
        giro = 0.28 + (semente % 1000) / 1000.0 * 0.44
        r, g, b = colorsys.hls_to_rgb((h + giro) % 1.0, max(0.45, l),
                                      max(0.55, s))
        return (int(r * 255), int(g * 255), int(b * 255))

    def _cores_do_confronto(self, luta: dict) -> tuple[tuple, tuple]:
        """Cores dos dois lados, com contraste garantido.

        As cores vem do banco e podem cair quase iguais (dois verdes) — ai
        nao da para saber quem e quem, e algum desempate e inevitavel.

        O que MUDOU na 15C e de onde sai a cor do desempate. Antes o lado 2
        virava o laranja do ecossistema: uma cor sem nenhuma relacao com
        aquele lutador, que aparecia num video e nao no outro. Agora ele
        gira o PROPRIO matiz por um valor derivado do nome dele.

        A garantia honesta, portanto, nao e "a cor nunca muda": e que toda
        cor que um lutador exibe e funcao SO DELE. Ele tem no maximo duas
        aparencias — a dele e a dele girada — e as duas sao dele, estaveis
        em qualquer confronto. Identidade que muda ao acaso nao vira
        torcida, e torcida e o que o formato precisa.
        """
        cor1 = self._cor_lutador(luta["p1_ficha"])
        cor2 = self._cor_lutador(luta["p2_ficha"], hex_rgb(self.colors["accent_weapon"]))
        distancia = sum(abs(a - b) for a, b in zip(cor1, cor2))
        if distancia < self.DISTANCIA_MINIMA_DE_COR:
            cor2 = self._girar_matiz(cor2, str(luta.get("p2") or ""))
        return cor1, cor2

    def _participantes_frames(self, event: dict):
        total = self._n_frames(event["duration"])
        nomes = event["participantes"]
        colunas = 2 if (len(nomes) > 6 and not self.horizontal) else (
            4 if self.horizontal else 1)
        titulo_font = load_font(self.fonts["black"], int(self.ref * 0.07))
        nome_font = load_font(self.fonts["bold"], int(self.ref * 0.036))
        linhas = (len(nomes) + colunas - 1) // colunas
        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            draw.text((self.width / 2, self.height * 0.12), "OS PARTICIPANTES",
                      font=titulo_font, fill=hex_rgb(self.colors["accent_character"]),
                      anchor="mm", stroke_width=3, stroke_fill=(15, 12, 30))
            aparecendo = min(len(nomes), int((i / max(1, total * 0.6)) * len(nomes)) + 1)
            area_top = self.height * 0.22
            area_h = self.height * 0.66
            cel_h = area_h / max(1, linhas)
            for idx, nome in enumerate(nomes[:aparecendo]):
                col, lin = idx % colunas, idx // colunas
                cx = self.width * (col + 0.5) / colunas
                cy = area_top + cel_h * (lin + 0.5)
                largura = self.width / colunas * 0.86
                draw.rounded_rectangle(
                    [cx - largura / 2, cy - cel_h * 0.34,
                     cx + largura / 2, cy + cel_h * 0.34],
                    radius=14, fill=(35, 32, 64),
                    outline=hex_rgb(self.colors["accent_character"]), width=3)
                texto = nome if len(nome) <= 22 else nome[:21] + "…"
                fonte = fit_font(texto, self.fonts["bold"], int(largura * 0.9),
                                 nome_font.size)
                draw.text((cx, cy), texto, font=fonte, fill=(245, 242, 255),
                          anchor="mm")
            yield img
        return

    def _round_title_frames(self, event: dict):
        total = self._n_frames(event["duration"])
        titulo = event["titulo"]
        accent = hex_rgb(self.colors["accent_weapon"])
        font = fit_font(titulo, self.fonts["black"], int(self.width * 0.9),
                        int(self.ref * 0.14))
        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            t = min(1.0, i / max(1, self.fps * 0.3))
            escala = 1.3 - 0.3 * (1 - (1 - t) ** 3)
            largura_linha = int(self.width * 0.7 * t)
            draw.rectangle([self.width / 2 - largura_linha / 2, self.height * 0.42,
                            self.width / 2 + largura_linha / 2, self.height * 0.425],
                           fill=accent)
            self._wrapped_center(draw, titulo, font, self.height * 0.5,
                                 fill=(245, 242, 255), stroke=5, scale=escala)
            draw.rectangle([self.width / 2 - largura_linha / 2, self.height * 0.575,
                            self.width / 2 + largura_linha / 2, self.height * 0.58],
                           fill=accent)
            yield img
        return

    def _fight_card_frames(self, event: dict):
        total = self._n_frames(event["duration"])
        luta = event["luta"]
        cor1, cor2 = self._cores_do_confronto(luta)
        nome_font_size = int(self.ref * 0.062)
        info_font = load_font(self.fonts["bold"], int(self.ref * 0.032))
        vs_font = load_font(self.fonts["black"], int(self.ref * 0.13))
        caption_font = fit_font(event.get("caption", ""), self.fonts["bold"],
                                int(self.width * 0.9), int(self.ref * 0.042))
        # rotulo de rodada pode ser longo ("ESTREIA • MELHOR DE 3"): encolhe
        # para caber em vez de vazar pelas bordas.
        rodada_font = fit_font(luta["rodada_nome"], self.fonts["bold"],
                               int(self.width * 0.9), int(self.ref * 0.04))

        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            t = min(1.0, i / max(1, self.fps * 0.35))
            desliza = (1 - (1 - t) ** 3)
            draw.text((self.width / 2, self.height * 0.08), luta["rodada_nome"],
                      font=rodada_font, fill=(154, 147, 184), anchor="mm")

            if self.horizontal:
                centros = [(self.width * 0.26, self.height * 0.48),
                           (self.width * 0.74, self.height * 0.48)]
                deslocamentos = [(-self.width * (1 - desliza), 0),
                                 (self.width * (1 - desliza), 0)]
            else:
                centros = [(self.width / 2, self.height * 0.30),
                           (self.width / 2, self.height * 0.68)]
                deslocamentos = [(-self.width * (1 - desliza), 0),
                                 (self.width * (1 - desliza), 0)]

            for lado, (nome, ficha, cor) in enumerate((
                    (luta["p1"], luta["p1_ficha"], cor1),
                    (luta["p2"], luta["p2_ficha"], cor2))):
                cx = centros[lado][0] + deslocamentos[lado][0]
                cy = centros[lado][1] + deslocamentos[lado][1]
                caixa_w = self.width * (0.42 if self.horizontal else 0.86)
                caixa_h = self.height * (0.5 if self.horizontal else 0.26)
                draw.rounded_rectangle(
                    [cx - caixa_w / 2, cy - caixa_h / 2,
                     cx + caixa_w / 2, cy + caixa_h / 2],
                    radius=20, fill=(30, 27, 56), outline=cor, width=5)
                fonte_nome = fit_font(nome, self.fonts["black"],
                                      int(caixa_w * 0.9), nome_font_size)
                draw.text((cx, cy - caixa_h * 0.28), nome, font=fonte_nome,
                          fill=cor, anchor="mm", stroke_width=3,
                          stroke_fill=(15, 12, 30))
                classe = ficha.get("classe", "?")
                fonte_classe = fit_font(classe, self.fonts["bold"],
                                        int(caixa_w * 0.9), info_font.size)
                draw.text((cx, cy - caixa_h * 0.05), classe, font=fonte_classe,
                          fill=(200, 195, 230), anchor="mm")
                barra_w = int(caixa_w * 0.6)
                for j, (rotulo, valor) in enumerate((
                        ("FORCA", ficha.get("forca", 0)),
                        ("MANA", ficha.get("mana", 0)))):
                    by = cy + caixa_h * (0.14 + j * 0.16)
                    draw.text((cx - barra_w / 2 - self.ref * 0.008, by), rotulo,
                              font=info_font, fill=(154, 147, 184), anchor="rm")
                    stat_bar(draw, int(cx - barra_w / 2), int(by - self.ref * 0.011),
                             barra_w, max(10, int(self.ref * 0.022)),
                             round(valor * 10), "#%02x%02x%02x" % cor)
                    draw.text((cx + barra_w / 2 + self.ref * 0.008, by), str(valor),
                              font=info_font, fill=(245, 242, 255), anchor="lm")
                # Onda 11D: os nomes do kit, discretos, sob as barras — quem
                # descreve é o showcase da estreia, não o card do confronto.
                kit = ficha.get("kit") or []
                if kit:
                    linha_kit = "  ·  ".join(
                        s.get("nome", "") for s in kit if s.get("nome")
                    )
                    fonte_kit = fit_font(linha_kit, self.fonts["regular"],
                                         int(caixa_w * 0.92),
                                         int(self.ref * 0.024))
                    draw.text((cx, cy + caixa_h * 0.42), linha_kit,
                              font=fonte_kit, fill=(154, 147, 184),
                              anchor="mm")

            if t >= 1.0:
                pulso = 1 + 0.08 * math.sin(i / self.fps * 8)
                vs_y = self.height * (0.48 if self.horizontal else 0.49)
                self._wrapped_center(draw, "VS", vs_font, vs_y,
                                     fill=(255, 255, 255), stroke=6, scale=pulso)
            self._wrapped_center(draw, event.get("caption", ""), caption_font,
                                 self.height * 0.93, fill=(245, 242, 255), stroke=3)
            yield img
        return

    def _skill_card_frames(self, event: dict):
        """Onda 11D: card sintético do showcase de kit (sem demo gravada, o
        card fala sozinho: nome na COR da skill, papel e descrição)."""
        total = self._n_frames(event["duration"])
        skill = event.get("skill") or {}
        placa = event.get("nameplate") or {}
        nome = str(skill.get("nome") or placa.get("titulo") or "")
        descricao = str(skill.get("descricao") or placa.get("subtitulo") or "")
        papel = str(skill.get("papel") or "").title()
        lutador = str(event.get("lutador") or "")
        cor = skill.get("cor") or [245, 242, 255]
        accent = tuple(int(c) for c in cor[:3])
        rotulo = f"KIT DE {lutador}".upper() if lutador else "KIT"
        font_rotulo = fit_font(rotulo, self.fonts["bold"],
                               int(self.width * 0.8), int(self.ref * 0.03))
        font_nome = fit_font_wrap(nome, self.fonts["black"],
                                  int(self.width * 0.86),
                                  int(self.ref * 0.095))
        font_meta = fit_font(papel or " ", self.fonts["bold"],
                             int(self.width * 0.8), int(self.ref * 0.036))
        font_desc = fit_font_wrap(descricao or " ", self.fonts["regular"],
                                  int(self.width * 0.8),
                                  int(self.ref * 0.042), max_lines=3)
        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            t = min(1.0, i / max(1, self.fps * 0.25))
            draw.text((self.width / 2, self.height * 0.2), rotulo,
                      font=font_rotulo, fill=(154, 147, 184), anchor="mm")
            pulse = 1 + 0.02 * math.sin(i / self.fps * 5)
            self._wrapped_center(draw, nome, font_nome, self.height * 0.38,
                                 fill=accent, stroke=5, scale=pulse)
            if papel:
                draw.text((self.width / 2, self.height * 0.5), papel,
                          font=font_meta, fill=(245, 242, 255), anchor="mm",
                          stroke_width=2, stroke_fill=(15, 12, 30))
            if descricao:
                self._wrapped_center(draw, descricao, font_desc,
                                     self.height * 0.62,
                                     fill=(210, 205, 230), stroke=2,
                                     max_width=int(self.width * 0.8))
            largura_linha = int(self.width * 0.5 * t)
            draw.rectangle(
                [self.width / 2 - largura_linha / 2, self.height * 0.72,
                 self.width / 2 + largura_linha / 2, self.height * 0.723],
                fill=accent)
            yield img
        return

    def _round_result_frames(self, event: dict):
        """Placar entre rounds de uma serie: quem levou, e como esta.

        Tela deliberadamente mais leve que o veredito da serie — ninguem foi
        eliminado ainda, entao o que importa e o numero grande no meio.
        """
        total = self._n_frames(event["duration"])
        luta = event["luta"]
        placar = list(event.get("placar") or [0, 0])
        cor1, cor2 = self._cores_do_confronto(luta)
        cor = cor1 if luta["vencedor"] == luta["p1"] else cor2
        rotulo_font = load_font(self.fonts["black"], int(self.ref * 0.045))
        vencedor_font = fit_font(luta["vencedor"], self.fonts["black"],
                                 int(self.width * 0.9), int(self.ref * 0.075))
        placar_font = load_font(self.fonts["black"], int(self.ref * 0.16))
        nome_font = load_font(self.fonts["bold"], int(self.ref * 0.03))
        info_font = load_font(self.fonts["bold"], int(self.ref * 0.034))
        caption_font = fit_font(event.get("caption", ""), self.fonts["bold"],
                                int(self.width * 0.9), int(self.ref * 0.042))

        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            draw.text((self.width / 2, self.height * 0.20),
                      f"{luta['rodada_nome']} PARA", font=rotulo_font,
                      fill=(154, 147, 184), anchor="mm")
            escala = 1.0
            if i < self.fps * 0.25:
                escala = 1.25 - 0.25 * (i / (self.fps * 0.25))
            self._wrapped_center(draw, luta["vencedor"], vencedor_font,
                                 self.height * 0.30, fill=cor, stroke=5,
                                 scale=escala)

            # o placar da serie, grande, com os nomes pequenos sob cada lado
            y_placar = self.height * 0.50
            for lado, (x, valor, nome, cor_lado) in enumerate((
                    (self.width * 0.32, placar[0], luta["p1"], cor1),
                    (self.width * 0.68, placar[1], luta["p2"], cor2))):
                draw.text((x, y_placar), str(valor), font=placar_font,
                          fill=cor_lado, anchor="mm", stroke_width=4,
                          stroke_fill=(15, 12, 30))
                fonte = fit_font(nome, self.fonts["bold"],
                                 int(self.width * 0.3), nome_font.size)
                draw.text((x, y_placar + self.height * 0.09), nome, font=fonte,
                          fill=(154, 147, 184), anchor="mm")
            draw.text((self.width / 2, y_placar), "x", font=placar_font,
                      fill=(90, 84, 122), anchor="mm")

            draw.text((self.width / 2, self.height * 0.68),
                      f"{luta['ko_type']}  •  {luta['duracao']}s",
                      font=info_font, fill=(245, 242, 255), anchor="mm")
            self._wrapped_center(draw, event.get("caption", ""), caption_font,
                                 self.height * 0.90, fill=(245, 242, 255), stroke=3)
            yield img
        return

    def _fight_result_frames(self, event: dict):
        total = self._n_frames(event["duration"])
        luta = event["luta"]
        vencedor_e_p1 = luta["vencedor"] == luta["p1"]
        cor1, cor2 = self._cores_do_confronto(luta)
        cor = cor1 if vencedor_e_p1 else cor2
        tier_rgb = hex_rgb(luta["tier_color"])
        nome_font = fit_font(luta["vencedor"], self.fonts["black"],
                             int(self.width * 0.9), int(self.ref * 0.1))
        rotulo_font = load_font(self.fonts["black"], int(self.ref * 0.05))
        info_font = load_font(self.fonts["bold"], int(self.ref * 0.038))
        marca_font = load_font(self.fonts["black"], int(self.ref * 0.042))
        caption_font = fit_font(event.get("caption", ""), self.fonts["bold"],
                                int(self.width * 0.9), int(self.ref * 0.044))
        rng = random.Random(f"resultado:{luta['match_id']}")
        extremo = luta["tier"] in ("INSANE", "GREAT", "TERRIBLE")
        # Numa serie o veredito e da SERIE, nao do round que fechou: o placar
        # entra sob o nome para o 2 x 1 nao virar "venceu por pouco".
        placar = list(event.get("placar") or [])
        rotulo = "VENCEDOR DA SERIE" if placar else "VENCEDOR"
        rotulo_font = fit_font(rotulo, self.fonts["black"],
                               int(self.width * 0.9), rotulo_font.size)
        linha_serie = ""
        info_decisivo = f"{luta['ko_type']}  •  {luta['duracao']}s"
        rotulo_hp = f"HP restante: {luta['hp_vencedor']}%"
        if placar:
            formato = event.get("melhor_de")
            linha_serie = (f"MELHOR DE {formato}  •  " if formato else "")
            linha_serie += " x ".join(str(v) for v in placar)
            round_ = luta.get("round")
            decidiu = f"round {round_} decidiu" if round_ else "round decisivo"
            info_decisivo = f"{decidiu}: {luta['ko_type']}, {luta['duracao']}s"
            rotulo_hp = f"HP no fim: {luta['hp_vencedor']}%"

        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            dx = 0
            if extremo and i < self.fps * 0.4:
                amp = 8 * max(0.0, 1 - i / (self.fps * 0.4))
                dx = rng.randint(-1, 1) * amp
            draw.text((self.width / 2 + dx, self.height * 0.16), rotulo,
                      font=rotulo_font, fill=(154, 147, 184), anchor="mm")
            escala = 1.0
            if i < self.fps * 0.25:
                escala = 1.3 - 0.3 * (i / (self.fps * 0.25))
            self._wrapped_center(draw, luta["vencedor"], nome_font,
                                 self.height * 0.27, fill=cor, stroke=5,
                                 scale=escala, x_offset=dx)

            if linha_serie:
                draw.text((self.width / 2, self.height * 0.365), linha_serie,
                          font=marca_font, fill=tier_rgb, anchor="mm",
                          stroke_width=3, stroke_fill=(15, 12, 30))
            # Numa serie, KO e duracao sao do round que FECHOU: sem dizer isso
            # a tela parece afirmar que a serie inteira durou 21 s.
            draw.text((self.width / 2, self.height * 0.40), info_decisivo,
                      font=info_font, fill=(245, 242, 255), anchor="mm")

            draw.text((self.width * 0.5, self.height * 0.47), rotulo_hp,
                      font=info_font, fill=(154, 147, 184), anchor="mm")
            barra_w = int(self.width * 0.5)
            stat_bar(draw, int((self.width - barra_w) / 2), int(self.height * 0.50),
                     barra_w, max(12, int(self.ref * 0.02)),
                     luta["hp_vencedor"], "#%02x%02x%02x" % cor)

            marcas = luta.get("marcas", [])[:3]
            y = self.height * 0.58
            for marca in marcas:
                cor_marca = (255, 214, 90) if marca in ("ZEBRA", "DUPLO KO") else tier_rgb
                fonte = fit_font(marca.upper(), self.fonts["black"],
                                 int(self.width * 0.8), marca_font.size)
                draw.text((self.width / 2, y), marca.upper(), font=fonte,
                          fill=cor_marca, anchor="mm", stroke_width=3,
                          stroke_fill=(15, 12, 30))
                y += self.height * 0.06

            # sem marcas o bloco sobe: nada de vao vazio no meio da tela
            y_eliminado = max(y + self.height * 0.02, self.height * 0.60)
            draw.text((self.width / 2, y_eliminado),
                      f"eliminado: {luta['perdedor']}", font=info_font,
                      fill=(255, 122, 122), anchor="mm")
            self._wrapped_center(draw, event.get("caption", ""), caption_font,
                                 self.height * 0.90, fill=(245, 242, 255), stroke=3)
            yield img
        return

    def _gameplay_indisponivel_frames(self, event: dict):
        """Cartao usado quando o mp4 da luta nao existe ou nao pode ser lido.

        O video precisa continuar de pe: uma luta sem gravacao vira um aviso
        curto, e o resultado (que sempre existe) e mostrado logo em seguida.
        """
        total = self._n_frames(event["duration"])
        luta = event.get("luta") or {}
        titulo_font = load_font(self.fonts["black"], int(self.ref * 0.055))
        nome_font = fit_font(f"{luta.get('p1', '?')} vs {luta.get('p2', '?')}",
                             self.fonts["bold"], int(self.width * 0.86),
                             int(self.ref * 0.05))
        for _ in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            self._wrapped_center(draw, "LUTA NAO GRAVADA", titulo_font,
                                 self.height * 0.45, fill=(154, 147, 184), stroke=3)
            self._wrapped_center(draw, f"{luta.get('p1', '?')} vs {luta.get('p2', '?')}",
                                 nome_font, self.height * 0.53,
                                 fill=(245, 242, 255), stroke=2)
            yield img
        return

    def _champion_frames(self, event: dict):
        total = self._n_frames(event["duration"])
        torneio = event["torneio"]
        ficha = torneio.get("campeao_ficha", {})
        cor = self._cor_lutador(ficha, (255, 214, 90))
        campeao = str(torneio.get("campeao", "???"))
        titulo_font = load_font(self.fonts["black"], int(self.ref * 0.06))
        nome_font = fit_font(campeao, self.fonts["black"], int(self.width * 0.88),
                             int(self.ref * 0.13))
        info_font = load_font(self.fonts["bold"], int(self.ref * 0.038))
        caption_font = fit_font(event.get("caption", ""), self.fonts["black"],
                                int(self.width * 0.9), int(self.ref * 0.05))
        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            t = i / self.fps
            # raios de luz girando atras do campeao
            cx, cy = self.width / 2, self.height * 0.36
            raio = self.ref * 0.42
            for k in range(12):
                ang = math.radians(k * 30 + t * 25)
                draw.line([cx, cy, cx + math.cos(ang) * raio,
                           cy + math.sin(ang) * raio],
                          fill=(46, 40, 80), width=max(2, int(self.ref * 0.012)))
            self._wrapped_center(draw, "🏆 CAMPEAO", titulo_font,
                                 self.height * 0.14, fill=(255, 214, 90), stroke=3)
            pulso = 1 + 0.04 * math.sin(t * 5)
            self._wrapped_center(draw, campeao, nome_font, self.height * 0.36,
                                 fill=cor, stroke=6, scale=pulso)
            if ficha:
                sub = f"{ficha.get('classe', '?')}  •  {ficha.get('personalidade', '?')}"
                draw.text((self.width / 2, self.height * 0.52), sub,
                          font=info_font, fill=(200, 195, 230), anchor="mm")
                draw.text((self.width / 2, self.height * 0.58),
                          f"arma: {ficha.get('nome_arma', '?')}",
                          font=info_font, fill=(154, 147, 184), anchor="mm")
            if torneio.get("campeao_gerado"):
                draw.text((self.width / 2, self.height * 0.66),
                          "CRIADO NA ROLETA", font=info_font,
                          fill=(126, 217, 87), anchor="mm")
            self._wrapped_center(draw, event.get("caption", ""), caption_font,
                                 self.height * 0.82, fill=(245, 242, 255), stroke=4)
            yield img
        return

    def _tournament_stats_frames(self, event: dict):
        total = self._n_frames(event["duration"])
        stats = event.get("estatisticas", {})
        titulo_font = load_font(self.fonts["black"], int(self.ref * 0.06))
        rotulo_font = load_font(self.fonts["bold"], int(self.ref * 0.034))
        valor_font = load_font(self.fonts["black"], int(self.ref * 0.038))
        melhor = stats.get("melhor_luta", {})
        linhas = [
            ("LUTAS", str(stats.get("total_lutas", 0))),
            ("NOCAUTES", str(stats.get("kos", 0))),
            ("ZEBRAS", str(stats.get("zebras", 0))),
            ("MAIS RAPIDA", f"{stats.get('mais_rapida', {}).get('duracao', 0)}s"),
            ("MAIS LONGA", f"{stats.get('mais_longa', {}).get('duracao', 0)}s"),
            ("LUTA DO TORNEIO", str(melhor.get("luta", "-"))),
        ]
        for i in range(total):
            img = self._bg().copy()
            draw = ImageDraw.Draw(img)
            draw.text((self.width / 2, self.height * 0.14), "RESUMO DO TORNEIO",
                      font=titulo_font, fill=hex_rgb(self.colors["accent_weapon"]),
                      anchor="mm", stroke_width=3, stroke_fill=(15, 12, 30))
            y = self.height * 0.30
            aparecendo = min(len(linhas), int(i / max(1, self.fps * 0.18)) + 1)
            for rotulo, valor in linhas[:aparecendo]:
                draw.text((self.width * 0.12, y), rotulo, font=rotulo_font,
                          fill=(154, 147, 184), anchor="lm")
                texto = valor if len(valor) <= 30 else valor[:29] + "…"
                fonte = fit_font(texto, self.fonts["black"],
                                 int(self.width * 0.42), valor_font.size)
                draw.text((self.width * 0.88, y), texto, font=fonte,
                          fill=(245, 242, 255), anchor="rm")
                y += self.height * 0.085
            yield img
        return

    # ------------------------------------------------------------------- utils
    @staticmethod
    def _curto(texto) -> str:
        """'Cavaleiro (Defesa)' -> 'Cavaleiro'.

        O parenteses e do catalogo do jogo e nao acrescenta nada na tela: ele
        so obriga a fonte a encolher para caber (secao 13). O dado gravado
        continua completo - isto e so o que aparece no video.
        """
        curto = str(texto).split(" (")[0].strip()
        return curto or str(texto)

    def _curtos(self, rotulos: list[str]) -> tuple[list[str], bool]:
        """Encurta a roda inteira - mas so se ela continuar distinguivel.

        Um catalogo com 'Mago (Fogo)' e 'Mago (Gelo)' viraria duas fatias
        escritas 'Mago', e dois rotulos iguais na roda sao piores que dois
        rotulos longos.
        """
        curtos = [self._curto(rotulo) for rotulo in rotulos]
        if len(set(curtos)) != len(set(rotulos)):
            return [str(r) for r in rotulos], False
        return curtos, True

    @staticmethod
    def _is_emoji(char: str) -> bool:
        code = ord(char)
        return (code >= 0x1F000 or 0x2600 <= code <= 0x27BF
                or code in (0xFE0F, 0x200D, 0x2B50))

    def _emoji_font(self, size: int):
        try:
            return load_font(self.fonts.get("emoji", ""), size)
        except OSError:
            return None

    def _runs(self, text: str) -> list[tuple[str, bool]]:
        """Divide o texto em trechos (texto, eh_emoji) para fontes mistas."""
        runs: list[tuple[str, bool]] = []
        for char in text:
            emoji = self._is_emoji(char)
            if runs and runs[-1][1] == emoji:
                runs[-1] = (runs[-1][0] + char, emoji)
            else:
                runs.append((char, emoji))
        return runs

    def _mixed_length(self, text: str, font, emoji_font) -> float:
        total = 0.0
        for trecho, emoji in self._runs(text):
            usada = emoji_font if (emoji and emoji_font) else font
            total += usada.getlength(trecho)
        return total

    def _draw_mixed(self, draw, cx: float, y: float, text: str, font, fill,
                    stroke: int, emoji_font) -> None:
        """Desenha uma linha centralizada com Arial + Segoe UI Emoji colorido."""
        largura = self._mixed_length(text, font, emoji_font)
        x = cx - largura / 2
        for trecho, emoji in self._runs(text):
            if emoji and emoji_font:
                draw.text((x, y), trecho, font=emoji_font, anchor="lm",
                          embedded_color=True)
                x += emoji_font.getlength(trecho)
            else:
                draw.text((x, y), trecho, font=font, fill=fill, anchor="lm",
                          stroke_width=stroke, stroke_fill=(15, 12, 30))
                x += font.getlength(trecho)

    def _wrapped_center(self, draw: ImageDraw.ImageDraw, text: str, font, y: float,
                        fill, stroke: int = 0, scale: float = 1.0,
                        x_offset: float = 0.0, center_x: float | None = None,
                        max_width: int | None = None) -> None:
        if not text:
            return
        cx = center_x if center_x is not None else self.width / 2
        limit = max_width if max_width is not None else self.width * 0.92
        size = font.size if hasattr(font, "size") else 40
        emoji_font = self._emoji_font(int(size))
        words = text.split()
        lines, current = [], ""
        for word in words:
            trial = f"{current} {word}".strip()
            if self._mixed_length(trial, font, emoji_font) <= limit or not current:
                current = trial
            else:
                lines.append(current)
                current = word
        lines.append(current)
        line_h = size * 1.15 * scale
        start_y = y - line_h * (len(lines) - 1) / 2
        for line in lines:
            self._draw_mixed(draw, cx + x_offset, start_y, line, font, fill,
                             stroke, emoji_font)
            start_y += line_h
