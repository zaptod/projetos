extends Node2D
## Evento sem folha nao recebe arte de reserva.

var idade := 0.0
var vida := 0.35

func configurar(evento: Dictionary, _ctx: Dictionary) -> void:
	vida = 0.6 if str(evento.get("tipo", "")) == "ko" else 0.35

func atualizar(_amostra: Dictionary, ctx: Dictionary) -> void:
	idade += float(ctx.get("dt_mundo", 0.0))
	if idade >= vida:
		queue_free()
