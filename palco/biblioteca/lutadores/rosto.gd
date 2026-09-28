class_name RostoPalco
extends RefCounted
## Os 24 rostos do jogo (neural_fights/effects/character_flair.py), portados
## traco a traco e com antialiasing.
##
## Tudo e desenhado no QUADRO DO ROSTO: +x = queixo (para onde o lutador
## olha), +y = direita do rosto. Quem chama poe o CanvasItem nesse quadro
## (draw_set_transform com o angulo do olhar e o squash). Medidas em fracoes
## do raio R do corpo, as mesmas do jogo:
##   olhos em +0,26R, +-0,40R, raio 0,30R; boca em +0,70R; sobrancelha acima.

const COR_TRACO := Color8(16, 16, 26)
const COR_ESCLERA := Color8(248, 248, 252)
const COR_PUPILA := Color8(20, 20, 34)
const OLHO_AVANCO := 0.26
const OLHO_LATERAL := 0.40
const OLHO_RAIO := 0.30
const BOCA_AVANCO := 0.70
const SOBR_RECUO := 1.28
const SEM_PISCADA := {"morto": true, "tonto": true, "dor": true, "euforico": true, "concentrado": true}

var ci: CanvasItem
var R := 100.0
var t := 0.0
var semente := 0
var cor_corpo := Color.WHITE
var simples := false
var r_olho := 30.0
var olho_c: Array[Vector2] = []


func _init(p_ci: CanvasItem, raio: float, tempo: float, p_semente: int, p_cor_corpo: Color, p_simples: bool) -> void:
	ci = p_ci
	R = raio
	t = tempo
	semente = p_semente
	cor_corpo = p_cor_corpo
	simples = p_simples
	r_olho = R * OLHO_RAIO
	olho_c = [Vector2(OLHO_AVANCO * R, -OLHO_LATERAL * R), Vector2(OLHO_AVANCO * R, OLHO_LATERAL * R)]


# ------------------------------------------------------------ primitivas
func F(avanco: float, lateral: float = 0.0) -> Vector2:
	return Vector2(avanco, lateral) * R


func O(i: int, frente: float = 0.0, direita: float = 0.0) -> Vector2:
	return olho_c[i] + Vector2(frente, direita) * r_olho


func B(frente: float = 0.0, direita: float = 0.0) -> Vector2:
	return Vector2(BOCA_AVANCO * R, 0.0) + Vector2(frente, direita) * r_olho


func w() -> float:
	return maxf(1.0, r_olho * 0.24)


func linha(a: Vector2, b: Vector2, largura: float = -1.0, cor: Color = COR_TRACO) -> void:
	ci.draw_line(a, b, cor, largura if largura > 0.0 else w(), true)


func circ(c: Vector2, r: float, cor: Color) -> void:
	ci.draw_circle(c, maxf(0.5, r), cor, true, -1.0, true)


# ------------------------------------------------------------ olhos
func olho_aberto(i: int, r_mult := 1.0, pupila_mult := 1.0, olhar := 1.0, tremor := 0.0) -> void:
	var c := olho_c[i]
	var jit := sin(t * 24.0 + i * 2.1) * tremor if tremor != 0.0 else 0.0
	if simples:
		circ(c, r_olho * 0.62, COR_PUPILA)
		return
	var r := r_olho * r_mult
	circ(c, r, COR_ESCLERA)
	var pr := r_olho * 0.46 * pupila_mult
	var alcance := maxf(0.0, r - pr - 1.0)
	circ(c + Vector2(1.0, jit) * alcance * olhar, pr, COR_PUPILA)


func olho_fechado(i: int, curva := 0.0, largura := -1.0) -> void:
	var a := O(i, 0, -0.85)
	var b := O(i, 0, 0.85)
	if absf(curva) < 0.01:
		linha(a, b, largura)
	else:
		var m := O(i, -curva, 0)
		linha(a, m, largura)
		linha(m, b, largura)


func olho_x(i: int) -> void:
	linha(O(i, -0.75, -0.75), O(i, 0.75, 0.75))
	linha(O(i, 0.75, -0.75), O(i, -0.75, 0.75))


func olho_espiral(i: int) -> void:
	var c := olho_c[i]
	circ(c, r_olho, COR_ESCLERA)
	if simples:
		circ(c, r_olho * 0.45, COR_PUPILA)
		return
	var pts := PackedVector2Array()
	for k in 11:
		var fr := k / 10.0
		var a := t * 7.0 + fr * PI * 3.4 + i * PI
		pts.append(c + Vector2(cos(a), sin(a)) * r_olho * 0.78 * fr)
	ci.draw_polyline(pts, COR_TRACO, maxf(1.0, w() - 1.0), true)


func olho_apertado(i: int) -> void:
	var ponta := O(i, 0.55, 0)
	linha(O(i, -0.55, -0.8), ponta)
	linha(O(i, -0.55, 0.8), ponta)


func palpebra(i: int, quanto := 0.4) -> void:
	if simples:
		return
	quanto = clampf(quanto, 0.05, 0.75)
	circ(O(i, -(2.0 - 2.0 * quanto), 0), r_olho + 1.0, cor_corpo)
	var prof := 1.0 - 2.0 * quanto
	var corda := sqrt(maxf(0.0, 1.0 - prof * prof)) + 0.12
	linha(O(i, -prof, -corda), O(i, -prof, corda))


# ------------------------------------------------------------ sobrancelhas
func sobrancelha(i: int, incl := 0.0, subir := 0.0) -> void:
	if simples:
		return
	var lado := -1.0 if i == 0 else 1.0
	var base_f := -(SOBR_RECUO + subir)
	linha(O(i, base_f - incl * 0.15, 0.85 * lado), O(i, base_f + incl * 0.62, -0.62 * lado))


# ------------------------------------------------------------ bocas
func boca_linha(larg := 0.7) -> void:
	linha(B(0, -larg), B(0, larg))


func boca_sorriso(larg := 1.0, prof := 0.5) -> void:
	var m := B(prof * 0.5, 0)
	linha(B(-prof * 0.6, -larg), m)
	linha(m, B(-prof * 0.6, larg))


func boca_triste(larg := 0.85) -> void:
	var m := B(-0.45, 0)
	linha(B(0.18, -larg), m)
	linha(m, B(0.18, larg))


func boca_aberta(r_mult := 0.55, grito := false) -> void:
	var c := B(0.15 if grito else 0.0, 0)
	var r := r_olho * r_mult
	circ(c, r, COR_TRACO)
	if grito:
		circ(c, r * 0.55, Color8(128, 42, 52))


func boca_dentes(larg := 1.0) -> void:
	if simples:
		boca_linha(larg * 0.8)
		return
	var faixa := maxf(2.0, r_olho * 0.6)
	var fino := maxf(1.0, w() - 1.0)
	var a := B(0, -larg)
	var b := B(0, larg)
	linha(a, b, faixa, COR_ESCLERA)
	var meio := faixa / 2.0
	for s in [-1.0, 1.0]:
		linha(a + Vector2(meio * s, 0), b + Vector2(meio * s, 0), fino)
	for ponta in [a, b]:
		linha(ponta - Vector2(meio, 0), ponta + Vector2(meio, 0), fino)
	for fr in [-0.5, 0.0, 0.5]:
		var c := B(0, larg * fr)
		linha(c - Vector2(meio, 0), c + Vector2(meio, 0), maxf(1.0, fino * 0.6))


func boca_onda(larg := 0.9) -> void:
	if simples:
		boca_linha(larg * 0.7)
		return
	var pts := PackedVector2Array()
	for k in 7:
		var fr := k / 6.0 - 0.5
		pts.append(B(sin(fr * PI * 3.0 + t * 10.0) * 0.28, larg * 2.0 * fr))
	ci.draw_polyline(pts, COR_TRACO, w(), true)


func boca_smirk() -> void:
	var m := B(0.1, 0.25)
	linha(B(0, -0.75), m)
	linha(m, B(-0.45, 0.85))


# ------------------------------------------------------------ extras
func gota_suor() -> void:
	if simples:
		return
	var queda := fmod(t * 2.0 + semente * 0.13, 1.0) * 0.42
	var g := F(0.05 + queda, 0.72)
	var r := r_olho * 0.3
	var cor := Color8(140, 208, 248)
	circ(g, r, cor)
	ci.draw_colored_polygon(PackedVector2Array([g + Vector2(0, -r), g + Vector2(0, r), g + Vector2(-r * 1.7, 0)]), cor)


func lagrima(i := 1) -> void:
	if simples:
		return
	var queda := fmod(t * 1.4 + semente * 0.29, 1.0)
	circ(O(i, 0.85 + queda * 0.35, 0.25), r_olho * 0.24, Color8(150, 205, 250))


func veia_raiva() -> void:
	if simples:
		return
	var p := F(-0.52, 0.42)
	var r := r_olho * (0.5 + 0.09 * sin(t * 10.0))
	var cor := Color8(235, 76, 76)
	for k in 4:
		var a := k * PI / 2.0 + PI / 4.0
		linha(p + Vector2(cos(a), sin(a)) * r * 0.3, p + Vector2(cos(a), sin(a)) * r, maxf(1.0, w() - 1.0), cor)


func brilho_pupila(i: int) -> void:
	if simples:
		return
	var c := O(i, 0.28, 0)
	var r := r_olho * 0.42
	var pts := PackedVector2Array()
	for k in 8:
		var a := t * 1.5 + k * PI / 4.0
		pts.append(c + Vector2(cos(a), sin(a)) * (r if k % 2 == 0 else r * 0.42))
	ci.draw_colored_polygon(pts, Color8(255, 214, 90))
	circ(c, r * 0.3, Color8(255, 250, 220))


func faiscas_alerta() -> void:
	if simples:
		return
	for k in [-1, 0, 1]:
		linha(F(-0.55 - 0.06 * absf(k), 0.26 * k), F(-0.78 - 0.08 * absf(k), 0.38 * k), maxf(1.0, w() - 1.0))


# ------------------------------------------------------------ catalogo
func desenhar(expressao: String) -> void:
	match expressao:
		"focado":
			olho_aberto(0); olho_aberto(1); palpebra(0, 0.34); palpebra(1, 0.34)
			sobrancelha(0, 0.45); sobrancelha(1, 0.45); boca_linha(0.6)
		"glacial":
			olho_aberto(0, 1.0, 0.8); olho_aberto(1, 1.0, 0.8); palpebra(0, 0.46); palpebra(1, 0.46); boca_linha(0.9)
		"determinado":
			olho_aberto(0); olho_aberto(1); sobrancelha(0, 0.7); sobrancelha(1, 0.7); boca_linha(0.8)
		"furia":
			olho_aberto(0, 0.94, 0.68); olho_aberto(1, 0.94, 0.68); sobrancelha(0, 1.0); sobrancelha(1, 1.0)
			boca_dentes(1.0); veia_raiva()
		"berserk":
			olho_aberto(0, 1.12, 0.4); olho_aberto(1, 0.9, 1.25); sobrancelha(0, 1.0); sobrancelha(1, 0.55)
			boca_sorriso(1.25, 0.75); veia_raiva()
		"confiante":
			olho_aberto(0); olho_aberto(1); palpebra(0, 0.3); palpebra(1, 0.3); boca_smirk()
		"animado":
			olho_aberto(0, 1.08); olho_aberto(1, 1.08); sobrancelha(0, 0.0, 0.35); sobrancelha(1, 0.0, 0.35); boca_sorriso(1.0, 0.5)
		"euforico":
			olho_fechado(0, 0.6); olho_fechado(1, 0.6); boca_aberta(0.75)
		"extase":
			olho_aberto(0, 1.1, 1.35); olho_aberto(1, 1.1, 1.35); brilho_pupila(0); brilho_pupila(1); boca_aberta(0.5)
		"panico":
			olho_aberto(0, 1.28, 0.42); olho_aberto(1, 1.28, 0.42); sobrancelha(0, -0.7, 0.5); sobrancelha(1, -0.7, 0.5)
			boca_onda(0.85); gota_suor()
		"nervoso":
			olho_aberto(0, 1.0, 1.0, 1.0, 0.35); olho_aberto(1, 1.0, 1.0, 1.0, 0.35); sobrancelha(0, -0.5); sobrancelha(1, -0.5)
			boca_onda(0.7); gota_suor()
		"desespero":
			olho_aberto(0, 1.22, 0.5); olho_aberto(1, 1.22, 0.5); sobrancelha(0, -1.0, 0.4); sobrancelha(1, -1.0, 0.4)
			boca_aberta(0.62, true); gota_suor()
		"tedio":
			olho_aberto(0); olho_aberto(1); palpebra(0, 0.58); palpebra(1, 0.58); boca_triste(0.55)
		"tristeza":
			olho_aberto(0, 1.0, 0.85, 0.45); olho_aberto(1, 1.0, 0.85, 0.45); sobrancelha(0, -0.9); sobrancelha(1, -0.9)
			boca_triste(0.8); lagrima()
		"morto":
			olho_x(0); olho_x(1); boca_linha(0.6)
		"tonto":
			olho_espiral(0); olho_espiral(1); boca_onda(0.75)
		"dor":
			olho_apertado(0); olho_apertado(1); boca_aberta(0.55, true)
		"esforco":
			olho_aberto(0, 0.85); olho_aberto(1, 0.85); sobrancelha(0, 0.85); sobrancelha(1, 0.85); boca_dentes(0.9)
		"firmeza":
			olho_aberto(0, 0.85); olho_aberto(1, 0.85); palpebra(0, 0.4); palpebra(1, 0.4)
			sobrancelha(0, 0.6); sobrancelha(1, 0.6); boca_linha(0.9)
		"alerta":
			olho_aberto(0, 1.28, 0.55); olho_aberto(1, 1.28, 0.55); sobrancelha(0, 0.0, 0.65); sobrancelha(1, 0.0, 0.65)
			boca_aberta(0.4); faiscas_alerta()
		"confuso":
			olho_aberto(0, 1.18); olho_aberto(1, 0.86); palpebra(1, 0.42); sobrancelha(0, 0.0, 0.6); sobrancelha(1, 0.5)
			boca_onda(0.55)
		"limite":
			olho_aberto(0, 0.9, 1.2); olho_aberto(1, 0.9, 1.2); sobrancelha(0, -0.6); sobrancelha(1, -0.6)
			boca_dentes(0.8); gota_suor()
		"concentrado":
			olho_fechado(0); olho_fechado(1); sobrancelha(0, 0.3); sobrancelha(1, 0.3); boca_linha(0.5)
		_:
			olho_aberto(0); olho_aberto(1); boca_linha(0.7)
	# Piscada por cima de qualquer expressao (a do jogo dependia do relogio de
	# parede e do id do objeto; aqui e o tempo de JOGO e o slot: reproduzivel).
	if not SEM_PISCADA.has(expressao) and fmod(t + (semente % 10) * 0.37, 3.4) < 0.12:
		for i in 2:
			circ(olho_c[i], r_olho * 1.5, cor_corpo)
			olho_fechado(i)
