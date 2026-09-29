class_name RostoPalco
extends RefCounted
## Os 24 rostos do jogo (neural_fights/effects/character_flair.py) montados
## com as PECAS do Kenney Shape Characters (CC0, biblioteca/lutadores/rosto/,
## recortadas a 12x por `main.py palco pecas-do-rosto`): olho, 4 sobrancelhas,
## meio-olhos, olhos fechados, olho em X e 3 bocas. As pecas sao mascaras
## BRANCAS pintadas com a cor do traco do estilo (#14141A); o branco do olho
## arregalado e dos dentes leva o cel de 2 tons (base + sombra embaixo) e o
## contorno do estilo. O que o pacote nao tem (espiral, boca ondulada, gota,
## lagrima, veia, estrela) continua desenhado aqui, na mesma cor e espessura.
##
## Tudo e desenhado no QUADRO DO ROSTO: +x = queixo (para onde o lutador
## olha), +y = direita do rosto. Quem chama poe o CanvasItem nesse quadro
## (`base`, com o angulo do olhar e o squash) e passa a mesma matriz aqui:
## cada peca e desenhada com base * (posicao, giro, escala). Medidas em
## fracoes do raio R do corpo. A imagem da peca tem o "alto" para a testa
## (-x) e a direita da imagem para o lado -y.

const PECAS := {
	"eye_open": preload("res://biblioteca/lutadores/rosto/eye_open.png"),
	"eye_half_top": preload("res://biblioteca/lutadores/rosto/eye_half_top.png"),
	"eye_half_top_wing": preload("res://biblioteca/lutadores/rosto/eye_half_top_wing.png"),
	"eye_half_bottom": preload("res://biblioteca/lutadores/rosto/eye_half_bottom.png"),
	"eye_closed_down": preload("res://biblioteca/lutadores/rosto/eye_closed_down.png"),
	"eye_closed_up": preload("res://biblioteca/lutadores/rosto/eye_closed_up.png"),
	"eye_x": preload("res://biblioteca/lutadores/rosto/eye_x.png"),
	"eyebrow_a": preload("res://biblioteca/lutadores/rosto/eyebrow_a.png"),
	"eyebrow_b": preload("res://biblioteca/lutadores/rosto/eyebrow_b.png"),
	"eyebrow_c": preload("res://biblioteca/lutadores/rosto/eyebrow_c.png"),
	"eyebrow_d": preload("res://biblioteca/lutadores/rosto/eyebrow_d.png"),
	"mouth_happy": preload("res://biblioteca/lutadores/rosto/mouth_happy.png"),
	"mouth_sad": preload("res://biblioteca/lutadores/rosto/mouth_sad.png"),
	"mouth_smirk": preload("res://biblioteca/lutadores/rosto/mouth_smirk.png"),
}
## margem (px) em volta de cada peca no png (builds/palco/rosto_pecas.py): o
## diametro do olho e a largura do png menos 2 margens. A escala da peca sai
## do png, entao rasterizar de novo em outra escala nao muda o rosto.
const MARGEM_TEX := 6.0

const EXPRESSOES := [
	"neutro", "focado", "glacial", "determinado", "furia", "berserk", "confiante", "animado",
	"euforico", "extase", "panico", "nervoso", "desespero", "tedio", "tristeza", "morto",
	"tonto", "dor", "esforco", "firmeza", "alerta", "confuso", "limite", "concentrado",
]
const COR_BRANCO := Color8(250, 250, 252)
const COR_BRANCO_SOMBRA := Color8(206, 210, 224)
const COR_BOCA := Color8(128, 42, 52)
# layout (fracoes de R): o rosto ocupa a metade da frente da bolinha vista de cima
const OLHO_AVANCO := 0.20
const OLHO_LATERAL := 0.36
const OLHO_DIAM := 0.40
const BOCA_AVANCO := 0.66
const SOBR_RECUO := 0.36
const SOBR_INCL := 0.42      # rad de inclinacao por unidade de `incl`
const SEM_PISCADA := {"morto": true, "tonto": true, "dor": true, "euforico": true, "concentrado": true}

var ci   # o CanvasItem que desenha (ou o Gravador, nos testes)
var base := Transform2D.IDENTITY
var R := 100.0
var t := 0.0
var semente := 0
var cor_corpo := Color.WHITE
var traco := Color8(20, 20, 26)
var simples := false
var k := 1.0                  # px do rosto por px da textura
var olho_c: Array[Vector2] = []
var piscando := false
## nome da peca -> maior ampliacao usada (px da tela por px do png, com zoom 1):
## acima de 1 a peca cresce e fica mole (teste "nitida a 408 px")
var ampliacao := {}


## Um "CanvasItem" que nao desenha: o teste monta as 24 expressoes sem tela
## (headless) e le `ampliacao`.
class Gravador:
	extends RefCounted
	func draw_set_transform_matrix(_m: Transform2D) -> void: pass
	func draw_texture_rect(_t, _r, _tile, _mod = Color.WHITE, _tr = false) -> void: pass
	func draw_line(_a, _b, _c, _w = -1.0, _aa = false) -> void: pass
	func draw_circle(_c, _r, _cor, _f = true, _w = -1.0, _aa = false) -> void: pass
	func draw_polyline(_p, _c, _w = -1.0, _aa = false) -> void: pass
	func draw_colored_polygon(_p, _c, _uv = PackedVector2Array(), _tex = null) -> void: pass


func _init(p_ci, raio: float, tempo: float, p_semente: int, p_cor_corpo: Color, p_simples: bool,
		p_base: Transform2D = Transform2D.IDENTITY, p_traco: Color = Color8(20, 20, 26)) -> void:
	ci = p_ci
	R = raio
	t = tempo
	semente = p_semente
	cor_corpo = p_cor_corpo
	simples = p_simples
	base = p_base
	traco = p_traco
	k = R * OLHO_DIAM / (PECAS["eye_open"].get_width() - 2.0 * MARGEM_TEX)
	olho_c = [Vector2(OLHO_AVANCO * R, -OLHO_LATERAL * R), Vector2(OLHO_AVANCO * R, OLHO_LATERAL * R)]


# ------------------------------------------------------------ primitivas
func F(avanco: float, lateral: float = 0.0) -> Vector2:
	return Vector2(avanco, lateral) * R


## Uma peca centrada em `c` (quadro do rosto). `escala` multiplica o tamanho
## Kenney (1 = olho de 0,40R); `giro` gira no quadro do rosto; `espelho`
## espelha a imagem (a sobrancelha do outro olho); `achatar` (0..1) encolhe
## na altura da imagem (palpebra mais baixa).
func peca(nome: String, c: Vector2, escala := 1.0, giro := 0.0, espelho := false, cor: Color = Color(0, 0, 0, 0),
		achatar := 1.0) -> void:
	var tex: Texture2D = PECAS[nome]
	var s := k * escala
	ci.draw_set_transform_matrix(base * Transform2D(-PI / 2.0 + giro, Vector2(s * (-1.0 if espelho else 1.0), s * achatar), 0.0, c))
	var tam := tex.get_size()
	ampliacao[nome] = maxf(float(ampliacao.get(nome, 0.0)), s * maxf(1.0, achatar))
	ci.draw_texture_rect(tex, Rect2(-tam / 2.0, tam), false, traco if cor.a == 0.0 else cor)
	ci.draw_set_transform_matrix(base)


## Largura (px do rosto) do traco das pecas: o Kenney usa ~1/4 do olho.
func w() -> float:
	return maxf(1.5, R * OLHO_DIAM * 0.21)


func linha(a: Vector2, b: Vector2, largura: float = -1.0, cor: Color = Color(0, 0, 0, 0)) -> void:
	ci.draw_line(a, b, traco if cor.a == 0.0 else cor, largura if largura > 0.0 else w(), true)
	# ponta redonda, como as pecas
	var r := (largura if largura > 0.0 else w()) / 2.0
	circ(a, r, traco if cor.a == 0.0 else cor)
	circ(b, r, traco if cor.a == 0.0 else cor)


func circ(c: Vector2, r: float, cor: Color) -> void:
	ci.draw_circle(c, maxf(0.5, r), cor, true, -1.0, true)


## Direcao da TELA (luz do alto a esquerda) no quadro do rosto: o brilho do
## olho fica no mesmo canto do brilho do corpo, gire o lutador como girar.
func _luz(tamanho: float) -> Vector2:
	var d := base.affine_inverse().basis_xform(Vector2(-1.0, -1.0).normalized())
	return d.normalized() * tamanho if d.length() > 0.0 else Vector2.ZERO


# ------------------------------------------------------------ olhos
## Olho aberto: o disco do Kenney com um brilho branco (o "1 brilho" do
## estilo). `olhar` empurra o olho para a frente (para onde ele mira).
func olho_aberto(i: int, r_mult := 1.0, olhar := 0.0, tremor := 0.0) -> void:
	if piscando:
		olho_fechado(i)
		return
	var c := olho_c[i] + Vector2(olhar * 0.06 * R, sin(t * 24.0 + i * 2.1) * tremor * 0.05 * R)
	peca("eye_open", c, r_mult)
	if not simples:
		var r := R * OLHO_DIAM * 0.5 * r_mult
		circ(c + _luz(r * 0.42), r * 0.26, COR_BRANCO)


## Olho arregalado: branco com contorno e sombra (cel de 2 tons) e o disco
## do Kenney pequeno como pupila. `pupila` = fracao do diametro do branco.
func olho_arregalado(i: int, r_mult := 1.2, pupila := 0.45, tremor := 0.0) -> void:
	if piscando:
		olho_fechado(i)
		return
	var c := olho_c[i]
	var r := R * OLHO_DIAM * 0.5 * r_mult
	if simples:
		circ(c, r * 0.6, traco)
		return
	circ(c, r + w() * 0.45, traco)
	circ(c, r, COR_BRANCO_SOMBRA)
	circ(c + _luz(r * 0.12), r * 0.9, COR_BRANCO)
	var jit := Vector2(0, sin(t * 24.0 + i * 2.1) * tremor * r * 0.25)
	var cp := c + Vector2(r * (1.0 - pupila) * 0.35, 0) + jit
	peca("eye_open", cp, r_mult * pupila)
	circ(cp + _luz(r * pupila * 0.4), r * pupila * 0.22, COR_BRANCO)


## Olho fechado reto (a peca fina deitada) ou em arco: curva > 0 = feliz (^),
## curva < 0 = calmo (u).
func olho_fechado(i: int, curva := 0.0) -> void:
	if curva > 0.01:
		peca("eye_closed_up", olho_c[i], 0.95)
	elif curva < -0.01:
		peca("eye_closed_down", olho_c[i] + Vector2(-0.04 * R, 0), 0.95)
	else:
		peca("eyebrow_a", olho_c[i] + Vector2(0.02 * R, 0), 0.62, 0.0, false, Color(0, 0, 0, 0), 0.8)


## Palpebra baixa: o meio-olho do Kenney (topo reto). `quanto` 0,3..0,6 abaixa
## a palpebra (achata o meio-olho).
func olho_palpebra(i: int, r_mult := 1.0, quanto := 0.4) -> void:
	if piscando:
		olho_fechado(i)
		return
	var achatar := clampf(1.25 - quanto, 0.55, 1.0)
	var r := R * OLHO_DIAM * 0.5 * r_mult
	peca("eye_half_bottom", olho_c[i] + Vector2(r * 0.28, 0), r_mult, 0.0, false, Color(0, 0, 0, 0), achatar)
	if not simples:
		circ(olho_c[i] + Vector2(r * 0.5, 0) + _luz(r * 0.3), r * 0.18, COR_BRANCO)


func olho_x(i: int) -> void:
	peca("eye_x", olho_c[i], 0.95)


func olho_espiral(i: int) -> void:
	var c := olho_c[i]
	var r := R * OLHO_DIAM * 0.55
	if simples:
		circ(c, r * 0.5, traco)
		return
	circ(c, r + w() * 0.4, traco)
	circ(c, r, COR_BRANCO)
	var pts := PackedVector2Array()
	for kk in 15:
		var fr := kk / 14.0
		var a := t * 7.0 + fr * PI * 3.4 + i * PI
		pts.append(c + Vector2(cos(a), sin(a)) * r * 0.8 * fr)
	ci.draw_polyline(pts, traco, w() * 0.6, true)


## Olho apertado de dor (> <): duas pecas finas em V.
func olho_apertado(i: int) -> void:
	var c := olho_c[i]
	var lado := -1.0 if i == 0 else 1.0
	var d := R * OLHO_DIAM * 0.2
	for s in [-1.0, 1.0]:
		peca("eyebrow_a", c + Vector2(s * d, lado * d * 0.5), 0.36, s * lado * 0.62)


# ------------------------------------------------------------ sobrancelhas
## `incl` > 0 = brava (ponta de dentro desce), < 0 = triste; `subir` afasta
## do olho. `forma`: a (fina), b (inclinada), c (curta), d (grossa).
func sobrancelha(i: int, incl := 0.0, subir := 0.0, forma := "eyebrow_a", escala := 0.72) -> void:
	if simples:
		return
	var lado := -1.0 if i == 0 else 1.0
	var c := olho_c[i] + Vector2(-(SOBR_RECUO + subir * 0.3) * R + incl * 0.03 * R, lado * 0.03 * R)
	# o olho 0 fica em -y: a imagem ja aponta a direita para -y (a ponta de
	# FORA); o olho 1 espelha a imagem
	peca(forma, c, escala, lado * incl * SOBR_INCL, i == 1)


# ------------------------------------------------------------ bocas
func _boca(frente := 0.0) -> Vector2:
	return Vector2((BOCA_AVANCO + frente) * R, 0.0)


func boca_linha(larg := 0.7) -> void:
	peca("eyebrow_a", _boca(), larg * 0.95, 0.0, false, Color(0, 0, 0, 0), 0.85)


func boca_sorriso(larg := 1.0, _prof := 0.5) -> void:
	peca("mouth_happy", _boca(-0.02), larg * 1.0)


func boca_triste(larg := 0.85) -> void:
	peca("mouth_sad", _boca(0.02), larg * 1.0)


func boca_smirk() -> void:
	peca("mouth_smirk", _boca() + Vector2(0, 0.06 * R), 1.05)


## Boca aberta: o meio-disco do Kenney (reto em cima). No grito, o disco
## inteiro com a lingua.
func boca_aberta(r_mult := 0.55, grito := false) -> void:
	if grito:
		var c := _boca(0.04)
		peca("eye_open", c, r_mult * 1.5)
		if not simples:
			circ(c + Vector2(0.02 * R, 0), R * OLHO_DIAM * 0.5 * r_mult * 0.9, COR_BOCA)
		return
	peca("eye_half_bottom", _boca(0.02), r_mult * 2.0)


## Dentes cerrados: barra branca de cel (base + sombra embaixo), contorno do
## estilo e as divisoes; a silhueta e a da sobrancelha grossa (eyebrow_d).
func boca_dentes(larg := 1.0) -> void:
	if simples:
		boca_linha(larg * 0.8)
		return
	var c := _boca()
	var e := larg * 0.85
	peca("eyebrow_d", c, e * 1.12, 0.0, false, traco, 1.25)
	peca("eyebrow_d", c, e, 0.0, false, COR_BRANCO_SOMBRA)
	peca("eyebrow_d", c + Vector2(-0.015 * R, 0), e * 0.97, 0.0, false, COR_BRANCO, 0.6)
	var tam: Vector2 = PECAS["eyebrow_d"].get_size() - Vector2(2.0, 2.0) * MARGEM_TEX
	var meia := tam.x * k * e / 2.0
	var alto := tam.y * k * e / 2.0
	for fr in [-0.5, 0.0, 0.5]:
		linha(c + Vector2(-alto * 0.8, meia * fr), c + Vector2(alto * 0.8, meia * fr), maxf(1.0, w() * 0.35))
	linha(c + Vector2(0, -meia * 0.92), c + Vector2(0, meia * 0.92), maxf(1.0, w() * 0.3))


func boca_onda(larg := 0.9) -> void:
	if simples:
		boca_linha(larg * 0.7)
		return
	var pts := PackedVector2Array()
	for kk in 13:
		var fr := kk / 12.0 - 0.5
		pts.append(_boca() + Vector2(sin(fr * PI * 3.0 + t * 10.0) * 0.045 * R, larg * 0.36 * R * 2.0 * fr))
	ci.draw_polyline(pts, traco, w() * 0.9, true)
	circ(pts[0], w() * 0.45, traco)
	circ(pts[pts.size() - 1], w() * 0.45, traco)


# ------------------------------------------------------------ extras
func gota_suor() -> void:
	if simples:
		return
	var queda := fmod(t * 2.0 + semente * 0.13, 1.0) * 0.30
	var g := F(-0.05 + queda, 0.74)
	var r := R * 0.085
	var cor := Color8(140, 208, 248)
	var ponta := g + Vector2(-r * 1.9, 0)
	ci.draw_colored_polygon(PackedVector2Array([g + Vector2(0, -r), g + Vector2(0, r), ponta]), traco)
	circ(g, r + w() * 0.3, traco)
	circ(g, r, cor)
	ci.draw_colored_polygon(PackedVector2Array([g + Vector2(0, -r * 0.8), g + Vector2(0, r * 0.8), ponta + Vector2(r * 0.4, 0)]), cor)
	circ(g + Vector2(-r * 0.25, -r * 0.3), r * 0.28, COR_BRANCO)


func lagrima(i := 1) -> void:
	if simples:
		return
	var queda := fmod(t * 1.4 + semente * 0.29, 1.0)
	var c := olho_c[i] + Vector2((0.22 + queda * 0.16) * R, 0.06 * R)
	circ(c, R * 0.07 + w() * 0.3, traco)
	circ(c, R * 0.07, Color8(150, 205, 250))


func veia_raiva() -> void:
	if simples:
		return
	var p := F(-0.50, 0.46)
	var r := R * 0.13 * (1.0 + 0.09 * sin(t * 10.0))
	var cor := Color8(235, 76, 76)
	for kk in 4:
		var a := kk * PI / 2.0 + PI / 4.0
		ci.draw_line(p + Vector2(cos(a), sin(a)) * r * 0.3, p + Vector2(cos(a), sin(a)) * r, cor, w() * 0.55, true)


func brilho_pupila(i: int) -> void:
	if simples:
		return
	var c := olho_c[i]
	var r := R * OLHO_DIAM * 0.34
	var pts := PackedVector2Array()
	for kk in 8:
		var a := t * 1.5 + kk * PI / 4.0
		pts.append(c + Vector2(cos(a), sin(a)) * (r if kk % 2 == 0 else r * 0.42))
	ci.draw_colored_polygon(pts, Color8(255, 214, 90))
	circ(c, r * 0.3, Color8(255, 250, 220))


func faiscas_alerta() -> void:
	if simples:
		return
	for kk in [-1, 0, 1]:
		linha(F(-0.58 - 0.05 * absf(kk), 0.26 * kk), F(-0.78 - 0.07 * absf(kk), 0.38 * kk), w() * 0.5)


# ------------------------------------------------------------ catalogo
func desenhar(expressao: String) -> void:
	# Piscada: tempo de JOGO e slot (reproduzivel). Os olhos abertos viram a
	# peca fina deitada; quem ja tem olho especial nao pisca.
	piscando = not SEM_PISCADA.has(expressao) and fmod(t + (semente % 10) * 0.37, 3.4) < 0.12
	ci.draw_set_transform_matrix(base)
	match expressao:
		"focado":
			olho_palpebra(0, 1.0, 0.34); olho_palpebra(1, 1.0, 0.34)
			sobrancelha(0, 0.45); sobrancelha(1, 0.45); boca_linha(0.6)
		"glacial":
			olho_palpebra(0, 1.0, 0.5); olho_palpebra(1, 1.0, 0.5); boca_linha(0.9)
		"determinado":
			olho_aberto(0); olho_aberto(1); sobrancelha(0, 0.7, 0.0, "eyebrow_d"); sobrancelha(1, 0.7, 0.0, "eyebrow_d")
			boca_linha(0.8)
		"furia":
			olho_aberto(0, 0.94, 0.5); olho_aberto(1, 0.94, 0.5)
			sobrancelha(0, 1.0, 0.0, "eyebrow_d"); sobrancelha(1, 1.0, 0.0, "eyebrow_d")
			boca_dentes(1.0); veia_raiva()
		"berserk":
			olho_arregalado(0, 1.15, 0.36); olho_aberto(1, 0.95, 0.5)
			sobrancelha(0, 1.0, 0.0, "eyebrow_d"); sobrancelha(1, 0.55, 0.1, "eyebrow_b")
			boca_sorriso(1.25, 0.75); veia_raiva()
		"confiante":
			olho_palpebra(0, 1.0, 0.3); olho_palpebra(1, 1.0, 0.3); sobrancelha(1, -0.15, 0.25, "eyebrow_c"); boca_smirk()
		"animado":
			olho_aberto(0, 1.08); olho_aberto(1, 1.08); sobrancelha(0, 0.0, 0.4); sobrancelha(1, 0.0, 0.4)
			boca_sorriso(1.0, 0.5)
		"euforico":
			olho_fechado(0, 0.6); olho_fechado(1, 0.6); sobrancelha(0, -0.1, 0.45); sobrancelha(1, -0.1, 0.45)
			boca_aberta(0.75)
		"extase":
			olho_aberto(0, 1.1); olho_aberto(1, 1.1); brilho_pupila(0); brilho_pupila(1); boca_aberta(0.55)
		"panico":
			olho_arregalado(0, 1.3, 0.34); olho_arregalado(1, 1.3, 0.34)
			sobrancelha(0, -0.7, 0.55); sobrancelha(1, -0.7, 0.55); boca_onda(0.85); gota_suor()
		"nervoso":
			olho_aberto(0, 1.0, 0.0, 0.35); olho_aberto(1, 1.0, 0.0, 0.35); sobrancelha(0, -0.5); sobrancelha(1, -0.5)
			boca_onda(0.7); gota_suor()
		"desespero":
			olho_arregalado(0, 1.24, 0.4); olho_arregalado(1, 1.24, 0.4)
			sobrancelha(0, -1.0, 0.45); sobrancelha(1, -1.0, 0.45); boca_aberta(0.62, true); gota_suor()
		"tedio":
			olho_palpebra(0, 1.0, 0.6); olho_palpebra(1, 1.0, 0.6); boca_triste(0.6)
		"tristeza":
			olho_aberto(0, 1.0, -0.4); olho_aberto(1, 1.0, -0.4); sobrancelha(0, -0.9); sobrancelha(1, -0.9)
			boca_triste(0.85); lagrima()
		"morto":
			olho_x(0); olho_x(1); boca_triste(0.7)
		"tonto":
			olho_espiral(0); olho_espiral(1); boca_onda(0.75)
		"dor":
			olho_apertado(0); olho_apertado(1); sobrancelha(0, -0.6, 0.2); sobrancelha(1, -0.6, 0.2)
			boca_aberta(0.55, true)
		"esforco":
			olho_aberto(0, 0.85); olho_aberto(1, 0.85); sobrancelha(0, 0.85, 0.0, "eyebrow_d"); sobrancelha(1, 0.85, 0.0, "eyebrow_d")
			boca_dentes(0.9)
		"firmeza":
			olho_palpebra(0, 0.9, 0.4); olho_palpebra(1, 0.9, 0.4); sobrancelha(0, 0.6); sobrancelha(1, 0.6)
			boca_linha(0.9)
		"alerta":
			olho_arregalado(0, 1.3, 0.45); olho_arregalado(1, 1.3, 0.45); sobrancelha(0, 0.0, 0.7); sobrancelha(1, 0.0, 0.7)
			boca_aberta(0.4); faiscas_alerta()
		"confuso":
			olho_aberto(0, 1.18); olho_palpebra(1, 0.86, 0.42); sobrancelha(0, -0.2, 0.6, "eyebrow_c"); sobrancelha(1, 0.5)
			boca_onda(0.55)
		"limite":
			olho_arregalado(0, 1.0, 0.55, 0.2); olho_arregalado(1, 1.0, 0.55, 0.2); sobrancelha(0, -0.6); sobrancelha(1, -0.6)
			boca_dentes(0.8); gota_suor()
		"concentrado":
			olho_fechado(0, -0.5); olho_fechado(1, -0.5); sobrancelha(0, 0.3); sobrancelha(1, 0.3); boca_linha(0.5)
		_:
			olho_aberto(0); olho_aberto(1); boca_sorriso(0.8)
	ci.draw_set_transform_matrix(base)
