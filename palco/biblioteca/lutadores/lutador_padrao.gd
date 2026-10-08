extends "res://nucleo/peca_reserva.gd"
## Lutador sem folha: marcador neutro. A timeline continua dona da posicao.

func configurar(dados: Dictionary, _ctx: Dictionary) -> void:
	categoria = "lutadores"
	raio_ref = float(dados.get("raio_corpo", 0.85)) * UtilPalco.PX_POR_M

func atualizar(amostra: Dictionary, _ctx: Dictionary) -> void:
	visible = (int(amostra.get("flags", 0)) & (1 << 16)) == 0
	queue_redraw()

func evento(_tipo: String, _dados: Dictionary, _ctx: Dictionary) -> void:
	pass
