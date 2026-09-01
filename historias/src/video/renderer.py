# -*- coding: utf-8 -*-
"""Plano de edicao -> mp4 da historia.

Uma cena e uma IMAGEM com camera por cima, a legenda karaoke sincronizada
com a voz e, na primeira, o titulo. E so isso — e e de proposito: num canal
de historias o que prende e a voz e a legenda; a imagem existe para o olho
ter onde pousar enquanto o ouvido trabalha.

Tres escolhas que vieram de retencao medida no outro projeto:

  - Imagem PARADA em vertical mata a retencao. Toda cena tem Ken Burns, e o
    movimento alterna entre cenas para a sequencia nao virar slideshow.
  - Legenda KARAOKE (a palavra falada acende) segura quem assiste no mudo,
    que e a maior parte do publico de Shorts.
  - Sem imagem, a cena NAO deixa de existir: sai com o texto grande sobre o
    fundo do canal. Video incompleto e melhor que video inexistente.

O renderer nao decide nada: duracao, camera e titulo vem do plano.
"""
from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from .. import compartilhado

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_desenho = compartilhado.desenho()
medidas = compartilhado.modulo("video.medidas")
fit_font = _desenho.fit_font
fit_font_wrap = _desenho.fit_font_wrap
gradient = _desenho.gradient
hex_rgb = _desenho.hex_rgb
load_font = _desenho.load_font


class VideoRenderer:
    def __init__(self, config: dict, profile: str = "celular",
                 preview: bool = False):
        base = config["profiles"][profile]
        self.config = config
        self.profile = profile
        self.horizontal = base.get("layout") == "horizontal"
        escala = config["preview"]["scale"] if preview else 1.0
        self.width = int(base["width"] * escala) // 2 * 2
        self.height = int(base["height"] * escala) // 2 * 2
        self.fps = int(config["preview"]["fps"] if preview else config["fps"])
        self.crf = int(config["preview"]["crf"] if preview else config["crf"])
        self.preset = config["preview"]["preset"] if preview else config["preset"]
        self.colors = config["colors"]
        self.fonts = config["fonts"]
        self.audio_cfg = config.get("audio", {})
        self.legenda_cfg = config.get("legenda", {})
        self.titulo_cfg = config.get("titulo", {})
        self.camera_cfg = config.get("camera", {})
        self.ref = min(self.width, self.height)
        self._bg = None
        self._vinheta = None
        self._palavras: list[dict] = []

    # ------------------------------------------------------------- publico
    def render(self, plano: dict, out_dir: Path, *, voz: Path | None = None,
               palavras: Path | None = None, musica: Path | None = None,
               out_name: str | None = None) -> Path:
        out_dir = Path(out_dir)
        seg_dir = out_dir / f"_segments_{self.profile}"
        seg_dir.mkdir(parents=True, exist_ok=True)
        self._palavras = self._carregar_palavras(palavras)

        segmentos = []
        total = len(plano["events"])
        for i, evento in enumerate(plano["events"]):
            destino = seg_dir / f"seg_{i:03d}.mp4"
            self._encode_frames(self._cena_frames(evento), destino)
            segmentos.append(destino)
            print(f"[progresso] {self.profile} {i + 1}/{total}", flush=True)

        concat = seg_dir / "concat.mp4"
        self._concat(segmentos, concat)
        final = out_dir / (out_name or f"final_{self.profile}.mp4")
        self._mix_final(concat, musica, voz, final)
        return final

    # -------------------------------------------------------------- ffmpeg
    def _encode_frames(self, frames, destino: Path) -> None:
        """Um segmento. Se sair quebrado, tenta de novo — e nunca deixa lixo.

        O `stderr` do ffmpeg era jogado fora: quando o processo morria no
        meio, o Python levantava um `OSError: [Errno 22]` cru (o cano
        quebrado) e o motivo real ficava perdido. E o arquivo pela metade
        continuava no disco, onde o `concat` tropecava nele depois.
        """
        quadros = list(frames)          # precisa reenviar numa 2a tentativa
        ultimo = ""
        for tentativa in (1, 2):
            erro = self._encode_uma_vez(quadros, destino)
            if erro is None:
                return
            ultimo = erro
            destino.unlink(missing_ok=True)     # nada de segmento pela metade
            print(f"[render] {destino.name}: {erro} — refazendo "
                  f"(tentativa {tentativa + 1})", flush=True)
        raise RuntimeError(f"ffmpeg nao conseguiu escrever {destino.name}: "
                           f"{ultimo}")

    def _encode_uma_vez(self, quadros, destino: Path) -> str | None:
        """None quando o segmento ficou INTEIRO; senao o motivo."""
        taxa = int(self.audio_cfg.get("sample_rate", 44100))
        cmd = ["ffmpeg", "-y", "-loglevel", "error",
               "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{self.width}x{self.height}", "-r", str(self.fps),
               "-i", "pipe:",
               "-f", "lavfi", "-i", f"anullsrc=r={taxa}:cl=stereo",
               "-shortest", "-c:v", "libx264", "-preset", self.preset,
               "-crf", str(self.crf), "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "128k", str(destino)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                stderr=subprocess.PIPE, creationflags=NO_WINDOW)
        cano_quebrou = None
        try:
            for frame in quadros:
                proc.stdin.write(frame.tobytes())
        except OSError as exc:
            # O ffmpeg morreu antes da hora: o motivo dele vale mais que o
            # nosso errno.
            cano_quebrou = f"o ffmpeg fechou a entrada ({exc})"
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass
            saida = (proc.stderr.read() or b"").decode("utf-8", "replace").strip()
            proc.stderr.close()
            proc.wait()
        if proc.returncode != 0 or cano_quebrou:
            return (saida[-400:] or cano_quebrou
                    or f"codigo {proc.returncode}")
        if medidas.duracao(destino) is None:
            # Saiu 0 e mesmo assim o arquivo nao abre: e o caso do `moov
            # atom` faltando, que so aparece na hora do concat.
            return "o arquivo saiu ilegivel (sem moov atom?)"
        return None

    def _concat(self, segmentos, destino: Path) -> None:
        """Junta os segmentos e CONFERE que juntou todos.

        O `returncode` do ffmpeg mente aqui: com um segmento ilegivel no
        meio da lista ele imprime "Error during demuxing" e sai **0**,
        deixando um video com o comeco so. Foi assim que a parte 1 de uma
        historia virou 11,8 s no lugar de 193 s, com o log dizendo "pronto".
        A unica prova que vale e a duracao do resultado.
        """
        ruins = medidas.quebrados(segmentos)
        if ruins:
            raise RuntimeError(
                "segmento(s) ilegivel(is) antes de juntar: "
                + ", ".join(p.name for p in ruins)
                + ". Apague a pasta _segments_* e renderize de novo.")
        esperado = sum(medidas.duracao(s) or 0.0 for s in segmentos)

        lista = destino.with_suffix(".txt")
        lista.write_text("".join(f"file '{s.as_posix()}'\n" for s in segmentos),
                         encoding="utf-8")
        base = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                "-i", str(lista)]
        tentativas = (
            base + ["-c", "copy", str(destino)],
            base + ["-c:v", "libx264", "-preset", self.preset,
                    "-crf", str(self.crf), "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(destino)],
        )
        erro = ""
        for cmd in tentativas:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               creationflags=NO_WINDOW)
            saiu = medidas.duracao(destino)
            if r.returncode == 0 and saiu is not None \
                    and saiu >= esperado - 0.5:
                return
            erro = (r.stderr or "")[-400:] or (
                f"saiu com {saiu:.1f}s de {esperado:.1f}s esperados"
                if saiu else "o arquivo nao abre")
            print(f"[render] concat incompleto ({erro}); tentando recodificar",
                  flush=True)
        raise RuntimeError(
            f"concat falhou: {erro}. Esperava {esperado:.1f}s de "
            f"{len(segmentos)} segmento(s).")

    def _mix_final(self, video: Path, musica: Path | None, voz: Path | None,
                   destino: Path) -> None:
        """Trilha (em loop, abaixada sob a fala) + voz, normalizado em LUFS.

        Sem isto o video sai a -30 dB, que no celular e silencio. O ducking
        existe porque trilha e narracao disputam a mesma faixa de frequencia:
        sem ele voce sobe o volume para entender a historia e leva um susto
        na musica.
        """
        sr = int(self.audio_cfg.get("sample_rate", 44100))
        alvo = float(self.audio_cfg.get("loudnorm", -14))
        tem_voz = voz is not None and Path(voz).is_file()
        tem_musica = musica is not None and Path(musica).is_file()
        ducking = tem_voz and tem_musica and bool(self.audio_cfg.get("ducking", True))

        entradas = ["-i", str(video)]
        cadeia = [f"[0:a]aresample={sr},aformat=channel_layouts=stereo[base]"]
        mistura = ["[base]"]
        indice = 1
        if tem_voz:
            volume = float((self.audio_cfg.get("voz") or {}).get("volume", 1.0))
            entradas += ["-i", str(voz)]
            # EQ de voz falada. Medido em 01/09/2026: a banda de presenca
            # (2-4 kHz), que e onde moram as consoantes, estava 21,4 dB
            # abaixo do fundamental — no alto-falante de celular, que nao
            # reproduz quase nada abaixo de 400 Hz, sobrava pouquissimo. O
            # corte em 220 Hz tira o abafamento sem afinar a voz.
            eq = self.audio_cfg.get("eq_voz") or (
                "highpass=f=85,"
                "equalizer=f=220:t=q:w=1.0:g=-2.5,"
                "equalizer=f=3000:t=q:w=1.2:g=4,"
                "equalizer=f=7500:t=q:w=1.0:g=2.5")
            base_voz = f"[{indice}:a]aresample={sr},volume={volume},{eq}"
            if ducking:
                cadeia.append(f"{base_voz},asplit=2[v1][v2]")
            else:
                cadeia.append(f"{base_voz}[v1]")
            indice += 1
        if tem_musica:
            volume = float(self.audio_cfg.get("music_volume", 0.16))
            entradas += ["-stream_loop", "-1", "-i", str(musica)]
            # A cama cede a faixa da voz em vez de disputar: medido, em
            # 100-300 Hz a musica estava a 1,9 dB do fundamental da fala,
            # mascarando justamente o que sustenta a voz.
            eq = self.audio_cfg.get("eq_musica") or (
                "highpass=f=60,"
                "equalizer=f=300:t=q:w=1.4:g=-6,"
                "equalizer=f=800:t=q:w=1.4:g=-4")
            cadeia.append(f"[{indice}:a]aresample={sr},volume={volume},{eq}[m]")
            if ducking:
                # O ducking antigo (threshold 0.03, ratio 8, release 350 ms)
                # oscilava 18,7 dB: como o release era MAIS CURTO que a pausa
                # de ~930 ms, a musica voltava inteira dentro de cada buraco
                # da fala — 66 inchacos em 3,5 min. Threshold mais alto com
                # ratio menor da uma abaixada constante de 5-7 dB, e o
                # release de 600 ms impede o retorno dentro da pausa.
                duck = self.audio_cfg.get("ducking_filtro") or (
                    "sidechaincompress=threshold=0.06:ratio=3:"
                    "attack=20:release=600:makeup=1")
                cadeia.append(f"[m][v2]{duck}[md]")
                mistura.append("[md]")
            else:
                mistura.append("[m]")
            indice += 1
        if tem_voz:
            mistura.append("[v1]")

        if len(mistura) > 1:
            cadeia.append("".join(mistura) +
                          f"amix=inputs={len(mistura)}:duration=first:"
                          "dropout_transition=0:normalize=0[mx]")
            ultimo = "[mx]"
        else:
            ultimo = "[base]"
        cadeia.append(f"{ultimo}alimiter=limit=0.97,"
                      f"loudnorm=I={alvo}:TP=-1.5:LRA=11,aresample={sr}[out]")
        cmd = ["ffmpeg", "-y", "-loglevel", "error", *entradas,
               "-filter_complex", ";".join(cadeia),
               "-map", "0:v", "-map", "[out]", "-c:v", "copy",
               "-c:a", "aac", "-b:a", "160k", "-ar", str(sr), str(destino)]
        r = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW)
        if r.returncode != 0:
            print(f"[render] mixagem falhou ({r.stderr[-300:]}); video sem trilha",
                  flush=True)
            destino.write_bytes(video.read_bytes())

    # -------------------------------------------------------------- quadros
    def _fundo(self) -> Image.Image:
        if self._bg is None:
            self._bg = gradient(self.width, self.height,
                                self.colors["bg_top"], self.colors["bg_bottom"])
        return self._bg

    def _mascara_vinheta(self) -> Image.Image | None:
        """Escurece as bordas: o olho vai para o centro e a legenda ganha
        contraste sem precisar de tarja."""
        forca = float(self.camera_cfg.get("vinheta", 0.0))
        if forca <= 0:
            return None
        if self._vinheta is None:
            lado = max(self.width, self.height)
            mascara = Image.new("L", (lado, lado), 0)
            desenho = ImageDraw.Draw(mascara)
            passos = 60
            for i in range(passos):
                raio = int(lado * (0.5 + 0.5 * i / passos))
                alfa = int(255 * forca * (i / passos) ** 2.2)
                caixa = [lado // 2 - raio, lado // 2 - raio,
                         lado // 2 + raio, lado // 2 + raio]
                desenho.ellipse(caixa, outline=alfa, width=max(2, lado // passos))
            mascara = mascara.filter(ImageFilter.GaussianBlur(lado * 0.04))
            self._vinheta = mascara.resize((self.width, self.height))
        return self._vinheta

    def _fundo_borrado(self, fonte: Image.Image) -> Image.Image:
        escala = max(self.width / fonte.width, self.height / fonte.height)
        tamanho = (max(1, int(fonte.width * escala)), max(1, int(fonte.height * escala)))
        coberto = fonte.resize(tamanho, Image.BILINEAR)
        x = (tamanho[0] - self.width) // 2
        y = (tamanho[1] - self.height) // 2
        recorte = coberto.crop((x, y, x + self.width, y + self.height))
        borrado = recorte.filter(ImageFilter.GaussianBlur(int(self.ref * 0.05)))
        return ImageEnhance.Brightness(borrado).enhance(0.4)

    def _n_frames(self, duracao: float) -> int:
        return max(1, round(float(duracao) * self.fps))

    @staticmethod
    def _interp(a: float, b: float, t: float) -> float:
        return a + (b - a) * t

    def _cena_frames(self, evento: dict):
        total = self._n_frames(evento["duration"])
        caminho = evento.get("arquivo")
        fonte = None
        if caminho and Path(caminho).is_file():
            try:
                fonte = Image.open(caminho)
                fonte.load()
                fonte = fonte.convert("RGB")
            except Exception:
                fonte = None

        if fonte is None:
            yield from self._cena_sem_imagem(evento, total)
            return

        movimento = evento.get("camera") or {}
        zoom_ini, zoom_fim = (movimento.get("zoom") or [1.0, 1.12])[:2]
        centros = movimento.get("centro") or [[0.5, 0.5], [0.5, 0.5]]
        (cx0, cy0), (cx1, cy1) = centros[0], centros[-1]

        escala = min(self.width / fonte.width, self.height / fonte.height)
        destino = (max(1, int(fonte.width * escala)), max(1, int(fonte.height * escala)))
        canto = ((self.width - destino[0]) // 2, (self.height - destino[1]) // 2)
        fundo = (self._fundo_borrado(fonte)
                 if destino != (self.width, self.height)
                 and self.camera_cfg.get("fundo_borrado", True) else None)
        vinheta = self._mascara_vinheta()
        preto = Image.new("RGB", (self.width, self.height), (0, 0, 0))
        estalo = int(self.camera_cfg.get("flash_frames", 2))
        inicio = float(evento.get("start") or 0.0)

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
            img = fundo.copy() if fundo is not None else self._fundo().copy()
            img.paste(quadro, canto)
            if vinheta is not None:
                img = Image.composite(preto, img, vinheta)
            self._sobrepor(img, evento, inicio + i / self.fps, i)
            if i < estalo:
                branco = Image.new("RGB", img.size, (255, 255, 255))
                img = Image.blend(img, branco, 0.3 * (1 - i / max(1, estalo)))
            yield img

    def _cena_sem_imagem(self, evento: dict, total: int):
        """A imagem nao existe (ainda). A cena vira tipografia sobre o fundo
        do canal, e o video continua contando a historia."""
        texto = str(evento.get("narracao") or "")
        fonte = fit_font_wrap(texto, self.fonts["black"], int(self.width * 0.86),
                              int(self.ref * 0.075), max_lines=6)
        inicio = float(evento.get("start") or 0.0)
        # Com titulo, a narracao so entra DEPOIS que ele sai: os dois no mesmo
        # lugar da tela viravam uma sopa de letra sobreposta.
        espera = (float(evento.get("titulo_duracao", 2.2))
                  if evento.get("titulo") else 0.0)
        for i in range(total):
            img = self._fundo().copy()
            segundos = i / self.fps
            if segundos >= espera:
                desenho = ImageDraw.Draw(img)
                pulso = 1 + 0.01 * math.sin(segundos * 3)
                entrada = min(1.0, (segundos - espera) / 0.3) if espera else 1.0
                cor = tuple(int(20 + (c - 20) * entrada) for c in (238, 233, 224))
                self._texto_centrado(desenho, texto, fonte, self.height * 0.46,
                                     cor, escala=pulso, stroke=4)
            self._sobrepor(img, evento, inicio + segundos, i, com_legenda=False)
            yield img

    # ------------------------------------------------------------- camadas
    def _sobrepor(self, img: Image.Image, evento: dict, t: float, i: int,
                  com_legenda: bool = True) -> None:
        if evento.get("titulo"):
            self._desenhar_titulo(img, evento, i)
        if com_legenda and self.legenda_cfg.get("ativa", True) and self._palavras:
            # Enquanto o titulo esta na tela, a legenda espera: dois blocos
            # de texto ao mesmo tempo dividem a atencao no gancho.
            calado = (float(evento.get("start", 0.0))
                      + float(evento.get("titulo_duracao", 2.2))
                      if evento.get("titulo") else 0.0)
            self._desenhar_karaoke(img, t, calado_ate=calado)

    def _desenhar_titulo(self, img: Image.Image, evento: dict, i: int) -> None:
        """O titulo sobre a primeira imagem, com cortina, saindo por fade.

        Ele nao pode ficar o video inteiro (cobre a cena) nem virar cartao
        antes dela (o feed rola). Entra, e lido, sai.
        """
        duracao = float(evento.get("titulo_duracao", 2.2))
        segundos = i / self.fps
        if segundos > duracao:
            return
        alfa = 1.0 if segundos < duracao - 0.5 else max(0.0, (duracao - segundos) / 0.5)
        texto = str(evento["titulo"])
        y = float(self.titulo_cfg.get("y", 0.42))
        fonte = fit_font_wrap(texto, self.fonts["black"], int(self.width * 0.88),
                              int(self.ref * float(self.titulo_cfg.get("tamanho", 0.085))),
                              max_lines=4)

        # A cortina existia com alfa 190 (75% de preto) cobrindo 46% da
        # altura. Medido em 01/09/2026: os 2,2 s de titulo eram o trecho MAIS
        # ESCURO do video inteiro (luma 65 contra media 82), e a mesma regiao
        # da imagem clareava 37% assim que ela saia. Ou seja: o gancho — os
        # segundos que decidem se a pessoa fica — era o pior frame do video.
        # O texto ja tem contorno de 6px; a cortina so precisa tirar o
        # brilho do fundo, nao apagar a imagem.
        opacidade = int(self.titulo_cfg.get("cortina", 110))
        faixa = float(self.titulo_cfg.get("cortina_altura", 0.17))
        camada = Image.new("RGBA", (self.width, self.height), (0, 0, 0, 0))
        cortina = ImageDraw.Draw(camada)
        topo = int(self.height * (y - faixa))
        base = int(self.height * (y + faixa + 0.02))
        for linha in range(topo, base):
            centro = (topo + base) / 2
            distancia = abs(linha - centro) / max(1.0, (base - topo) / 2)
            cortina.line([(0, linha), (self.width, linha)],
                         fill=(10, 8, 16,
                               int(opacidade * (1 - distancia ** 2) * alfa)))
        img.paste(Image.alpha_composite(img.convert("RGBA"), camada).convert("RGB"),
                  (0, 0))
        desenho = ImageDraw.Draw(img)
        entrada = min(1.0, i / max(1.0, self.fps * 0.18))
        escala = 1.16 - 0.16 * (1 - (1 - entrada) ** 3)
        cor = tuple(int(c * alfa + 12 * (1 - alfa)) for c in hex_rgb(self.colors["text"]))
        self._texto_centrado(desenho, texto, fonte, self.height * y, cor,
                             escala=escala, stroke=6)

    def _carregar_palavras(self, caminho: Path | None) -> list[dict]:
        if caminho is None or not Path(caminho).is_file():
            return []
        try:
            with open(caminho, encoding="utf-8") as fh:
                dados = json.load(fh)
        except (OSError, ValueError):
            return []
        palavras = [d for d in dados if str(d.get("texto") or "").strip()]
        palavras.sort(key=lambda d: float(d["t0"]))
        # Grupos de N palavras: a legenda mostra o grupo da palavra atual, e
        # nao a frase inteira - frase inteira em vertical vira parede de texto.
        por_linha = max(1, int(self.legenda_cfg.get("palavras_por_linha", 4)))
        grupo, contador, ultima_cena = 0, 0, None
        for palavra in palavras:
            cena = palavra.get("linha")
            if cena != ultima_cena or contador >= por_linha:
                grupo += 1
                contador = 0
                ultima_cena = cena
            palavra["grupo"] = grupo
            contador += 1
        return palavras

    def _grupo_em(self, t: float):
        atual = None
        for palavra in self._palavras:
            if float(palavra["t0"]) - 0.08 <= t:
                atual = palavra
            else:
                break
        if atual is None:
            return None
        grupo = [p for p in self._palavras if p["grupo"] == atual["grupo"]]
        if t > max(float(p["t1"]) for p in grupo) + 0.4:
            return None
        return grupo

    def _desenhar_karaoke(self, img: Image.Image, t: float,
                          calado_ate: float = 0.0) -> None:
        # Enquanto o cartao de titulo esta na tela, a legenda fica fora: dois
        # blocos de texto ao mesmo tempo dividem a atencao justamente nos
        # segundos que decidem a retencao (visto no frame de t=1,0s).
        if t < calado_ate:
            return
        grupo = self._grupo_em(t)
        if not grupo:
            return
        palavras = [str(p["texto"]) for p in grupo]
        # A legenda nao pode entrar no trilho de curtir/comentar/enviar
        # do TikTok, que fica no lado direito exatamente nesta altura.
        # Medido em 01/09/2026: a caixa chegava a x=1017 de 1080 e as
        # ultimas palavras ficavam ATRAS dos botoes.
        margem = float(self.legenda_cfg.get("margem_lateral", 0.17))
        largura_max = int(self.width * max(0.4, 1.0 - 2 * margem))
        tamanho = int(self.ref * float(self.legenda_cfg.get("tamanho", 0.055)))
        espaco = int(tamanho * 0.42)
        fonte = load_font(self.fonts["black"], tamanho)
        larguras = [fonte.getlength(p) for p in palavras]
        total = sum(larguras) + espaco * (len(palavras) - 1)
        while total > largura_max and tamanho > int(self.ref * 0.03):
            tamanho = int(tamanho * 0.92)
            espaco = int(tamanho * 0.42)
            fonte = load_font(self.fonts["black"], tamanho)
            larguras = [fonte.getlength(p) for p in palavras]
            total = sum(larguras) + espaco * (len(palavras) - 1)

        desenho = ImageDraw.Draw(img)
        x = self.width / 2 - total / 2
        y = self.height * float(self.legenda_cfg.get("y", 0.74))
        stroke = max(3, tamanho // 10)
        ativa = hex_rgb(str(self.legenda_cfg.get("cor_ativa", "#ffb703")))
        dita = hex_rgb(str(self.legenda_cfg.get("cor_dita", "#f7f3ea")))
        futura = hex_rgb(str(self.legenda_cfg.get("cor_futura", "#8b8378")))
        # UMA palavra acesa por quadro: a ultima que ja comecou. Testar por
        # intervalo (t0 <= t < t1) acendia duas ao mesmo tempo, porque o fim de
        # uma e o comeco da outra se encavalam nos limites do motor de voz.
        ativo = max((i for i, d in enumerate(grupo) if float(d["t0"]) <= t),
                    default=-1)
        for indice, (palavra, largura, dado) in enumerate(zip(palavras, larguras, grupo)):
            acesa = indice == ativo
            passou = indice < ativo
            if acesa:
                caixa = [x - espaco * 0.35, y - tamanho * 0.18,
                         x + largura + espaco * 0.35, y + tamanho * 1.08]
                desenho.rounded_rectangle(caixa, radius=int(tamanho * 0.22),
                                          fill=ativa)
            desenho.text((x, y), palavra, font=fonte,
                         fill=(20, 16, 12) if acesa else (dita if passou else futura),
                         anchor="la", stroke_width=0 if acesa else stroke,
                         stroke_fill=(12, 10, 18))
            x += largura + espaco

    def _texto_centrado(self, desenho, texto: str, fonte, y: float, cor,
                        escala: float = 1.0, stroke: int = 4) -> None:
        if not texto:
            return
        palavras = texto.split()
        limite = self.width * 0.88
        linhas, atual = [], ""
        for palavra in palavras:
            teste = f"{atual} {palavra}".strip()
            if desenho.textlength(teste, font=fonte) <= limite or not atual:
                atual = teste
            else:
                linhas.append(atual)
                atual = palavra
        if atual:
            linhas.append(atual)
        altura = fonte.size * 1.22
        inicio = y - (len(linhas) - 1) * altura / 2
        for i, linha in enumerate(linhas):
            largura = desenho.textlength(linha, font=fonte)
            desenho.text((self.width / 2, inicio + i * altura), linha, font=fonte,
                         fill=cor, anchor="mm", stroke_width=stroke,
                         stroke_fill=(12, 10, 18))
            del largura
