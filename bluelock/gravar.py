# -*- coding: utf-8 -*-
"""Grava uma partida do Blue Lock em mp4 SEM mexer no repositorio do Adrian.

COMO. O repositorio dele ja traz o caminho: os `scripts/check-*.py` abrem o
Vite, importam `/src/field.ts` e `/src/simulation.ts` dentro da pagina e
desenham o renderer de producao quadro a quadro (o `check-character-motion`
faz assim o mp4 dele, com "two actual 60 Hz simulation ticks per 30 fps
output frame"). Este gravador faz o mesmo, de FORA:

  1. sobe o Vite do espelho (`node node_modules/vite/bin/vite.js`, porta
     propria; o Vite so escreve no `node_modules/.vite`, ignorado pelo git);
  2. abre o Chrome headless (Playwright, canal `chrome`) na pagina dele e
     esconde o laboratorio;
  3. monta uma `Simulation` (formato, elenco, semente, goleiros) e um
     `Field` do tamanho do video;
  4. a cada quadro: `60/fps` passos de fisica, `field.draw(...)`, JPEG do
     canvas — o tempo de parede nao muda o resultado (deterministico na
     mesma versao do Chrome);
  5. manda os quadros ao ffmpeg, com faixa de audio muda (o `concat -c copy`
     da fabrica precisa dela), e escreve o JSON da partida ao lado.

A camera `bola` e nossa: troca o `updateCamera` da instancia do `Field` (so
na pagina, nada no repositorio) por um enquadramento que segue a bola com
suavizacao — a camera `follow` dele segue um JOGADOR, e o video vertical
precisa da jogada.

E PESADO: recusa com o League of Legends aberto e de :19 a :55 das horas de
postagem (`comum.pode_pesado`), a menos de `--forcar`; e segura a trava
`bluelock_espelho`, para o vigia nao puxar a main com o Vite servindo.

    python -m bluelock.gravar --saida E:\\tmp_pytest\\bluelock\\prova.mp4 --segundos 20
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from . import comum

PERSONAGENS = ("isagi", "bachira", "kunigami", "chigiri", "nagi", "reo", "barou", "rin", "reference")
CAMERAS = ("bola", "overview", "follow", "character")
QUALIDADES = ("performance", "balanced", "high")
AZUL_PADRAO = ("isagi", "bachira", "nagi")
VERMELHO_PADRAO = ("rin", "barou", "reo")
QUADROS_POR_CHAMADA = 10
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

MONTAR = r"""async (cfg) => {
 const {Field} = await import('/src/field.ts');
 const {Simulation, DEFAULT_MECHANICS, rosterIds} = await import('/src/simulation.ts');
 const {characterProfile} = await import('/src/characters.ts');
 const app = document.querySelector('#app'); if (app) app.style.cssText = 'position:fixed;left:-9999px;top:0;visibility:hidden';
 document.body.style.cssText = 'margin:0;background:#000;overflow:hidden';
 const host = document.createElement('div');
 host.style.cssText = `position:fixed;left:0;top:0;width:${cfg.largura}px;height:${cfg.altura}px`;
 document.body.append(host);
 const field = new Field(host, () => {});
 field.setQuality(cfg.qualidade);
 field.setCamera(cfg.camera === 'bola' ? 'follow' : cfg.camera);
 const ids = rosterIds(cfg.formato), characters = {}, characterModules = {};
 for (const id of ids) {
  const lista = id.startsWith('blue') ? cfg.azul : cfg.vermelho, indice = id.includes('-') ? Number(id.split('-')[1]) - 1 : 0;
  const quem = lista[indice];
  characters[id] = quem;
  if (cfg.tudo) characterModules[id] = Object.fromEntries(characterProfile(quem).modules.map(m => [m.id, !m.restriction]));
 }
 const sim = new Simulation(DEFAULT_MECHANICS, undefined, cfg.semente, {detailedBodies: true, teamSize: cfg.formato,
  characters, characterModules, goalkeepers: {blue: cfg.goleiros, red: cfg.goleiros}});
 const errados = ids.filter(id => sim.characters[id] !== characters[id]);
 if (errados.length) throw new Error('personagem recusado pelo simulador: ' + errados.map(id => id + '=' + characters[id]).join(', '));
 if (cfg.camera === 'bola') {
  // So nesta pagina: a instancia passa a seguir a BOLA, suavizada, em vez de um jogador.
  const vista = {x: 0, z: 0, pronta: false, placar: ''};
  const k = 1 - Math.exp(-cfg.suavidade / cfg.fps), margemX = sim.mechanics.width / 2 - 3, margemZ = sim.mechanics.height / 2 - 4;
  field.updateCamera = function (s) {
   const bola = s.ball.position, placar = JSON.stringify(s.score);
   const alvoX = Math.max(-margemX, Math.min(margemX, bola.x)), alvoZ = Math.max(-margemZ, Math.min(margemZ, bola.y));
   if (!vista.pronta || placar !== vista.placar) { vista.x = alvoX; vista.z = alvoZ; vista.pronta = true; vista.placar = placar; }
   else { vista.x += (alvoX - vista.x) * k; vista.z += (alvoZ - vista.z) * k; }
   this.camera.position.set(vista.x, 14, vista.z + 22); this.camera.lookAt(vista.x, 0.75, vista.z);
  };
 }
 for (let i = 0; i < Math.round(cfg.pular * 60); i++) sim.step();
 const gl = field.renderer.getContext(), info = gl.getExtension('WEBGL_debug_renderer_info');
 window.__bl = {field, sim, passos: Math.round(60 / cfg.fps), q: cfg.jpeg};
 return {ids, characters: sim.characters, goleiros: cfg.goleiros, tempo: sim.time,
  gpu: info ? gl.getParameter(info.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
  canvas: [field.renderer.domElement.width, field.renderer.domElement.height]};
}"""

QUADROS = r"""(n) => {
 const L = window.__bl, out = [];
 for (let i = 0; i < n; i++) {
  if (L.sim.finished) break;
  for (let k = 0; k < L.passos; k++) L.sim.step();
  L.field.draw(L.sim, L.sim.ball.owner ?? 'blue', false, false);
  out.push(L.field.renderer.domElement.toDataURL('image/jpeg', L.q));
 }
 return {quadros: out, tempo: L.sim.time, placar: {...L.sim.score}, fim: L.sim.finished};
}"""

EVENTOS = r"""() => {
 const s = window.__bl.sim;
 return {eventos: s.events.map(e => [e.time, e.kind, e.message]), placar: {...s.score}, tempo: s.time, fim: s.finished};
}"""


def _porta_livre(porta: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", porta)) != 0


def subir_vite(espelho: Path, porta: int, log: Path):
    vite = espelho / "node_modules" / "vite" / "bin" / "vite.js"
    if not vite.is_file():
        raise RuntimeError(f"sem {vite}: rode `npm ci` no espelho (o vigia faz isso quando o lock muda)")
    if not _porta_livre(porta):
        raise RuntimeError(f"a porta {porta} já está ocupada; use --porta")
    node = shutil.which("node") or "node"
    saida = open(log, "w", encoding="utf-8")
    proc = subprocess.Popen([node, str(vite), "--host", "127.0.0.1", "--port", str(porta), "--strictPort"],
                            cwd=str(espelho), stdout=saida, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
    url = f"http://127.0.0.1:{porta}/"
    prazo = time.monotonic() + 90
    while time.monotonic() < prazo:
        if proc.poll() is not None:
            raise RuntimeError(f"o Vite saiu com {proc.returncode}; veja {log}")
        try:
            with urllib.request.urlopen(url, timeout=3) as resposta:
                if resposta.status == 200:
                    return proc, url, saida
        except OSError:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError(f"o Vite não respondeu em 90 s; veja {log}")


def comando_ffmpeg(saida: Path, fps: int) -> list[str]:
    return ["ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg",
            "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-shortest",
            "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(saida)]


def config_da_pagina(args) -> dict:
    largura, altura = (int(x) for x in args.resolucao.lower().split("x"))
    azul = [p.strip() for p in args.azul.split(",") if p.strip()]
    vermelho = [p.strip() for p in args.vermelho.split(",") if p.strip()]
    for lado, lista in (("azul", azul), ("vermelho", vermelho)):
        if len(lista) < args.formato:
            raise ValueError(f"o time {lado} tem {len(lista)} personagem(ns) para um {args.formato}x{args.formato}")
        desconhecidos = [p for p in lista if p not in PERSONAGENS]
        if desconhecidos:
            raise ValueError(f"personagem desconhecido no {lado}: {', '.join(desconhecidos)} "
                             f"(conhecidos: {', '.join(PERSONAGENS)})")
    if 60 % args.fps:
        raise ValueError("--fps precisa dividir 60 (30, 20, 15...): cada quadro é um número inteiro de passos")
    return {"largura": largura, "altura": altura, "formato": args.formato, "azul": azul[:args.formato],
            "vermelho": vermelho[:args.formato], "semente": args.semente, "goleiros": not args.sem_goleiros,
            "camera": args.camera, "qualidade": args.qualidade, "fps": args.fps, "pular": args.pular,
            "tudo": not args.so_basico, "suavidade": 3.0, "jpeg": 0.92}


def gravar(args) -> dict:
    espelho = Path(args.espelho)
    saida = Path(args.saida)
    resultado_json = Path(args.resultado) if args.resultado else saida.with_suffix(".json")
    cfg = config_da_pagina(args)
    if not args.forcar:
        pode, motivo = comum.pode_pesado()
        if not pode:
            return {"sucesso": False, "motivo": f"recusado: {motivo} (use --forcar se for de propósito)"}
    from builds import travas
    from playwright.sync_api import sync_playwright
    saida.parent.mkdir(parents=True, exist_ok=True)
    inicio = time.monotonic()
    with travas.trava("bluelock_espelho") as minha:
        if not minha:
            return {"sucesso": False, "motivo": "o espelho está ocupado (o vigia está puxando ou testando)"}
        commit = subprocess.run(["git", "-C", str(espelho), "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True, creationflags=NO_WINDOW).stdout.strip()
        vite, url, log_vite = subir_vite(espelho, args.porta, comum.pasta() / "vite_gravacao.txt")
        ffmpeg = None
        try:
            with sync_playwright() as p:
                opcoes = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] if args.software else \
                         ["--enable-gpu", "--ignore-gpu-blocklist", "--use-angle=d3d11"]
                browser = p.chromium.launch(channel="chrome", headless=True, args=opcoes)
                pagina = browser.new_page(viewport={"width": cfg["largura"], "height": cfg["altura"]},
                                          device_scale_factor=1)
                erros = []
                pagina.on("pageerror", lambda erro: erros.append(str(erro)))
                pagina.goto(url, wait_until="networkidle", timeout=120000)
                montado = pagina.evaluate(MONTAR, cfg)
                ffmpeg = subprocess.Popen(comando_ffmpeg(saida, cfg["fps"]), stdin=subprocess.PIPE,
                                          stderr=subprocess.PIPE, creationflags=NO_WINDOW)
                alvo = int(round(args.segundos * cfg["fps"]))
                feitos, fim = 0, False
                while feitos < alvo and not fim:
                    lote = pagina.evaluate(QUADROS, min(QUADROS_POR_CHAMADA, alvo - feitos))
                    for dado in lote["quadros"]:
                        ffmpeg.stdin.write(base64.b64decode(dado.split(",", 1)[1]))
                    feitos += len(lote["quadros"])
                    fim = lote["fim"]
                    if args.progresso and feitos % (cfg["fps"] * 5) < QUADROS_POR_CHAMADA:
                        print(f"[bluelock-gravar] {feitos}/{alvo} quadros, jogo {lote['tempo']:.1f} s, "
                              f"placar {lote['placar']}", flush=True)
                partida = pagina.evaluate(EVENTOS)
                browser.close()
            ffmpeg.stdin.close()
            erro_ffmpeg = ffmpeg.stderr.read().decode("utf-8", "replace").strip()
            ffmpeg.wait(timeout=300)
        finally:
            if ffmpeg and ffmpeg.poll() is None:
                ffmpeg.kill()
            vite.kill()
            log_vite.close()
    t0 = cfg["pular"]
    duracao_video = feitos / cfg["fps"]
    # `sim.events` guarda o mais recente PRIMEIRO; o contrato e em ordem de tempo
    eventos = sorted([round(t - t0, 3), tipo, texto] for t, tipo, texto in partida["eventos"]
                     if t0 <= t <= t0 + duracao_video
                     and tipo in ("goal", "shot", "save", "pass", "contact", "end"))
    resultado = {
        "sucesso": ffmpeg.returncode == 0 and feitos > 0 and not erros,
        "jogo": "blue-lock", "commit_do_jogo": commit, "formato": f"{cfg['formato']}x{cfg['formato']}",
        "semente": cfg["semente"], "personagens": montado["characters"], "goleiros": cfg["goleiros"],
        "camera": cfg["camera"], "resolucao": [cfg["largura"], cfg["altura"]], "fps": cfg["fps"],
        "pular_s": cfg["pular"], "duracao_video": duracao_video, "quadros": feitos,
        "tempo_de_jogo_no_fim": round(partida["tempo"], 3), "placar": partida["placar"],
        "gols_em_video": [e[0] for e in eventos if e[1] == "goal"],
        "eventos": eventos, "gpu": montado["gpu"], "canvas": montado["canvas"],
        "erros_da_pagina": erros, "erro_ffmpeg": erro_ffmpeg,
        "tempo_de_parede_s": round(time.monotonic() - inicio, 1),
        "gravado_em": datetime.now().isoformat(timespec="seconds"), "arquivo": str(saida.resolve()),
    }
    resultado_json.parent.mkdir(parents=True, exist_ok=True)
    resultado_json.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bluelock.gravar", description=__doc__.split("\n")[0])
    parser.add_argument("--saida", required=True, help="o .mp4")
    parser.add_argument("--resultado", help="o .json (padrão: ao lado do mp4)")
    parser.add_argument("--espelho", default=str(comum.ESPELHO))
    parser.add_argument("--semente", type=int, default=42)
    parser.add_argument("--formato", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--azul", default=",".join(AZUL_PADRAO))
    parser.add_argument("--vermelho", default=",".join(VERMELHO_PADRAO))
    parser.add_argument("--sem-goleiros", action="store_true")
    parser.add_argument("--so-basico", action="store_true",
                        help="não liga 'Ativar tudo do personagem' (fica nas épocas iniciais)")
    parser.add_argument("--camera", choices=CAMERAS, default="bola")
    parser.add_argument("--resolucao", default="1080x1920")
    parser.add_argument("--qualidade", choices=QUALIDADES, default="high")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--segundos", type=float, default=20.0, help="de vídeo (= de jogo, a 1x)")
    parser.add_argument("--pular", type=float, default=0.0, help="segundos de jogo antes do 1º quadro")
    parser.add_argument("--porta", type=int, default=5199)
    parser.add_argument("--software", action="store_true", help="WebGL por SwiftShader (sem GPU)")
    parser.add_argument("--forcar", action="store_true", help="ignora a janela das postagens e o LoL")
    parser.add_argument("--progresso", action="store_true")
    args = parser.parse_args(argv)
    try:
        resultado = gravar(args)
    except (ValueError, RuntimeError) as exc:
        resultado = {"sucesso": False, "motivo": str(exc)}
    print(json.dumps({k: v for k, v in resultado.items() if k != "eventos"}, ensure_ascii=False))
    return 0 if resultado.get("sucesso") else 1


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main(sys.argv[1:]))
