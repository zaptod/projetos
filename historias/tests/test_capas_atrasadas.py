"""`ferramentas/capas_atrasadas.py`: a fila das capas que voltaram com 403
antes da verificacao do canal "historinhas" (05/10/2026)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "ferramentas" / "capas_atrasadas.py"


def _modulo():
    # O script poe `random_builds/` no sys.path[0]. Sem devolver o sys.path,
    # todo `import main` depois deste arquivo na suite pegava o main.py dos
    # builds (test_rumos: "module 'main' has no attribute 'cmd_auto'",
    # 15/10/2026).
    antes = list(sys.path)
    spec = importlib.util.spec_from_file_location("capas_atrasadas_teste", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path[:] = antes
    return mod


def test_fila_e_do_mais_novo_ao_mais_velho_sem_repetir_e_sem_as_feitas(tmp_path, monkeypatch):
    mod = _modulo()
    monkeypatch.setattr(mod, "OUTPUTS", tmp_path)
    ledger = tmp_path / "publicados.jsonl"
    linhas = [
        {"plataforma": "youtube", "youtube_id": "AAAAAAAAAAA", "video_id": "historia_00001:celular:p01",
         "quando": "2026-10-01T10:00:00"},
        {"plataforma": "tiktok", "video_id": "historia_00001:celular:p01", "quando": "2026-10-01T10:01:00"},
        {"plataforma": "youtube", "youtube_id": "BBBBBBBBBBB", "video_id": "historia_00002:celular:p03",
         "quando": "2026-10-03T10:00:00"},
        {"plataforma": "youtube", "youtube_id": "CCCCCCCCCCC", "video_id": "historia_00002:celular:p04",
         "quando": "2026-10-04T10:00:00"},
        {"plataforma": "youtube", "youtube_id": "publicado", "video_id": "historia_00003:celular:p01",
         "quando": "2026-10-05T10:00:00"},
        {"plataforma": "youtube", "youtube_id": "DDDDDDDDDDD", "video_id": "generation_00090",
         "quando": "2026-10-05T11:00:00"},
    ]
    ledger.write_text("\n".join(json.dumps(x) for x in linhas) + "\nlixo\n", encoding="utf-8")

    fila = mod.pendentes(ledger, feitas={"CCCCCCCCCCC": {}})

    assert [v["youtube_id"] for v in fila] == ["BBBBBBBBBBB", "AAAAAAAAAAA"]
    assert fila[0]["capa"] == tmp_path / "historia_00002" / "capa_p03.jpg"
