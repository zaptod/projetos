extends Node2D
## A reserva EMBUTIDA: entra quando nem o `_padrao` da categoria existe. Um
## marcador neutro: a ausencia de arte nunca inventa um visual do jogo.

# @export: so o que e exportado sobrevive ao PackedScene.pack().
@export var categoria := ""
@export var raio_ref: float = 100.0
@export var comprimento_ref: float = 100.0


func _draw() -> void:
	var cor := Color(0.55, 0.55, 0.55, 0.9)
	if categoria == "armas":
		draw_rect(Rect2(0, -comprimento_ref * 0.08, comprimento_ref, comprimento_ref * 0.16), cor, true)
	elif categoria != "efeitos":
		draw_circle(Vector2.ZERO, raio_ref * 0.5, cor, true, -1.0, true)
