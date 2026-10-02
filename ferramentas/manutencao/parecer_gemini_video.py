"""Pede ao Gemini, pelo navegador configurado, um parecer textual sobre um MP4."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
PERGUNTA_PADRAO = """PEDIDO DE TEXTO. Nao crie nem gere video ou imagem: assista ao video anexado e responda so com texto. Liste defeitos concretos que voce ve, com segundo aproximado e por que atrapalham quem assiste no celular. Nao elogie, nao invente defeitos e nao comente audio."""


def argumentos() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", type=Path, help="arquivo MP4 a anexar")
    p.add_argument("pergunta", nargs="?", default=PERGUNTA_PADRAO, help="pergunta enviada ao Gemini")
    p.add_argument("--saida", type=Path, default=RAIZ / "outputs/parecer_gemini",
                   help="diretorio para resultados.json e capturas")
    return p.parse_args()


def principal() -> int:
    a = argumentos()
    if not a.video.is_file():
        print(f"video nao encontrado: {a.video}", file=sys.stderr)
        return 2
    # A dependencia e importada apenas ao executar; --help continua seguro e offline.
    sys.path.insert(0, str(RAIZ / "historias"))
    from contos.llm.cliente import abrir_cliente
    a.saida.mkdir(parents=True, exist_ok=True)
    arquivo = a.saida / "resultados.json"
    try:
        resultados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        resultados = []
    rec = {"video": str(a.video), "pergunta": a.pergunta, "inicio": f"{datetime.now():%H:%M:%S}"}
    inicio = time.monotonic()
    try:
        with abrir_cliente("gemini", esperar=300.0, papel="diagnostico", ref=a.video.parent.name,
                           canal="builds") as cli:
            cli.abrir(novo_chat=True)
            rec["modelo"] = cli.modelo_atual
            rec["duracao_vista"] = cli.anexar_video(a.video, espera=600)
            cli.enviar(a.pergunta)
            rec["resposta"] = cli.esperar_resposta(timeout=840, desistir_calado=830)
    except Exception as exc:  # noqa: BLE001
        rec["erro"] = f"{type(exc).__name__}: {exc}"[:400]
    rec["segundos"] = round(time.monotonic() - inicio)
    resultados.append(rec)
    arquivo.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(rec.get("resposta") or rec.get("erro") or "sem resposta")
    return 0 if "resposta" in rec else 1


if __name__ == "__main__":
    raise SystemExit(principal())
