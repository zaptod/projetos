extends PecaPalco
## Objeto PADRAO (projeteis, orbes, areas, beams, summons, traps, portais).
##
## O palco poe a peca em (x, y) quando a trilha tem posicao; beam e portal
## ficam na origem e desenham pelos pontos fixos (de/ate/pontos, a/b), em
## coordenadas do mundo. Cor: a paleta do ELEMENTO; sem elemento, a cor do
## objeto. Uma peca propria entra como efeitos/objetos/<tipo>/<elemento>.tscn
## ou efeitos/skills/<skill>.tscn.

const PPM_MOTOR := 50.0
# mascara branca CC0 (Kenney light_01), tingida pela paleta do elemento
const TEX_BRILHO := preload("res://biblioteca/efeitos/texturas/brilho.png")

var tipo := "projetil"
var fixos: Dictionary = {}
var paleta: Dictionary = {}
var cor_base := Color.WHITE
var _s: Dictionary = {}
var _ctx: Dictionary = {}
var _rastro: Array[Vector2] = []   # posicoes do mundo (px)


func configurar(dados: Dictionary, _c: Dictionary) -> void:
	fixos = dados
	tipo = str(dados.get("tipo", "projetil"))
	var elemento := str(dados.get("elemento", ""))
	cor_base = UtilPalco.cor(dados.get("cor", 0xFFFFFF))
	if elemento != "" and elemento.to_upper() != "DEFAULT" and UtilPalco.PALETAS.has(elemento.to_upper()):
		paleta = UtilPalco.paleta(elemento)
	else:
		# sem elemento: monta a paleta a partir da cor do objeto
		var c := int(dados.get("cor", 0xFFFFFF))
		paleta = {"core": 0xFFFFFF, "mid": [c, c, c], "outer": [c, c, c], "spark": 0xFFFFFF, "glow": c}
	if tipo in ["projetil", "orbe", "beam"]:
		# energia soma luz: mistura aditiva (o nucleo branco estoura, o halo tinge)
		var mat := CanvasItemMaterial.new()
		mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		material = mat


func atualizar(amostra: Dictionary, ctx: Dictionary) -> void:
	_s = amostra
	_ctx = ctx
	if ctx.get("corte", false):
		_rastro.clear()
	if tipo in ["projetil", "projetil_arma"]:
		_rastro.push_front(position)
		while _rastro.size() > 7:
			_rastro.pop_back()
	queue_redraw()


func _brilho() -> float:
	var estilo: EstiloPalco = _ctx.get("estilo")
	return estilo.brilho if estilo else 0.45


func _c(chave: String, i := 0, alfa := 1.0) -> Color:
	var v = paleta.get(chave, 0xFFFFFF)
	if typeof(v) == TYPE_ARRAY:
		v = v[clampi(i, 0, v.size() - 1)]
	return UtilPalco.cor(v, alfa)


func _draw() -> void:
	if _s.is_empty():
		return
	var M := UtilPalco.PX_POR_M
	var t := float(_ctx.get("t_jogo", 0.0))
	var prog := float(_s.get("prog", 0.0))
	match tipo:
		"projetil", "projetil_arma":
			var r := maxf(0.08, float(_s.get("r", 0.2))) * M
			# rastro
			for k in range(1, _rastro.size()):
				var a := do_mundo(_rastro[k - 1])
				var b := do_mundo(_rastro[k])
				var f := 1.0 - float(k) / _rastro.size()
				draw_line(a, b, _c("outer", 0, 0.55 * f), r * 1.4 * f, true)
			if tipo == "projetil_arma":
				_projetil_arma(r)
			else:
				var halo := r * 5.0
				draw_texture_rect(TEX_BRILHO, Rect2(-Vector2(halo, halo) / 2.0, Vector2(halo, halo)), false, _c("glow", 0, 0.9 * _brilho()))
				draw_circle(Vector2.ZERO, r * 1.25, _c("outer", 0, 0.9), true, -1.0, true)
				draw_circle(Vector2.ZERO, r * 0.9, _c("mid", 0), true, -1.0, true)
				draw_circle(Vector2.ZERO, r * 0.45, _c("core"), true, -1.0, true)
		"orbe":
			var r := maxf(0.06, float(_s.get("r", 0.15))) * M
			var estado := int(_s.get("estado", 0))
			var forte := 1.0 + 0.35 * estado
			var halo := r * 4.5 * forte
			draw_texture_rect(TEX_BRILHO, Rect2(-Vector2(halo, halo) / 2.0, Vector2(halo, halo)), false, _c("glow", 0, 0.8 * _brilho()))
			draw_circle(Vector2.ZERO, r, _c("mid", 1), true, -1.0, true)
			draw_circle(Vector2.ZERO, r * 0.5, _c("core"), true, -1.0, true)
		"area":
			_area(M, t, prog)
		"beam":
			_beam(M, prog)
		"summon":
			_summon(M, t)
		"trap":
			var larg := float(fixos.get("largura", 1.0)) * M
			var alt := float(fixos.get("altura", 1.0)) * M
			draw_set_transform(Vector2.ZERO, deg_to_rad(float(fixos.get("angulo", 0.0))))
			var ret := Rect2(-larg / 2, -alt / 2, larg, alt)
			var hp := clampf(float(_s.get("hp", 1.0)), 0.0, 1.0)
			draw_rect(ret, Color(cor_base.r, cor_base.g, cor_base.b, 0.35 + 0.35 * hp), true)
			draw_rect(ret, cor_base.lightened(0.3), false, 4.0, true)
			draw_set_transform(Vector2.ZERO)
		"portal":
			for chave in ["a", "b"]:
				var p = fixos.get(chave)
				if typeof(p) == TYPE_ARRAY and p.size() == 2:
					var c := do_mundo(Vector2(float(p[0]), float(p[1])) * M)
					var raio := float(fixos.get("raio", 0.65)) * M
					draw_circle(c, raio, Color(0.1, 0.0, 0.2, 0.55), true, -1.0, true)
					draw_arc(c, raio, t * 3.0, t * 3.0 + TAU * 0.8, 40, _c("mid", 0), raio * 0.18, true)
		_:
			draw_circle(Vector2.ZERO, 20.0, cor_base, true, -1.0, true)


func _projetil_arma(r: float) -> void:
	var forma := UtilPalco.slug(str(fixos.get("forma", "")))
	var ang := deg_to_rad(float(_s.get("ang", 0.0)))
	var metal := Color8(205, 208, 218).lerp(cor_base, 0.3)
	var giro := float(_ctx.get("t_jogo", 0.0)) * 18.0
	match forma:
		"shuriken", "estrela":
			var pts := PackedVector2Array()
			for k in 8:
				var a := giro + k * PI / 4.0
				pts.append(Vector2(cos(a), sin(a)) * (r * 1.6 if k % 2 == 0 else r * 0.5))
			draw_colored_polygon(pts, metal)
		"chakram", "anel":
			draw_arc(Vector2.ZERO, r * 1.3, 0, TAU, 32, metal, r * 0.45, true)
		_:
			# flecha / faca / kunai: haste com ponta, orientada pelo angulo
			var d := Vector2(cos(ang), sin(ang))
			var n := Vector2(-d.y, d.x)
			draw_line(-d * r * 2.4, d * r * 0.8, Color8(120, 90, 55), maxf(2.0, r * 0.35), true)
			draw_colored_polygon(PackedVector2Array([d * r * 1.9, d * r * 0.4 + n * r * 0.7, d * r * 0.4 - n * r * 0.7]), metal)


func _area(M: float, t: float, prog: float) -> void:
	var r := maxf(0.05, float(_s.get("r", fixos.get("raio_max", 1.0)))) * M
	var ativa := int(_s.get("ativ", 1)) == 1
	var some := clampf((1.0 - prog) / 0.15, 0.0, 1.0)
	if ativa:
		var pulso := 0.85 + 0.15 * sin(t * 12.0)
		draw_circle(Vector2.ZERO, r, _c("outer", 1, (0.30 + 0.10 * _brilho()) * some), true, -1.0, true)
		draw_circle(Vector2.ZERO, r * 0.7 * pulso, _c("mid", 1, 0.35 * some), true, -1.0, true)
		draw_arc(Vector2.ZERO, r, 0, TAU, 64, _c("mid", 0, 0.9 * some), maxf(4.0, r * 0.05), true)
	else:
		# aviso (telegraph): anel tracejado que fecha
		var segs := 24
		for k in segs:
			if k % 2 == 0:
				var a0 := k * TAU / segs + t
				draw_arc(Vector2.ZERO, r, a0, a0 + TAU / segs, 6, _c("mid", 0, 0.8), maxf(3.0, r * 0.035), true)
		draw_circle(Vector2.ZERO, r, _c("outer", 2, 0.12), true, -1.0, true)
	var pilares = fixos.get("pilares")
	if typeof(pilares) == TYPE_ARRAY:
		var rp := float(fixos.get("raio_pilar", 0.4)) * M
		for p in pilares:
			var c := do_mundo(Vector2(float(p[0]), float(p[1])) * M)
			draw_circle(c, rp, _c("mid", 0, 0.85 * some), true, -1.0, true)
			draw_circle(c, rp * 0.5, _c("core", 0, some), true, -1.0, true)


func _beam(M: float, prog: float) -> void:
	var pts := PackedVector2Array()
	var pontos = fixos.get("pontos")
	if typeof(pontos) == TYPE_ARRAY and pontos.size() >= 2:
		for p in pontos:
			pts.append(do_mundo(Vector2(float(p[0]), float(p[1])) * M))
	else:
		var de = fixos.get("de", [0, 0])
		var ate = fixos.get("ate", [0, 0])
		pts.append(do_mundo(Vector2(float(de[0]), float(de[1])) * M))
		pts.append(do_mundo(Vector2(float(ate[0]), float(ate[1])) * M))
	# `larg` esta em px da tela de referencia do motor (50 px/m)
	var larg := maxf(0.08, float(_s.get("larg", 8.0)) / PPM_MOTOR) * M
	var some := clampf(1.0 - prog, 0.15, 1.0)
	draw_polyline(pts, _c("glow", 0, 0.3 * _brilho() * some), larg * 3.0, true)
	draw_polyline(pts, _c("outer", 0, 0.9 * some), larg * 1.4, true)
	draw_polyline(pts, _c("core", 0, some), larg * 0.5, true)


func _summon(M: float, t: float) -> void:
	var r := float(fixos.get("raio", 0.8)) * M
	var ang := deg_to_rad(float(_s.get("ang", 0.0)))
	draw_circle(Vector2.ZERO, r * 1.6, _c("glow", 0, 0.18 * _brilho()), true, -1.0, true)
	draw_circle(Vector2.ZERO, r, _c("mid", 1), true, -1.0, true)
	draw_arc(Vector2.ZERO, r, 0, TAU, 48, _c("outer", 1), maxf(3.0, r * 0.06), true)
	var d := Vector2(cos(ang), sin(ang))
	var n := Vector2(-d.y, d.x)
	for lado: float in [-1.0, 1.0]:
		var olho := d * r * 0.35 + n * r * 0.3 * lado
		draw_circle(olho, r * 0.17, Color.WHITE, true, -1.0, true)
		draw_circle(olho + d * r * 0.06, r * 0.08, Color8(20, 20, 34), true, -1.0, true)
	var hp := clampf(float(_s.get("hp", 1.0)), 0.0, 1.0)
	if hp < 0.999:
		draw_arc(Vector2.ZERO, r * 1.2, -PI / 2, -PI / 2 + TAU * hp, 32, Color8(120, 255, 140, 200), maxf(3.0, r * 0.07), true)
