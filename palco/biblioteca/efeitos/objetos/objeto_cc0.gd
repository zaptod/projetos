extends "res://biblioteca/efeitos/objetos/objeto_padrao.gd"
## Objeto com ARTE CC0 por (tipo x elemento): projetil, area e beam.
##
## As cenas `efeitos/objetos/<tipo>/<elemento>.tscn` e `<tipo>/_padrao.tscn`
## sao este script com texturas diferentes (geradas por
## `main.py palco efeitos-cc0` a partir do catalogo CC0). Para trocar a arte
## de um par: abra a cena no editor e troque a textura no inspetor. Para uma
## skill so: salve uma copia em efeitos/skills/<skill>.tscn.
##
## As texturas sao mascaras BRANCAS: a cor vem da paleta do ELEMENTO
## (UtilPalco.PALETAS). Tudo anda pelo tempo de JOGO (congela no hitstop) e o
## tamanho vem da timeline: o raio do projetil e da area e o da hitbox, e a
## borda da area e desenhada no raio exato. Campo vazio = o desenho da 16D.

@export_group("Arte (CC0)")
## projetil: o centro, que gira
@export var nucleo: Texture2D
## projetil: o brilho em volta
@export var halo: Texture2D
## area: o chao da area, que gira
@export var preenchimento: Texture2D
## area: o anel da borda
@export var anel: Texture2D
## beam: o pedaco de energia que corre ao longo do feixe
@export var corpo: Texture2D
## beam: o que brilha na ponta
@export var ponta: Texture2D

@export_group("Movimento e cor")
## rad/s de jogo do nucleo (projetil) ou do preenchimento (area)
@export var giro: float = 2.0
@export var halo_giro: float = 0.0
## largura do nucleo em raios do projetil
@export var nucleo_escala: float = 2.6
@export var halo_escala: float = 5.0
## luz somada (brilha no escuro); false = tinta normal (trevas, sangue, void)
@export var aditivo: bool = true
## CAOS: a segunda textura gira ao contrario na outra cor da paleta
@export var duas_cores: bool = false
## VOID: um buraco escuro no centro
@export var nucleo_escuro: bool = false
## TEMPO: dois ponteiros de relogio
@export var ponteiros: bool = false
## GRAVITACAO: o anel da area encolhe (puxa) em vez de pulsar
@export var encolhe: bool = false
## chave da paleta do nucleo: core, mid, outer, spark, glow
@export var cor_nucleo: String = "mid"


func configurar(dados: Dictionary, c: Dictionary) -> void:
	super(dados, c)
	# o corpo do beam se repete ao longo do feixe (e corre, pelo tempo de jogo)
	texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
	if tipo in ["projetil", "area", "beam"]:
		if aditivo:
			var mat := CanvasItemMaterial.new()
			mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
			material = mat
		else:
			material = null


func _tex(tex: Texture2D, tamanho: Vector2, cor: Color, ang := 0.0, c := Vector2.ZERO) -> void:
	if tex == null:
		return
	draw_set_transform(c, ang)
	draw_texture_rect(tex, Rect2(-tamanho / 2.0, tamanho), false, cor)
	draw_set_transform(Vector2.ZERO)


func _ponteiros(r: float, t: float, alfa: float) -> void:
	var cor := _c("core", 0, alfa)
	draw_line(Vector2.ZERO, Vector2.from_angle(t * 5.0) * r * 0.85, cor, maxf(2.0, r * 0.1), true)
	draw_line(Vector2.ZERO, Vector2.from_angle(t * 0.6) * r * 0.55, cor, maxf(2.5, r * 0.14), true)
	draw_circle(Vector2.ZERO, maxf(2.0, r * 0.1), cor, true, -1.0, true)


func _draw() -> void:
	if _s.is_empty():
		return
	match tipo:
		"projetil":
			if nucleo == null and halo == null:
				super()
			else:
				_projetil_cc0()
		"area":
			if preenchimento == null and anel == null or int(_s.get("ativ", 1)) != 1:
				super()   # o aviso (telegraph) continua o tracejado da 16D
			else:
				_area_cc0()
		"beam":
			if corpo == null:
				super()
			else:
				_beam_cc0()
		_:
			super()


func _projetil_cc0() -> void:
	var M := UtilPalco.PX_POR_M
	var t := float(_ctx.get("t_jogo", 0.0)) + float(fixos.get("id", 0)) * 0.7
	var r := maxf(0.08, float(_s.get("r", 0.2))) * M
	for k in range(1, _rastro.size()):
		var a := do_mundo(_rastro[k - 1])
		var b := do_mundo(_rastro[k])
		var f := 1.0 - float(k) / _rastro.size()
		draw_line(a, b, _c("outer", 0, 0.5 * f), r * 1.3 * f, true)
	var lado_h := r * halo_escala
	_tex(halo, Vector2(lado_h, lado_h), _c("glow", 0, 0.85 * _brilho()), t * halo_giro)
	var lado := r * nucleo_escala
	_tex(nucleo, Vector2(lado, lado), _c(cor_nucleo, 0, 0.95), t * giro)
	if duas_cores:
		_tex(nucleo, Vector2(lado, lado) * 0.8, _c("outer", 2, 0.9), -t * giro * 1.3)
	if nucleo_escuro:
		draw_circle(Vector2.ZERO, r * 0.62, Color(0.02, 0.0, 0.05, 0.92), true, -1.0, true)
	else:
		draw_circle(Vector2.ZERO, r * 0.3, _c("core"), true, -1.0, true)
	if ponteiros:
		_ponteiros(r * 1.1, t, 0.9)


func _area_cc0() -> void:
	var M := UtilPalco.PX_POR_M
	var t := float(_ctx.get("t_jogo", 0.0))
	var prog := float(_s.get("prog", 0.0))
	var r := maxf(0.05, float(_s.get("r", fixos.get("raio_max", 1.0)))) * M
	var some := clampf((1.0 - prog) / 0.15, 0.0, 1.0)
	var nasce := clampf(prog / 0.06, 0.25, 1.0)
	var alfa := some * nasce
	var d := Vector2(2.0 * r, 2.0 * r)
	_tex(preenchimento, d, _c("mid", 0, (0.6 + 0.3 * _brilho()) * alfa), t * giro)
	if duas_cores:
		_tex(preenchimento, d * 0.8, _c("outer", 2, 0.5 * alfa), -t * giro * 1.2)
	if anel != null:
		if encolhe:
			for k in 2:
				var fase := fmod(t * 0.7 + k * 0.5, 1.0)
				_tex(anel, d * (1.3 - 0.8 * fase), _c("outer", 0, 0.8 * alfa * sin(fase * PI)), -t * 0.5)
		else:
			var pulso := 1.04 + 0.04 * sin(t * 6.0)
			_tex(anel, d * pulso, _c("outer", 0, 0.9 * alfa), -t * giro * 0.4)
	# a borda honesta: o raio que a simulacao usa
	draw_arc(Vector2.ZERO, r, 0, TAU, 64, _c("mid", 0, 0.75 * alfa), maxf(3.0, r * 0.03), true)
	if nucleo_escuro:
		draw_circle(Vector2.ZERO, r * 0.3, Color(0.02, 0.0, 0.04, 0.85 * alfa), true, -1.0, true)
	if ponteiros:
		_ponteiros(r * 0.8, t, 0.85 * alfa)
	var pilares = fixos.get("pilares")
	if typeof(pilares) == TYPE_ARRAY:
		var rp := float(fixos.get("raio_pilar", 0.4)) * M
		for p in pilares:
			var c := do_mundo(Vector2(float(p[0]), float(p[1])) * M)
			_tex(preenchimento, Vector2(rp, rp) * 2.2, _c("mid", 0, 0.9 * some), t * giro, c)
			draw_circle(c, rp * 0.45, _c("core", 0, some), true, -1.0, true)


func _beam_cc0() -> void:
	var M := UtilPalco.PX_POR_M
	var t := float(_ctx.get("t_jogo", 0.0))
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
	var larg := maxf(0.08, float(_s.get("larg", 8.0)) / PPM_MOTOR) * M
	var some := clampf(1.0 - float(_s.get("prog", 0.0)), 0.15, 1.0)
	# o corpo: a textura repetida ao longo de cada trecho, correndo da origem
	# para a ponta (uma repeticao a cada 6 larguras)
	var tam_tex := corpo.get_size()
	for s in range(1, pts.size()):
		var a := pts[s - 1]
		var b := pts[s]
		var comp := a.distance_to(b)
		if comp < 1.0:
			continue
		draw_set_transform(a, (b - a).angle())
		var rep := comp / (larg * 6.0)
		var regiao := Rect2(-fmod(t * 1.5, 1.0) * tam_tex.x, 0.0, tam_tex.x * rep, tam_tex.y)
		# halo largo e macio (a faixa da textura some nas bordas: sem retangulo)
		draw_texture_rect_region(corpo, Rect2(0.0, -larg * 2.6, comp, larg * 5.2), regiao, _c("glow", 0, 0.45 * _brilho() * some))
		draw_texture_rect_region(corpo, Rect2(0.0, -larg * 1.3, comp, larg * 2.6), regiao, _c("outer", 0, 0.9 * some))
		if duas_cores:
			regiao.position.x = fmod(t * 2.1, 1.0) * tam_tex.x
			draw_texture_rect_region(corpo, Rect2(0.0, -larg * 0.9, comp, larg * 1.8), regiao, _c("outer", 2, 0.8 * some))
		draw_set_transform(Vector2.ZERO)
	draw_polyline(pts, _c("core", 0, some), larg * 0.45, true)
	if nucleo_escuro:
		draw_polyline(pts, Color(0.02, 0.0, 0.05, 0.8 * some), larg * 0.3, true)
	var fim := pts[pts.size() - 1]
	_tex(ponta, Vector2(larg, larg) * 4.5, _c("mid", 0, some), t * 5.0, fim)
	_tex(TEX_BRILHO, Vector2(larg, larg) * 3.0, _c("glow", 0, 0.7 * some), 0.0, pts[0])
	if ponteiros:
		draw_set_transform(fim)
		_ponteiros(larg * 1.6, t, some)
		draw_set_transform(Vector2.ZERO)
