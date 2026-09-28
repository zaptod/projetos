extends PecaPalco
## A arena PADRAO, desenhada a partir do cabecalho `arena` da timeline:
## chao (retangular ou circular), piso com juntas, paredes, borda e os
## obstaculos (pilar = cilindro visto de cima, o resto = bloco).
##
## Uma arena propria entra como arenas/<nome>.tscn (o nome da arena no jogo,
## ex. "salao_da_torre.tscn") ou arenas/temas/<tema>.tscn. Ela recebe o mesmo
## cabecalho em configurar() e o evento "obstaculo" quando um quebra.

## Chao provisorio CC0 (Poly Haven stone_tiles_02, dessaturado e escurecido:
## "chao que nao briga" com as bolinhas). A arena pintada por IA (16F) entra
## como arenas/<nome>.tscn e vence esta.
const TEX_CHAO := preload("res://biblioteca/arenas/texturas/pedra.jpg")
## metros de chao que uma repeticao da textura cobre
const METROS_POR_LADRILHO := 3.0

var arena: Dictionary = {}
var quebrados := {}


func configurar(dados: Dictionary, _ctx: Dictionary) -> void:
	arena = dados
	texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
	queue_redraw()


func _chao(ret: Rect2, tom: Color) -> void:
	var escala := METROS_POR_LADRILHO * UtilPalco.PX_POR_M / float(TEX_CHAO.get_width())
	draw_set_transform(ret.position, 0.0, Vector2(escala, escala))
	draw_texture_rect(TEX_CHAO, Rect2(Vector2.ZERO, ret.size / escala), true, tom.lerp(Color.WHITE, 0.55))
	draw_set_transform(Vector2.ZERO)


func evento(tipo: String, dados: Dictionary, _ctx: Dictionary) -> void:
	if tipo == "obstaculo":
		quebrados[int(dados.get("indice", -1))] = true
		queue_redraw()


func _v(par, padrao := Vector2.ZERO) -> Vector2:
	if typeof(par) == TYPE_ARRAY and par.size() >= 2:
		return Vector2(float(par[0]), float(par[1])) * UtilPalco.PX_POR_M
	return padrao


func _draw() -> void:
	if arena.is_empty():
		return
	var M := UtilPalco.PX_POR_M
	var chao := UtilPalco.cor(arena.get("cor_chao", 0x262626))
	var parede := UtilPalco.cor(arena.get("cor_parede", 0x4E4E4E))
	var borda := UtilPalco.cor(arena.get("cor_borda", 0x969696))
	var esp := maxf(0.15, float(arena.get("espessura_parede", 0.3))) * M
	if str(arena.get("formato", "retangular")) == "circular" and arena.get("raio") != null:
		var c := _v(arena.get("centro"))
		var r := float(arena.get("raio")) * M
		if arena.get("tem_paredes", true):
			draw_circle(c, r + esp, parede, true, -1.0, true)
		draw_circle(c, r, chao, true, -1.0, true)
		for k in range(1, int(r / M)):
			draw_arc(c, k * M, 0, TAU, 64, Color(1, 1, 1, 0.045), 2.0, true)
		draw_arc(c, r, 0, TAU, 128, borda, 5.0, true)
	else:
		var a := _v(arena.get("min"))
		var b := _v(arena.get("max"), a + Vector2(10, 10) * M)
		var ret := Rect2(a, b - a)
		if arena.get("tem_paredes", true):
			draw_rect(ret.grow(esp), parede, true)
			# face interna da parede um pouco mais clara: le como altura
			draw_rect(ret.grow(esp * 0.35), parede.lightened(0.12), true)
		draw_rect(ret, chao, true)
		_chao(ret, chao)
		# sombra interna junto a parede
		draw_rect(ret, Color(0, 0, 0, 0.35), false, esp * 0.6)
		draw_rect(ret, borda, false, 5.0)
	var obst: Array = arena.get("obstaculos", [])
	for k in obst.size():
		_obstaculo(obst[k], quebrados.has(k))


func _obstaculo(o: Dictionary, quebrado: bool) -> void:
	var M := UtilPalco.PX_POR_M
	var c := Vector2(float(o.get("x", 0)), float(o.get("y", 0))) * M
	var tam := Vector2(float(o.get("largura", 1)), float(o.get("altura", 1))) * M
	var cor := UtilPalco.cor(o.get("cor", 0x646464))
	var tipo := str(o.get("tipo", ""))
	if tipo in ["tapete", "lava", "fogo", "gelo"]:
		draw_rect(Rect2(c - tam / 2, tam), cor, true)
		return
	if quebrado or tipo.ends_with("_quebrado") and tipo != "pilar_quebrado":
		draw_rect(Rect2(c + Vector2(-tam.x / 2, tam.y * 0.1), Vector2(tam.x, tam.y * 0.4)), cor.darkened(0.2), true)
		return
	# sombra de contato
	draw_set_transform(c + Vector2(0, tam.y * 0.5), 0.0, Vector2(1.0, 0.32))
	draw_circle(Vector2.ZERO, tam.x * 0.55, Color(0, 0, 0, 0.3), true, -1.0, true)
	draw_set_transform(Vector2.ZERO)
	if tipo.begins_with("pilar"):
		draw_set_transform(c, 0.0, Vector2(1.0, tam.y / maxf(tam.x, 1.0)))
		draw_circle(Vector2.ZERO, tam.x / 2, cor, true, -1.0, true)
		draw_circle(Vector2(0, -tam.x * 0.12), tam.x * 0.36, cor.lightened(0.12), true, -1.0, true)
		draw_arc(Vector2.ZERO, tam.x / 2, 0, TAU, 48, cor.darkened(0.45), 4.0, true)
		draw_set_transform(Vector2.ZERO)
	else:
		var ret := Rect2(c - tam / 2, tam)
		draw_rect(ret, cor, true)
		draw_rect(Rect2(ret.position, Vector2(ret.size.x, ret.size.y * 0.3)), cor.lightened(0.12), true)
		draw_rect(ret, cor.darkened(0.45), false, 4.0)
