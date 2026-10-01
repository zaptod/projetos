extends "res://biblioteca/armas/arma_padrao.gd"
## A CORRENTE NOVA no palco (rework de 01/10/2026, F3): a corrente presa na
## MAO e na BOLA, com fisica de Verlet SEM ESTADO.
##
## A bola e a do motor (canais `bola_*` da timeline revisao 4, cabecalho
## `arma.corrente`). A corrente entre a mao e a bola e so desenho: a cada
## quadro ela e REINTEGRADA desde a ancora mais recente (inicio do golpe,
## ultimo repouso da bola ou a grade de 30 passos), no maximo 60 passos atras,
## usando so a timeline. Sem relogio, sem RNG e sem nada guardado de um
## quadro para o outro: o mesmo passo da sempre a mesma corrente, entao seek,
## corte de tedio, camera lenta e hitstop funcionam sozinhos (o hitstop e o
## passo em que o tempo de jogo `tj` nao anda: a corrente nao anda junto).
##
## Os elos sao desenhados por codigo por enquanto (frente/lado alternados,
## contorno #14141A); a ARTE vem depois pela esteira de sprites.
##
## Luta SEM a chave (corrente antiga, ou timeline < 4): nao ha `bola_*` e a
## peca desenha a corrente antiga da arma padrao, como antes.

const PASSOS_MAX := 60          # janela maxima de reintegracao (1 s a 60 Hz)
const GRADE := 30               # ancora de grade: a janela fica entre 30 e 60 passos
const SEGMENTOS_MAX := 14       # pontos da fisica; os elos se distribuem na curva
const ITERACOES := 12           # relaxacao das restricoes por subpasso (ida e volta)
const SUBPASSOS_MAX := 6        # subpassos por passo do motor (bola rapida)
const ACABAMENTO := 4           # rodadas extras de relaxacao so no quadro mostrado
const AMORTECE := 0.88          # inercia que sobra por passo de 1/60 s de jogo
const FOLGA := 1.06             # corrente visivel = distancia mao-bola x folga (<= comp)
const REPOUSO_FRAC := 0.06      # bola quase parada em relacao a mao (fracao de v_ref)
const RASTRO_PASSOS := 9        # passos de rastro atras da bola
const RASTRO_MIN_FRAC := 0.25   # abaixo disto (v / v_ref) nao ha rastro

const ELO := Color8(170, 176, 190)
const ELO_CLARO := Color8(222, 226, 236)
const ELO_ESCURO := Color8(96, 100, 114)
const COURO := Color8(104, 66, 38)
const COURO_CLARO := Color8(150, 104, 62)
const CORDA := Color8(186, 160, 112)
const CORDA_ESCURA := Color8(132, 108, 70)

## Com a bola (revisao 4), o palco nao desenha o rastro generico (a ponta
## antiga de 4 raios) desta arma: o rastro aqui e o da BOLA, proporcional a
## velocidade dela. Sem a bola, a corrente antiga segue com o rastro de antes.
var rastro_proprio := false

var _slot := "p1"
var _corr: Dictionary = {}
var _raio_m := 0.85
var _comp_px := 250.0
var _rb_px := 20.0
var _v_ref := 30.0
var _n_elos := 16
var _cabeca := "bola_espinhos"
var _material := "elos"
var _mao_av := 0.9
var _mao_lat := 0.15
var _canais: Dictionary = {}    # nome -> Array (leitura da timeline, so cache)
var _n := 0
var _ativo := false
var _pontos := PackedVector2Array()   # a corrente neste quadro (mundo, px)
# Trabalho da integracao: refeitos do zero a cada quadro (nao e estado).
var _pp := PackedVector2Array()
var _pa := PackedVector2Array()
var _h_ant := 1.0
var _rastro := PackedVector2Array()
var _rastro_v := PackedFloat32Array()
var _dir_bola := Vector2.RIGHT


func configurar(dados: Dictionary, c: Dictionary) -> void:
	super.configurar(dados, c)
	_slot = str(dados.get("slot", "p1"))
	_corr = dados.get("corrente") if typeof(dados.get("corrente")) == TYPE_DICTIONARY else {}
	_raio_m = float(dados.get("raio_corpo", 0.85))
	rastro_proprio = not _corr.is_empty()
	if _corr.is_empty():
		return
	_comp_px = float(_corr.get("comp_m", 2.5)) * UtilPalco.PX_POR_M
	_rb_px = float(_corr.get("raio_bola_m", 0.2)) * UtilPalco.PX_POR_M
	_v_ref = maxf(1.0, float(_corr.get("v_ref_ms", 30.0)))
	_n_elos = clampi(int(_corr.get("n_elos", 16)), 2, 60)
	_cabeca = str(_corr.get("cabeca", "bola_espinhos"))
	_material = str(_corr.get("material", "elos"))
	var mao = _corr.get("mao")
	if typeof(mao) == TYPE_DICTIONARY:
		_mao_av = float(mao.get("avanco_r", 0.9))
		_mao_lat = float(mao.get("lateral_r", 0.15))


func atualizar(amostra: Dictionary, ctx: Dictionary) -> void:
	super.atualizar(amostra, ctx)
	_ativo = false
	if _corr.is_empty() or not amostra.has("bola_x"):
		return
	var tl = ctx.get("timeline")
	if tl == null or not ctx.has("passo"):
		return
	if _canais.is_empty():
		_ler_canais(tl)
	if _n < 2:
		return
	_ativo = _integrar(clampf(float(ctx["passo"]), 0.0, float(_n - 1)))


func _ler_canais(tl) -> void:
	for nome in ["x", "y", "z", "ang", "flags", "golpe_id", "arma_gx", "arma_gy",
			"bola_x", "bola_y", "bola_vx", "bola_vy"]:
		_canais[nome] = tl.canal_lutador(_slot, nome)
	var g = tl.trilhas().get("global", {}).get("tj", [])
	_canais["tj"] = g if typeof(g) == TYPE_ARRAY else []
	_n = int(tl.n)
	for nome in _canais:
		if (_canais[nome] as Array).size() != _n:
			_n = 0


# ------------------------------------------------------------------ geometria
func _v(nome: String, k: int) -> float:
	return float(_canais[nome][k])


func _morto(k: int) -> bool:
	return (int(_v("flags", k)) & 2) != 0


## A MAO no passo k (mundo, px), levantada pelo pulo: a mesma conta de
## `corrente.mao` (no olhar, avanco e lateral em fracoes do raio). Morto, a
## arma caida (a empunhadura da timeline, no chao).
func _mao(k: int) -> Vector2:
	if _morto(k):
		return Vector2(_v("arma_gx", k), _v("arma_gy", k)) * UtilPalco.PX_POR_M
	var a := deg_to_rad(_v("ang", k))
	var p := Vector2(_v("x", k), _v("y", k))
	p += Vector2(cos(a), sin(a)) * _raio_m * _mao_av
	p += Vector2(cos(a + PI / 2.0), sin(a + PI / 2.0)) * _raio_m * _mao_lat
	p.y -= _v("z", k)
	return p * UtilPalco.PX_POR_M


func _bola(k: int, mao: Vector2) -> Vector2:
	var z := 0.0 if _morto(k) else _v("z", k)
	var b := Vector2(_v("bola_x", k), _v("bola_y", k) - z) * UtilPalco.PX_POR_M
	var d := b - mao
	if d.length() > _comp_px:
		# morto, a bola ficou onde estava e a arma caiu em outro lugar
		b = mao + d.normalized() * _comp_px
	return b


func _vel_bola(k: int) -> Vector2:
	return Vector2(_v("bola_vx", k), _v("bola_vy", k))


## Passo k e uma ANCORA: o golpe comecou nele, ou a bola esta parada em
## relacao a mao (repouso: a corrente tem a forma de descanso, que e a forma
## inicial da integracao).
func _ancora(k: int) -> bool:
	if k <= 0:
		return true
	if int(_v("golpe_id", k)) != int(_v("golpe_id", k - 1)):
		return true
	var vm := (_mao(k) - _mao(k - 1)) / UtilPalco.PX_POR_M * 60.0
	return (_vel_bola(k) - vm).length() < REPOUSO_FRAC * _v_ref


## O passo de onde a integracao parte: a ancora mais recente nos ultimos
## PASSOS_MAX passos (o golpe inteiro, 0,95 s, cabe numa integracao so); sem
## ancora, a grade de 30 passos (janela de 30 a 59: a forma inicial ja foi
## esquecida, 0,88^30 = 2%, e a troca de grade nao salta).
func _inicio(i: int) -> int:
	var limite := maxi(0, i - PASSOS_MAX)
	var k := i
	while k >= limite:
		if _ancora(k):
			return k
		k -= 1
	return maxi(limite, i - i % GRADE - GRADE)


func _comp_visivel(mao: Vector2, bola: Vector2) -> float:
	var d := mao.distance_to(bola)
	return clampf(d * FOLGA, d, maxf(d, _comp_px))


## Forma de descanso: um arco suave da mao a bola, com a folga para o lado
## de onde a bola veio (a corrente fica para tras do movimento).
func _forma_inicial(mao: Vector2, bola: Vector2, vb: Vector2, nseg: int) -> PackedVector2Array:
	var pts := PackedVector2Array()
	var d := mao.distance_to(bola)
	var eixo := (bola - mao).normalized() if d > 1e-3 else Vector2.RIGHT
	var perp := Vector2(-eixo.y, eixo.x)
	var lado := -signf(vb.dot(perp)) if absf(vb.dot(perp)) > 1e-3 else 1.0
	var L := _comp_visivel(mao, bola)
	var flecha := sqrt(maxf(0.0, 0.375 * d * (L - d))) * lado
	for j in nseg + 1:
		var u := float(j) / nseg
		pts.append(mao.lerp(bola, u) + perp * flecha * 4.0 * u * (1.0 - u))
	return pts


## Restricoes de distancia (Jakobsen): as pontas presas na mao e na bola,
## cada segmento com o mesmo comprimento. Mexe em `_pp` (o quadro atual).
func _relaxar(mao: Vector2, bola: Vector2, seg: float) -> void:
	var ult := _pp.size() - 1
	for it in ITERACOES:
		_pp[0] = mao
		_pp[ult] = bola
		# ida e volta alternadas: a correcao chega as duas pontas mais rapido
		for jj in ult:
			var j := jj if it % 2 == 0 else ult - 1 - jj
			var a := _pp[j]
			var b := _pp[j + 1]
			var delta := b - a
			var dist := delta.length()
			if dist < 1e-6:
				continue
			var corr := delta * ((dist - seg) / dist)
			if j == 0:
				_pp[j + 1] = b - corr
			elif j + 1 == ult:
				_pp[j] = a + corr
			else:
				_pp[j] = a + corr * 0.5
				_pp[j + 1] = b - corr * 0.5
	_pp[0] = mao
	_pp[ult] = bola


## Reintegra a corrente ate o passo fracionario `p`. Puro: so le a timeline.
func _integrar(p: float) -> bool:
	var i := int(floor(p))
	var w := p - float(i)
	var nseg := clampi(_n_elos, 4, SEGMENTOS_MAX)
	var s0 := _inicio(i)
	var mao := _mao(s0)
	var bola := _bola(s0, mao)
	_pp = _forma_inicial(mao, bola, _vel_bola(s0), nseg)
	_pa = _pp.duplicate()
	_h_ant = 1.0
	if s0 > 0:
		# velocidade inicial: cada ponto anda entre a mao e a bola do passo anterior
		var mao_a := _mao(s0 - 1)
		var dm := mao - mao_a
		var db := bola - _bola(s0 - 1, mao_a)
		for j in nseg + 1:
			_pa[j] = _pp[j] - dm.lerp(db, float(j) / nseg)
	for k in range(s0 + 1, i + 1):
		_passo(k, 1.0)
	if w > 1e-4 and i + 1 < _n:
		_passo(i + 1, w)
	# acabamento so do que aparece: mais relaxacao nas pontas deste quadro
	# (nao volta para a integracao; a corrente fica no comprimento)
	var ult := _pp.size() - 1
	for _r in ACABAMENTO:
		_relaxar(_pp[0], _pp[ult], _comp_visivel(_pp[0], _pp[ult]) / float(ult))
	var pts := _pp
	_pontos = _pp.duplicate()
	_montar_rastro(p)
	var vb := _vel_bola(mini(i + (1 if w > 0.5 else 0), _n - 1))
	if vb.length() > 0.5:
		_dir_bola = vb.normalized()
	else:
		var e := pts[nseg] - pts[nseg - 1]
		_dir_bola = e.normalized() if e.length() > 1e-3 else Vector2.RIGHT
	return true


## Um passo de Verlet ate o passo k (fracao `f` dele: o passo parcial do
## quadro entre dois passos). O passo em que o tempo de jogo nao anda
## (hitstop) congela a corrente junto com o mundo.
func _passo(k: int, f: float) -> void:
	var dtj := (_v("tj", k) - _v("tj", k - 1)) * 60.0
	if dtj <= 1e-6:
		return
	var mao_0 := _mao(k - 1)
	var bola_0 := _bola(k - 1, mao_0)
	var mao_k := _mao(k)
	var mao_f := mao_0.lerp(mao_k, f)
	var bola_f := bola_0.lerp(_bola(k, mao_k), f)
	var ult := _pp.size() - 1
	# a bola anda ate 0,5 m num passo: em subpassos, nenhuma ponta anda mais
	# que um elo por vez e a corrente nao estica atras dela
	var seg := maxf(1.0, _comp_visivel(mao_f, bola_f) / float(ult))
	var desloc := maxf(mao_0.distance_to(mao_f), bola_0.distance_to(bola_f))
	if desloc > seg * SUBPASSOS_MAX:
		# SALTO (empurrao, puxao do enlace, teleporte): uma ponta andou mais
		# que a corrente acompanha num passo. A corrente se refaz na forma de
		# descanso ali, em vez de esticar alem do comprimento.
		var v := (bola_f - bola_0) / UtilPalco.PX_POR_M * 60.0
		_pp = _forma_inicial(mao_f, bola_f, v, ult)
		_pa = _pp.duplicate()
		_h_ant = dtj * f
		return
	var subs := clampi(ceili(desloc / seg), 1, SUBPASSOS_MAX)
	var h := dtj * f / float(subs)
	var razao := h / maxf(_h_ant, 1e-6)
	_h_ant = h
	var amortece := pow(AMORTECE, h)
	for sub in subs:
		var u := float(sub + 1) / float(subs)
		var m := mao_0.lerp(mao_f, u)
		var b := bola_0.lerp(bola_f, u)
		for j in range(1, ult):
			var atual := _pp[j]
			_pp[j] = atual + (atual - _pa[j]) * amortece * razao
			_pa[j] = atual
		_pa[0] = _pp[0]
		_pa[ult] = _pp[ult]
		_relaxar(m, b, _comp_visivel(m, b) / float(ult))
		razao = 1.0


func _montar_rastro(p: float) -> void:
	_rastro = PackedVector2Array()
	_rastro_v = PackedFloat32Array()
	var i := int(floor(p))
	for k in range(maxi(0, i - RASTRO_PASSOS), i + 1):
		var m := _mao(k)
		_rastro.append(_bola(k, m))
		_rastro_v.append(_vel_bola(k).length() / _v_ref)


# ------------------------------------------------------------------ desenho
func _draw() -> void:
	if not _ativo or _pontos.size() < 2:
		super._draw()
		return
	var local := PackedVector2Array()
	for q in _pontos:
		local.append(do_mundo(q))
	_desenhar_rastro()
	match _material:
		"couro":
			_cordao(local, COURO, COURO_CLARO, 0.20, 0.07, false)
		"corda":
			_cordao(local, CORDA, CORDA_ESCURA, 0.16, 0.12, true)
		_:
			_elos(local)
	_cabo(local)
	_desenhar_cabeca(local)


func _desenhar_rastro() -> void:
	if _rastro.size() < 2:
		return
	var tam := _rastro.size()
	for j in range(1, tam):
		var v := clampf(maxf(_rastro_v[j], _rastro_v[j - 1]), 0.0, 1.6)
		if v < RASTRO_MIN_FRAC:
			continue
		var idade := float(j) / float(tam - 1)   # 1 = agora
		var forca := clampf((v - RASTRO_MIN_FRAC) / (1.0 - RASTRO_MIN_FRAC), 0.0, 1.0)
		var a := do_mundo(_rastro[j - 1])
		var b := do_mundo(_rastro[j])
		if a.distance_to(b) < 0.5:
			continue
		var cor := cor_arma.lerp(Color.WHITE, 0.55)
		cor.a = 0.55 * forca * idade
		draw_line(a, b, cor, maxf(1.5, _rb_px * 1.7 * forca * (0.35 + 0.65 * idade)), true)


## Elos alternados: o de FRENTE e um anel (a argola vista de cima), o de LADO
## e uma barra (a argola de perfil). Distribuidos por comprimento de arco.
func _elos(pts: PackedVector2Array) -> void:
	var total := 0.0
	var acum := PackedFloat32Array([0.0])
	for j in range(1, pts.size()):
		total += pts[j].distance_to(pts[j - 1])
		acum.append(total)
	if total < 1.0:
		return
	var n := _n_elos
	var passo := total / n
	var comp_elo := passo * 1.3
	var larg := maxf(3.0, minf(comp_elo * 0.62, raio_px * 0.16))
	var contorno := _contorno()
	var cor_c := _cor_contorno()
	var seg := 0
	for e in n:
		var s := (e + 0.5) * passo
		while seg < pts.size() - 2 and acum[seg + 1] < s:
			seg += 1
		var l := maxf(1e-3, acum[seg + 1] - acum[seg])
		var u := clampf((s - acum[seg]) / l, 0.0, 1.0)
		var c := pts[seg].lerp(pts[seg + 1], u)
		var t := (pts[seg + 1] - pts[seg]).normalized()
		var ang := t.angle()
		if e % 2 == 0:
			# frente: anel achatado
			draw_set_transform(c, ang, Vector2(1.0, larg / comp_elo))
			draw_arc(Vector2.ZERO, comp_elo * 0.5, 0.0, TAU, 18, cor_c, maxf(2.0, larg * 0.42 + contorno), true)
			draw_arc(Vector2.ZERO, comp_elo * 0.5, 0.0, TAU, 18, ELO, maxf(1.2, larg * 0.42), true)
			draw_arc(Vector2.ZERO, comp_elo * 0.5, PI * 1.1, PI * 1.6, 8, ELO_CLARO, maxf(0.8, larg * 0.16), true)
			draw_set_transform(Vector2.ZERO)
		else:
			# lado: barra de perfil
			var meio := t * comp_elo * 0.5
			draw_line(c - meio, c + meio, cor_c, larg * 0.5 + contorno, true)
			draw_line(c - meio, c + meio, ELO_ESCURO, larg * 0.5, true)
			draw_line(c - meio * 0.7, c + meio * 0.7, ELO_CLARO, maxf(0.8, larg * 0.14), true)


## Couro (Chicote) e corda (Meteor Hammer, Rope Dart): cordao que afina da
## mao para a ponta; a corda ganha as marcas de torcao alternadas.
func _cordao(pts: PackedVector2Array, cor: Color, cor2: Color, w0_r: float, w1_r: float, torcida: bool) -> void:
	var w0 := maxf(3.0, raio_px * w0_r)
	var w1 := maxf(1.5, raio_px * w1_r)
	var ult := pts.size() - 1
	var contorno := _contorno()
	for j in ult:
		var u := float(j) / ult
		var w := lerpf(w0, w1, u)
		draw_line(pts[j], pts[j + 1], _cor_contorno(), w + contorno, true)
	for j in ult:
		var u := float(j) / ult
		var w := lerpf(w0, w1, u)
		draw_line(pts[j], pts[j + 1], cor, w, true)
	if torcida:
		for j in ult:
			var a := pts[j]
			var b := pts[j + 1]
			var t := (b - a)
			if t.length() < 1.0:
				continue
			var nrm := Vector2(-t.y, t.x).normalized() * lerpf(w0, w1, float(j) / ult) * 0.45
			var meio := a.lerp(b, 0.5)
			draw_line(meio - nrm + t * 0.15, meio + nrm - t * 0.15, cor2, maxf(1.0, w1 * 0.4), true)
	else:
		for j in ult:
			var u := float(j) / ult
			draw_line(pts[j], pts[j + 1], cor2, maxf(0.8, lerpf(w0, w1, u) * 0.3), true)


func _cabo(pts: PackedVector2Array) -> void:
	var t := (pts[1] - pts[0])
	var dir := t.normalized() if t.length() > 1e-3 else Vector2.RIGHT
	var w := maxf(3.0, raio_px * 0.14)
	var a := pts[0] - dir * raio_px * 0.22
	var b := pts[0] + dir * raio_px * 0.06
	draw_line(a, b, _cor_contorno(), w + _contorno(), true)
	draw_line(a, b, MADEIRA, w, true)


func _desenhar_cabeca(pts: PackedVector2Array) -> void:
	var c := pts[pts.size() - 1]
	var r := maxf(4.0, _rb_px)
	var ultimo := pts[pts.size() - 1] - pts[pts.size() - 2]
	var fora := ultimo.normalized() if ultimo.length() > 1e-3 else Vector2.RIGHT
	var giro := _dir_bola.rotated(-rotation).angle()
	var metal := cor_arma.lerp(METAL_ESCURO, 0.35)
	match _cabeca:
		"bola_espinhos":
			for k in 8:
				var a := giro + k * TAU / 8.0
				_poligono(PackedVector2Array([c + Vector2.from_angle(a - 0.32) * r * 0.85,
					c + Vector2.from_angle(a) * r * 1.5, c + Vector2.from_angle(a + 0.32) * r * 0.85]), METAL)
			_bola_cheia(c, r, metal)
		"martelo":
			_bola_cheia(c, r * 1.05, cor_arma.lerp(METAL_ESCURO, 0.55))
			draw_arc(c, r * 0.7, giro, giro + PI * 0.6, 10, Color(1, 1, 1, 0.35), maxf(1.0, r * 0.12), true)
		"peso":
			var f := fora
			var p := Vector2(-f.y, f.x)
			_poligono(PackedVector2Array([c - f * r * 0.7 - p * r * 0.8, c + f * r * 1.1 - p * r * 0.8,
				c + f * r * 1.1 + p * r * 0.8, c - f * r * 0.7 + p * r * 0.8]), metal)
		"ponta":
			var p := Vector2(-fora.y, fora.x)
			_poligono(PackedVector2Array([c - p * r * 0.9, c + fora * r * 2.4, c + p * r * 0.9]), COURO_CLARO)
		"dardo":
			var p := Vector2(-fora.y, fora.x)
			_poligono(PackedVector2Array([c - fora * r * 0.4, c + p * r * 0.9, c + fora * r * 3.0, c - p * r * 0.9]),
				METAL.lerp(cor_arma, 0.3))
		"foice":
			var p := Vector2(-fora.y, fora.x)
			var lamina := PackedVector2Array()
			for k in 9:
				var u := float(k) / 8.0
				lamina.append(c + fora * r * (0.2 + 1.8 * u) + p * r * 2.2 * sin(u * PI * 0.9))
			for k in range(8, -1, -1):
				var u := float(k) / 8.0
				lamina.append(c + fora * r * (0.2 + 1.6 * u) + p * r * 1.4 * sin(u * PI * 0.9))
			_poligono(lamina, METAL.lerp(cor_arma, 0.25))
			_bola_cheia(c, r * 0.55, MADEIRA)
		_:
			_bola_cheia(c, r, metal)


func _bola_cheia(c: Vector2, r: float, cor: Color) -> void:
	draw_circle(c, r, cor, true, -1.0, true)
	draw_arc(c, r, 0.0, TAU, 28, _cor_contorno(), _contorno(), true)
	draw_circle(c - Vector2(r, r) * 0.32, r * 0.22, Color(1, 1, 1, 0.45), true, -1.0, true)
