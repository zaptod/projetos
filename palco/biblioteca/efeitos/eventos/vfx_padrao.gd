extends PecaPalco
## VFX PADRAO dos eventos da luta: faisca de acerto por TIER, defesa, parede,
## esquiva, dash, skill, KO, escudo quebrado, cura, destrocos e (revisao 3 da
## timeline) a explosao no ponto do impacto e o choque de projeteis no ar.
##
## Arte CC0 (biblioteca/LICENCAS.md): mascaras BRANCAS do Kenney tingidas pela
## cor do tier ou pela paleta do ELEMENTO, em mistura aditiva (a camada
## "Luz"), e as sequencias da Sinestesia (acerto forte, KO) e da poeira do
## Kenney em mistura normal. O que nao tem arte ainda e procedural.
##
## Tudo DETERMINISTICO: a "aleatoriedade" sai de UtilPalco.ruido(semente, k),
## com a semente tirada do passo do evento. O relogio e o do JOGO
## (`ctx.dt_mundo`): no hitstop a faisca congela junto com o mundo, no slow-mo
## do KO ela anda devagar. A peca se apaga sozinha quando acaba (`vida`). Um
## efeito proprio entra como efeitos/eventos/<tipo>.tscn ou
## <tipo>_<tier>.tscn (acerto_heavy.tscn, por exemplo).

const TEX_ESTRELA := preload("res://biblioteca/efeitos/texturas/estrela.png")
const TEX_ESTRELA_LARGA := preload("res://biblioteca/efeitos/texturas/estrela_larga.png")
const TEX_ANEL := preload("res://biblioteca/efeitos/texturas/anel.png")
const TEX_ONDA := preload("res://biblioteca/efeitos/texturas/onda.png")
const TEX_FAISCA := preload("res://biblioteca/efeitos/texturas/faisca.png")
const TEX_BRILHO := preload("res://biblioteca/efeitos/texturas/brilho.png")
const SEQ_FORTE := preload("res://biblioteca/efeitos/sequencias/acerto_forte_4x4.png")
const SEQ_KO := preload("res://biblioteca/efeitos/sequencias/ko_8x8.png")
const SEQ_POEIRA := preload("res://biblioteca/efeitos/sequencias/poeira_4x2.png")

const TIERS := {
	"light": {"n": 8, "alcance": 0.55, "anel": 0.55, "vida": 0.30},
	"medium": {"n": 12, "alcance": 0.75, "anel": 0.75, "vida": 0.36},
	"heavy": {"n": 18, "alcance": 1.0, "anel": 1.05, "vida": 0.44},
	"colossal": {"n": 26, "alcance": 1.35, "anel": 1.5, "vida": 0.58},
}

var tipo := "acerto"
var dados: Dictionary = {}
var idade := 0.0
var vida := 0.4
var semente := 1
var cor := Color.WHITE
var _ctx: Dictionary = {}
var _luz: Node2D


func configurar(evento: Dictionary, ctx: Dictionary) -> void:
	dados = evento
	tipo = str(evento.get("tipo", "acerto"))
	semente = int(evento.get("i", 0)) * 131 + absi(tipo.hash()) % 997
	_ctx = ctx
	match tipo:
		"acerto":
			var tier := str(evento.get("tier", "light"))
			vida = TIERS.get(tier, TIERS["light"])["vida"]
			if tier in ["heavy", "colossal"]:
				vida = maxf(vida, 0.5)
			cor = UtilPalco.cor(UtilPalco.COR_TIER.get(tier, 0xFFF6C8))
		"ko":
			vida = 1.1
			cor = Color(1, 0.95, 0.8)
		"skill":
			vida = 0.5
			cor = UtilPalco.cor(UtilPalco.paleta(str(evento.get("elemento", ""))).get("mid")[0])
		"parede", "wall_splat", "obstaculo":
			vida = 0.55 if tipo == "parede" else 0.8
			cor = Color8(205, 190, 165)
		"bloqueio", "parry":
			vida = 0.28
			cor = Color8(170, 220, 255) if tipo == "bloqueio" else Color8(255, 225, 120)
		"esquiva", "desvio", "dash":
			vida = 0.32
			cor = Color8(190, 230, 255)
		"escudo_quebrou":
			vida = 0.5
			cor = Color8(150, 230, 255)
		"cura":
			vida = 0.7
			cor = Color8(120, 255, 140)
		"explosao":
			# a paleta do ELEMENTO (a DramaticExplosion do render); a da area
			# (timer, raio de explosao, meteoro) traz so a cor
			vida = 0.55
			var el := str(evento.get("elemento", ""))
			if el != "" and el.to_upper() != "DEFAULT":
				cor = UtilPalco.cor(UtilPalco.paleta(el).get("mid")[0])
			elif evento.has("cor"):
				cor = UtilPalco.cor(evento.get("cor"))
			else:
				cor = UtilPalco.cor(UtilPalco.paleta("DEFAULT").get("mid")[0])
		"choque":
			vida = 0.5
			cor = UtilPalco.cor(evento.get("cor1", 0xFFE664))
		_:
			vida = 0.3
			cor = Color8(255, 120, 120)
	# camada de LUZ (aditiva) por cima da camada normal desta peca
	_luz = Node2D.new()
	_luz.name = "Luz"
	var mat := CanvasItemMaterial.new()
	mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	_luz.material = mat
	add_child(_luz)
	_luz.draw.connect(_desenhar_luz)


func atualizar(_amostra: Dictionary, ctx: Dictionary) -> void:
	_ctx = ctx
	idade += float(ctx.get("dt_mundo", 1.0 / 30.0))
	if idade >= vida:
		queue_free()
		return
	queue_redraw()
	_luz.queue_redraw()


func _r(k: int) -> float:
	return UtilPalco.ruido(semente, k)


func _escala() -> float:
	var estilo: EstiloPalco = _ctx.get("estilo")
	return estilo.faisca_escala if estilo else 1.0


## Um quadro de uma sequencia (atlas colunas x linhas) centrado em `c`.
func _sequencia(tex: Texture2D, colunas: int, linhas: int, f: float, tamanho: float, c := Vector2.ZERO, mod := Color.WHITE) -> void:
	var total := colunas * linhas
	var k := clampi(int(f * total), 0, total - 1)
	var q := Vector2(tex.get_width() / float(colunas), tex.get_height() / float(linhas))
	var origem := Rect2(Vector2((k % colunas) * q.x, (k / colunas) * q.y), q)
	draw_texture_rect_region(tex, Rect2(c - Vector2(tamanho, tamanho) / 2.0, Vector2(tamanho, tamanho)), origem, mod)


func _mascara(no: CanvasItem, tex: Texture2D, tamanho: float, mod: Color, c := Vector2.ZERO, ang := 0.0) -> void:
	no.draw_set_transform(c, ang)
	no.draw_texture_rect(tex, Rect2(-Vector2(tamanho, tamanho) / 2.0, Vector2(tamanho, tamanho)), false, mod)
	no.draw_set_transform(Vector2.ZERO)


# ------------------------------------------------------------ camada normal
func _draw() -> void:
	var M := UtilPalco.PX_POR_M
	var f := clampf(idade / vida, 0.0, 1.0)
	var some := 1.0 - f
	match tipo:
		"acerto":
			var tier := str(dados.get("tier", "light"))
			if tier in ["heavy", "colossal"]:
				var p: Dictionary = TIERS[tier]
				_sequencia(SEQ_FORTE, 4, 4, f, float(p["alcance"]) * M * 2.6 * _escala(), Vector2.ZERO, Color(1, 1, 1, 0.95))
		"ko":
			_sequencia(SEQ_KO, 8, 8, f, M * 4.2 * _escala())
		"parede", "wall_splat", "obstaculo":
			var forte := 1.8 if tipo != "parede" else clampf(float(dados.get("intensidade", 6.0)) / 8.0, 0.6, 1.3)
			_sequencia(SEQ_POEIRA, 4, 2, f, M * 1.3 * forte, Vector2.ZERO, Color(cor.r, cor.g, cor.b, 0.8))
			if tipo == "wall_splat":
				for k in 6:
					var a := _r(k + 50) * TAU
					var d := Vector2(cos(a), sin(a))
					draw_line(Vector2.ZERO, d * M * 0.9 * (0.5 + _r(k + 60)), Color(0.15, 0.12, 0.1, 0.8 * some), 5.0, true)
		"dash":
			var v := Vector2(float(dados.get("vx", 1.0)), float(dados.get("vy", 0.0)))
			var d := v.normalized() if v.length() > 0.01 else Vector2.RIGHT
			var n := Vector2(-d.y, d.x)
			for k in 5:
				var lat := (k - 2) * M * 0.22
				draw_line(n * lat - d * M * (0.4 + 0.5 * f), n * lat - d * M * (1.3 + 0.9 * f), Color(cor.r, cor.g, cor.b, 0.6 * some), 4.0, true)
			_sequencia(SEQ_POEIRA, 4, 2, f, M * 0.9, -d * M * 0.5, Color(0.9, 0.95, 1.0, 0.5))
		"escudo_quebrou":
			for k in 9:
				var a := k * TAU / 9.0 + _r(k)
				var d := Vector2(cos(a), sin(a))
				var c := d * M * (1.0 + 1.3 * f)
				var nn := Vector2(-d.y, d.x)
				draw_colored_polygon(PackedVector2Array([c + d * 14.0, c + nn * 9.0, c - nn * 9.0]), Color(cor.r, cor.g, cor.b, some))


# ------------------------------------------------------------ camada de luz
func _desenhar_luz() -> void:
	var M := UtilPalco.PX_POR_M
	var f := clampf(idade / vida, 0.0, 1.0)
	var some := 1.0 - f
	var sai := 1.0 - pow(1.0 - f, 3.0)
	var esc := _escala()
	match tipo:
		"acerto":
			var p: Dictionary = TIERS.get(str(dados.get("tier", "light")), TIERS["light"])
			var alcance := float(p["alcance"]) * M * esc
			var dir := deg_to_rad(float(dados.get("dir", 0.0)))
			# estrela do impacto, onda que cresce e faiscas em leque na direcao do golpe
			_mascara(_luz, TEX_ESTRELA if str(dados.get("tier")) == "light" else TEX_ESTRELA_LARGA,
				alcance * (1.6 - 0.6 * f), Color(cor.r, cor.g, cor.b, some), Vector2.ZERO, _r(1) * TAU + f * 0.8)
			_mascara(_luz, TEX_ONDA, float(p["anel"]) * M * esc * (0.6 + 1.6 * sai), Color(cor.r, cor.g, cor.b, 0.85 * some))
			if idade < 0.08:
				_mascara(_luz, TEX_BRILHO, alcance * 1.4, Color(1, 1, 1, 0.9))
			var n := int(p["n"] * (1.0 + clampf(float(dados.get("dano_pct", 0.0)) * 4.0, 0.0, 0.6)))
			for k in n:
				var a := dir + (_r(k) - 0.5) * 2.4
				var dist := alcance * (0.45 + 0.55 * _r(k + 100)) * sai
				var comp := alcance * 0.22 * (0.5 + _r(k + 200)) * some
				var d := Vector2(cos(a), sin(a))
				_luz.draw_line(d * dist, d * (dist + comp), Color(1, 1, 0.85, some).lerp(cor, 0.5), maxf(2.0, alcance * 0.035 * some), true)
			if dados.get("critico", false):
				_mascara(_luz, TEX_ANEL, alcance * 2.4 * sai, Color(1, 0.85, 0.2, some))
		"ko":
			for k in 2:
				_mascara(_luz, TEX_ONDA, M * (2.0 + 5.0 * sai) * (1.0 + k * 0.5), Color(1, 0.95, 0.8, 0.8 * some / (k + 1)))
			_mascara(_luz, TEX_BRILHO, M * 3.0 * (1.0 - f * 0.5), Color(1, 1, 0.9, 0.7 * some))
		"skill":
			_mascara(_luz, TEX_BRILHO, M * (1.4 + 1.2 * f), Color(cor.r, cor.g, cor.b, 0.55 * some))
			_mascara(_luz, TEX_ONDA, M * (1.0 + 2.2 * sai), Color(cor.r, cor.g, cor.b, 0.8 * some))
		"bloqueio", "parry":
			var ang := deg_to_rad(float(dados.get("ang", 0.0)))
			_luz.draw_arc(Vector2.ZERO, M * (0.9 + 0.4 * f), ang - 1.0, ang + 1.0, 24, Color(cor.r, cor.g, cor.b, some), 12.0 * some + 2.0, true)
			if tipo == "parry":
				_mascara(_luz, TEX_FAISCA, M * 1.6, Color(1, 0.9, 0.6, some), Vector2(cos(ang), sin(ang)) * M * 0.9, ang)
		"esquiva", "desvio":
			_mascara(_luz, TEX_ANEL, M * (1.6 + 1.0 * f), Color(cor.r, cor.g, cor.b, 0.5 * some))
		"cura":
			for k in 5:
				var c := Vector2((_r(k) - 0.5) * M * 1.2, -M * (0.3 + 1.2 * f) - _r(k + 9) * M * 0.4)
				_luz.draw_line(c - Vector2(12, 0), c + Vector2(12, 0), Color(cor.r, cor.g, cor.b, some), 6.0, true)
				_luz.draw_line(c - Vector2(0, 12), c + Vector2(0, 12), Color(cor.r, cor.g, cor.b, some), 6.0, true)
		"escudo_quebrou":
			_mascara(_luz, TEX_ONDA, M * (1.5 + 2.0 * sai), Color(cor.r, cor.g, cor.b, 0.7 * some))
		"explosao":
			var tam := clampf(float(dados.get("tamanho", 1.0)), 0.4, 3.0) * esc
			if idade < 0.1:
				_mascara(_luz, TEX_BRILHO, M * 1.3 * tam, Color(1, 1, 0.95, 0.9))
			_mascara(_luz, TEX_BRILHO, M * (0.9 + 0.6 * f) * tam, Color(cor.r, cor.g, cor.b, 0.7 * some))
			_mascara(_luz, TEX_ONDA, M * (0.5 + 1.7 * sai) * tam, Color(cor.r, cor.g, cor.b, 0.85 * some))
			for k in 10:
				var a := k * TAU / 10.0 + _r(k) * 0.5
				var d := Vector2(cos(a), sin(a))
				var dist := M * tam * (0.25 + 0.75 * sai)
				_luz.draw_line(d * dist, d * (dist + M * 0.25 * tam * some), Color(cor.r, cor.g, cor.b, some), maxf(2.0, 5.0 * some), true)
		"choque":
			var cor2 := UtilPalco.cor(dados.get("cor2", 0xFFFFFF))
			if idade < 0.08:
				_mascara(_luz, TEX_BRILHO, M * 1.8, Color(1, 1, 1, 0.9))
			_mascara(_luz, TEX_ESTRELA_LARGA, M * 1.9 * (1.2 - 0.5 * f), Color(cor.r, cor.g, cor.b, some), Vector2.ZERO, _r(1) * TAU + f)
			_mascara(_luz, TEX_ONDA, M * (0.7 + 2.3 * sai), Color(cor2.r, cor2.g, cor2.b, 0.8 * some))
			_mascara(_luz, TEX_ONDA, M * (0.4 + 1.5 * sai), Color(cor.r, cor.g, cor.b, 0.6 * some))
		"parede", "wall_splat", "obstaculo", "dash":
			pass
		_:
			_mascara(_luz, TEX_BRILHO, M * 0.8 * (0.5 + f), Color(cor.r, cor.g, cor.b, 0.5 * some))
