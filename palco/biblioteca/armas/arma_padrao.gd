extends PecaPalco
## A arma PADRAO: uma silhueta vetorial por TIPO (os 8 tipos do jogo).
##
## O palco ja poe a peca na EMPUNHADURA e gira para a PONTA da timeline (a
## geometria honesta: a ponta desenhada e o alcance da hitbox). Aqui so se
## desenha ao longo de +x, com o comprimento que chega em
## `amostra._comprimento_px`. Um estilo proprio entra como
## armas/estilos/<estilo>.tscn e ganha desta peca (docs/palco/COMO-EDITAR.md).

const METAL := Color8(200, 204, 214)
const METAL_ESCURO := Color8(118, 122, 134)
const MADEIRA := Color8(112, 80, 46)
const MADEIRA_ESCURA := Color8(72, 50, 30)

## Esta peca se desenha no comprimento da timeline (`_comprimento_px`): o
## palco nao a estica por escala (UtilPalco.esticar_arma).
var desenha_comprimento := true
var tipo := "Reta"
var estilo_arma := ""
var cor_arma := Color.WHITE
var raio_px := 85.0
var duas: Dictionary = {}
var _L := 100.0
var _s: Dictionary = {}
var _ctx: Dictionary = {}


func configurar(dados: Dictionary, _c: Dictionary) -> void:
	tipo = str(dados.get("tipo", "Reta"))
	estilo_arma = str(dados.get("estilo", ""))
	cor_arma = UtilPalco.cor(dados.get("cor", 0xFFFFFF))
	raio_px = float(dados.get("raio_corpo", 0.85)) * UtilPalco.PX_POR_M
	duas = dados.get("duas_laminas", {}) if typeof(dados.get("duas_laminas")) == TYPE_DICTIONARY else {}


func atualizar(amostra: Dictionary, ctx: Dictionary) -> void:
	_s = amostra
	_ctx = ctx
	_L = float(amostra.get("_comprimento_px", 100.0))
	queue_redraw()


func _contorno() -> float:
	var estilo: EstiloPalco = _ctx.get("estilo")
	return estilo.contorno_px * 0.7 if estilo else 3.0


func _cor_contorno() -> Color:
	var estilo: EstiloPalco = _ctx.get("estilo")
	return estilo.cor_contorno if estilo else Color(0, 0, 0)


func _poligono(pts: PackedVector2Array, cor: Color) -> void:
	draw_colored_polygon(pts, cor)
	var fechado := pts.duplicate()
	fechado.append(pts[0])
	draw_polyline(fechado, _cor_contorno(), _contorno(), true)


func _draw() -> void:
	if _s.is_empty():
		return
	var w := maxf(2.5, raio_px * 0.10)
	var L := _L
	match UtilPalco.slug(tipo):
		"dupla":
			var sep := raio_px * float(duas.get("separacao_r", 0.55))
			var abre := deg_to_rad(float(duas.get("abertura_graus", 10.0)))
			var Ld := float(duas.get("comprimento_m", L / UtilPalco.PX_POR_M)) * UtilPalco.PX_POR_M
			for lado in [-1.0, 1.0]:
				draw_set_transform(Vector2(0, sep * lado), abre * lado)
				_lamina(Ld, w * 0.85, 0.28)
			draw_set_transform(Vector2.ZERO)
		"corrente":
			_corrente(L, w)
		"arco":
			_arco(L, w)
		"arremesso":
			_lamina_curta(L, w)
		"orbital":
			draw_circle(Vector2(L, 0), w * 1.7, cor_arma.lerp(METAL, 0.3), true, -1.0, true)
			draw_arc(Vector2(L, 0), w * 1.7, 0, TAU, 32, _cor_contorno(), _contorno(), true)
			draw_arc(Vector2(L, 0), w * 1.0, 0, TAU, 24, cor_arma.lightened(0.5), maxf(1.5, w * 0.3), true)
		"magica":
			_cristal(L, w)
		"transformavel":
			_machado_martelo(L, w)
		_:
			_lamina(L, w, 0.22)


func _lamina(L: float, w: float, cabo_frac: float) -> void:
	var h := L * cabo_frac
	# cabo
	_poligono(PackedVector2Array([Vector2(0, -w * 0.42), Vector2(h, -w * 0.42), Vector2(h, w * 0.42), Vector2(0, w * 0.42)]), MADEIRA)
	# lamina
	var lamina := METAL.lerp(cor_arma, 0.30)
	_poligono(PackedVector2Array([
		Vector2(h, -w * 0.6), Vector2(L - w * 1.8, -w * 0.6), Vector2(L, 0),
		Vector2(L - w * 1.8, w * 0.6), Vector2(h, w * 0.6)]), lamina)
	draw_line(Vector2(h + w * 0.4, -w * 0.18), Vector2(L - w * 2.0, -w * 0.18), Color(1, 1, 1, 0.55), maxf(1.0, w * 0.22), true)
	# guarda
	_poligono(PackedVector2Array([Vector2(h - w * 0.35, -w * 1.6), Vector2(h + w * 0.35, -w * 1.6), Vector2(h + w * 0.35, w * 1.6), Vector2(h - w * 0.35, w * 1.6)]), cor_arma)


func _lamina_curta(L: float, w: float) -> void:
	var a := L * 0.78
	_poligono(PackedVector2Array([Vector2(a, -w * 0.3), Vector2(a + w * 1.2, -w * 0.3), Vector2(a + w * 1.2, w * 0.3), Vector2(a, w * 0.3)]), MADEIRA)
	_poligono(PackedVector2Array([Vector2(a + w * 1.2, -w * 0.55), Vector2(L + w * 1.8, 0), Vector2(a + w * 1.2, w * 0.55)]), METAL.lerp(cor_arma, 0.35))


func _corrente(L: float, w: float) -> void:
	var cabo := L * 0.16
	_poligono(PackedVector2Array([Vector2(0, -w * 0.45), Vector2(cabo, -w * 0.45), Vector2(cabo, w * 0.45), Vector2(0, w * 0.45)]), MADEIRA)
	var cabeca := w * 1.5
	var fim := L - cabeca
	var elos := int(maxf(3.0, (fim - cabo) / (w * 1.1)))
	for k in elos:
		var x := lerpf(cabo, fim, (k + 0.5) / elos)
		draw_arc(Vector2(x, 0), w * 0.42, 0, TAU, 12, METAL_ESCURO, maxf(1.5, w * 0.25), true)
	# cabeca com espinhos
	var c := Vector2(L - cabeca, 0)
	for k in 8:
		var a := k * TAU / 8.0
		_poligono(PackedVector2Array([c + Vector2(cos(a - 0.3), sin(a - 0.3)) * cabeca * 0.9, c + Vector2(cos(a), sin(a)) * cabeca * 1.45, c + Vector2(cos(a + 0.3), sin(a + 0.3)) * cabeca * 0.9]), METAL)
	draw_circle(c, cabeca, cor_arma.lerp(METAL_ESCURO, 0.4), true, -1.0, true)
	draw_arc(c, cabeca, 0, TAU, 32, _cor_contorno(), _contorno(), true)


func _arco(L: float, w: float) -> void:
	var alt := raio_px * 0.95
	var puxada := clampf(float(_s.get("arma_puxada", 0.0)), 0.0, 1.0)
	var pts := PackedVector2Array()
	for k in 17:
		var f := k / 16.0 * 2.0 - 1.0
		pts.append(Vector2(L * 0.45 * (1.0 - f * f), f * alt))
	draw_polyline(pts, _cor_contorno(), w * 1.25 + _contorno(), true)
	draw_polyline(pts, MADEIRA.lerp(cor_arma, 0.35), w * 1.25, true)
	var meio := Vector2(-puxada * L * 0.35, 0)
	draw_line(pts[0], meio, Color(0.92, 0.92, 0.95), maxf(1.0, w * 0.18), true)
	draw_line(meio, pts[16], Color(0.92, 0.92, 0.95), maxf(1.0, w * 0.18), true)
	if puxada > 0.05:
		draw_line(meio, Vector2(L * 0.95, 0), MADEIRA_ESCURA, maxf(1.5, w * 0.3), true)
		_poligono(PackedVector2Array([Vector2(L * 0.95, -w * 0.5), Vector2(L * 1.15, 0), Vector2(L * 0.95, w * 0.5)]), METAL)


func _cristal(L: float, w: float) -> void:
	var c := Vector2(L * 1.02, 0)
	var t := float(_ctx.get("t_jogo", 0.0))
	var r := w * 1.9
	var estilo: EstiloPalco = _ctx.get("estilo")
	var brilho := estilo.brilho if estilo else 0.4
	draw_circle(c, r * 2.0, Color(cor_arma.r, cor_arma.g, cor_arma.b, 0.18 * brilho), true, -1.0, true)
	var gira := t * 1.8
	var pts := PackedVector2Array()
	for k in 4:
		var a := gira + k * PI / 2.0
		pts.append(c + Vector2(cos(a), sin(a)) * (r if k % 2 == 0 else r * 0.62))
	_poligono(pts, cor_arma.lightened(0.15))
	draw_circle(c, r * 0.28, Color(1, 1, 1, 0.85), true, -1.0, true)


func _machado_martelo(L: float, w: float) -> void:
	var cabo := L * 0.78
	_poligono(PackedVector2Array([Vector2(0, -w * 0.45), Vector2(L, -w * 0.45), Vector2(L, w * 0.45), Vector2(0, w * 0.45)]), MADEIRA)
	var metal := METAL.lerp(cor_arma, 0.3)
	# lamina de machado de um lado
	_poligono(PackedVector2Array([Vector2(cabo, -w * 0.5), Vector2(cabo - w * 0.8, -w * 3.4), Vector2(L + w * 0.4, -w * 3.0), Vector2(L - w * 0.2, -w * 0.5)]), metal)
	# cabeca de martelo do outro
	_poligono(PackedVector2Array([Vector2(cabo + w * 0.2, w * 0.5), Vector2(cabo + w * 0.2, w * 2.3), Vector2(L - w * 0.2, w * 2.3), Vector2(L - w * 0.2, w * 0.5)]), METAL_ESCURO)
