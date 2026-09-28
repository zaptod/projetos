extends Node2D
## A reserva EMBUTIDA: entra quando nem o `_padrao` da categoria existe. Um
## marcador magenta, feio de proposito: aparece no video e no relatorio, e
## nada some da tela calado.

# @export: so o que e exportado sobrevive ao PackedScene.pack().
@export var categoria := ""
@export var raio_ref: float = 100.0
@export var comprimento_ref: float = 100.0


func _draw() -> void:
	var cor := Color(1.0, 0.0, 1.0, 0.85)
	if categoria == "armas":
		draw_line(Vector2.ZERO, Vector2(comprimento_ref, 0), cor, 10.0, true)
	else:
		draw_circle(Vector2.ZERO, raio_ref * 0.5, cor, false, 8.0, true)
		draw_line(Vector2(-raio_ref * 0.35, -raio_ref * 0.35), Vector2(raio_ref * 0.35, raio_ref * 0.35), cor, 8.0, true)
		draw_line(Vector2(-raio_ref * 0.35, raio_ref * 0.35), Vector2(raio_ref * 0.35, -raio_ref * 0.35), cor, 8.0, true)
