extends "res://nucleo/peca_reserva.gd"
## Arma sem folha: retangulo neutro entre empunhadura e ponta da timeline.

var desenha_comprimento := true

func configurar(_dados: Dictionary, _ctx: Dictionary) -> void:
	categoria = "armas"

func atualizar(amostra: Dictionary, _ctx: Dictionary) -> void:
	comprimento_ref = maxf(1.0, float(amostra.get("_comprimento_px", 100.0)))
	queue_redraw()

func gatilho(_nome: String) -> void:
	pass
