extends PecaPalco
## HUD PADRAO do palco (desligado no duelo: la o HUD e da edicao em Python ate
## a 16G). Liga com `"hud": true` no job. Desenhado em px da TELA: nome e
## vida de cada lado no topo.

var nomes := ["", ""]
var cores := [Color.WHITE, Color.WHITE]
var hp := [1.0, 1.0]
var tela := Vector2(1080, 1920)


func configurar(dados: Dictionary, ctx: Dictionary) -> void:
	var lista: Array = dados.get("lutadores", [])
	for k in mini(2, lista.size()):
		nomes[k] = str(lista[k].get("rotulo", lista[k].get("nome", "")))
		cores[k] = UtilPalco.cor(lista[k].get("cor_lado", 0xFFFFFF))
	tela = ctx.get("tela", tela)


func atualizar(amostra: Dictionary, _ctx: Dictionary) -> void:
	hp[0] = float(amostra.get("p1", {}).get("hp", 1.0))
	hp[1] = float(amostra.get("p2", {}).get("hp", 1.0))
	queue_redraw()


func _draw() -> void:
	var fonte := ThemeDB.fallback_font
	var margem := tela.x * 0.04
	var larg := tela.x * 0.42
	var alt := tela.y * 0.014
	for k in 2:
		var x := margem if k == 0 else tela.x - margem - larg
		var y := tela.y * 0.06
		draw_rect(Rect2(x, y, larg, alt), Color(0, 0, 0, 0.55), true)
		var cheio := larg * clampf(hp[k], 0.0, 1.0)
		var x_cheio := x if k == 0 else x + larg - cheio
		draw_rect(Rect2(x_cheio, y, cheio, alt), cores[k], true)
		var tam := int(tela.y * 0.02)
		var alinh := HORIZONTAL_ALIGNMENT_LEFT if k == 0 else HORIZONTAL_ALIGNMENT_RIGHT
		draw_string_outline(fonte, Vector2(x, y - tam * 0.4), nomes[k], alinh, larg, tam, 8, Color(0, 0, 0))
		draw_string(fonte, Vector2(x, y - tam * 0.4), nomes[k], alinh, larg, tam, Color.WHITE)
