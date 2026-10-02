extends PecaPalco
## O lutador PADRAO: a bolinha do jogo, fiel ao circulo da simulacao (raio =
## tamanho/2, o circulo que o jogo desenha), com arte vetorial suavizada.
##
## Camadas: sombra de contato no chao -> corpo (levantado por z, com squash)
## -> rosto (as 24 expressoes com as pecas do Kenney, girando com o olhar)
## -> marcas de status.
## Para trocar: crie lutadores/classes/<classe>.tscn ou lutadores/nomes/<nome>.tscn
## (veja docs/palco/COMO-EDITAR.md). Esta peca e a reserva de todas.

const FLAG_ATACANDO := 1 << 0
const FLAG_MORTO := 1 << 1
const FLAG_ATORDOADO := 1 << 2
const FLAG_CONGELADO := 1 << 3
const FLAG_INVENCIVEL := 1 << 4
const FLAG_CANALIZANDO := 1 << 5
const FLAG_ADRENALINA := 1 << 6
const FLAG_AGARRADO := 1 << 7
const FLAG_INTANGIVEL := 1 << 9
const FLAG_SUPER_ARMOR := 1 << 10
const FLAG_BLOQUEANDO := 1 << 11
const FLAG_TEMPO_PARADO := 1 << 12
const FLAG_DORMINDO := 1 << 13
const FLAG_TRANSFORMADO := 1 << 14
const FLAG_OCULTO := 1 << 16

var cor_corpo := Color8(200, 50, 50)
var cor_lado := Color8(52, 152, 219)
var raio_px := 85.0
var semente := 0
var _s: Dictionary = {}
var _ctx: Dictionary = {}
var _expressoes: Array = []
var _status: Array = []
var _pecas := {}


func configurar(dados: Dictionary, ctx: Dictionary) -> void:
	# as pecas do rosto (12x) diminuem ate ~20 px na bolinha pequena: mipmaps
	texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	cor_corpo = UtilPalco.cor(dados.get("cor", 0xC83232))
	cor_lado = UtilPalco.cor(dados.get("cor_lado", 0x3498DB))
	raio_px = float(dados.get("raio_corpo", 0.85)) * UtilPalco.PX_POR_M
	semente = 0 if dados.get("slot", "p1") == "p1" else 5
	_expressoes = ctx.get("timeline").tabela("expressoes") if ctx.get("timeline") else []


func atualizar(amostra: Dictionary, ctx: Dictionary) -> void:
	_s = amostra
	_ctx = ctx
	_status = []
	for efeito in amostra.get("_efeitos", []):
		if efeito.get("tipo") == "status":
			_status.append(efeito)
	_sincronizar_pecas()
	queue_redraw()


func _sincronizar_pecas() -> void:
	var desejadas := {}
	for par in [
		[FLAG_ATORDOADO, "atordoado"], [FLAG_BLOQUEANDO, "bloqueando"],
		[FLAG_SUPER_ARMOR, "super_armor"], [FLAG_AGARRADO, "agarrado"],
		[FLAG_TEMPO_PARADO, "tempo_parado"], [FLAG_CONGELADO, "congelado"],
		[FLAG_ADRENALINA, "adrenalina"], [FLAG_DORMINDO, "dormindo"],
	]:
		if _flag(int(par[0])):
			desejadas["estados/" + str(par[1])] = {"tipo": "estado", "nome": par[1]}
	if float(_s.get("escudo", 0.0)) > 0.0:
		desejadas["estados/escudo_bolha"] = {"tipo": "estado", "nome": "escudo_bolha"}
	for efeito in _s.get("_efeitos", []):
		var categoria := {"status": "status", "buff": "buffs", "canal": "canais", "transformacao": "transformacoes"}.get(efeito.get("tipo"), "")
		var nome := str(efeito.get("status", efeito.get("nome", "")))
		if categoria != "" and nome != "":
			desejadas[categoria + "/" + UtilPalco.slug(nome)] = efeito
	for chave in desejadas:
		var partes: PackedStringArray = str(chave).split("/")
		var categoria: String = partes[0]
		var nome: String = partes[1]
		if not _pecas.has(chave):
			var palco = _ctx.get("palco")
			var bib: Biblioteca = palco.bib if palco != null else null
			# Sem arte (nem _padrao), o desenho procedural abaixo continua sendo
			# a reserva visual; quando a cena chegar, ela sobrepoe esse desenho.
			if bib == null or not bib.tem_peca_lutador(categoria, nome):
				continue
			var nova = bib.peca_lutador(categoria, nome).instantiate()
			add_child(nova)
			_pecas[chave] = nova
			if nova.has_method("configurar"):
				nova.configurar(desejadas[chave], _ctx)
		var peca = _pecas.get(chave)
		if peca != null:
			var ref = peca.get("raio_ref")
			peca.position = Vector2(0, -float(_s.get("z", 0.0)) * UtilPalco.PX_POR_M)
			peca.scale = Vector2.ONE * raio_px / maxf(1.0, float(ref) if ref != null else 100.0)
			if peca.has_method("atualizar"):
				peca.atualizar(desejadas[chave], _ctx)
	for chave in _pecas.keys():
		if not desejadas.has(chave):
			_pecas[chave].queue_free()
			_pecas.erase(chave)


func _flag(bit: int) -> bool:
	return (int(_s.get("flags", 0)) & bit) != 0


func _draw() -> void:
	if _s.is_empty() or _flag(FLAG_OCULTO):
		return
	var estilo: EstiloPalco = _ctx.get("estilo")
	var t_jogo := float(_ctx.get("t_jogo", 0.0))
	var quadro := int(_ctx.get("quadro", 0))
	var z := float(_s.get("z", 0.0)) * UtilPalco.PX_POR_M
	var morto := _flag(FLAG_MORTO)
	var esc := Vector2(float(_s.get("esc_x", 1.0)), float(_s.get("esc_y", 1.0)))
	if morto:
		z = 0.0
		esc = Vector2.ONE
	var R := raio_px
	var alfa := 1.0
	if _flag(FLAG_INTANGIVEL):
		alfa = 0.45
	if _flag(FLAG_INVENCIVEL) and not morto and (quadro / 2) % 2 == 0:
		alfa *= 0.55

	# --- sombra de contato (achatada; encolhe com a altura do pulo) ---
	if estilo.sombra_alfa > 0.0 and not morto:
		var larg := R * 2.0 * maxf(0.4, 1.0 - z / (4.0 * UtilPalco.PX_POR_M))
		var alt := larg * estilo.sombra_achatamento
		draw_set_transform(Vector2(0, R * 0.5), 0.0, Vector2(1.0, alt / larg))
		draw_circle(Vector2.ZERO, larg * 0.5, Color(0, 0, 0, estilo.sombra_alfa * alfa), true, -1.0, true)
		draw_circle(Vector2.ZERO, larg * 0.36, Color(0, 0, 0, estilo.sombra_alfa * 0.55 * alfa), true, -1.0, true)
		draw_set_transform(Vector2.ZERO)

	var centro := Vector2(0, -z)
	# --- cor do corpo: flash de dano, congelado ---
	var cor := cor_corpo
	var flash := float(_s.get("flash", 0.0))
	if flash > 0.0:
		cor = cor_corpo.lerp(UtilPalco.cor(_s.get("flash_cor", 0xFFFFFF)), clampf(flash / 0.25, 0.0, 1.0))
	if _flag(FLAG_CONGELADO):
		cor = cor.lerp(Color8(150, 215, 255), 0.55)
	cor.a = alfa

	# --- aura fina da transformacao (estado de jogo, nao enfeite) ---
	if _flag(FLAG_TRANSFORMADO):
		draw_set_transform(centro, 0.0, esc)
		draw_arc(Vector2.ZERO, R * 1.14, 0, TAU, 64, cor_lado.lerp(Color.WHITE, 0.4), maxf(3.0, estilo.contorno_px), true)

	# --- corpo ---
	draw_set_transform(centro, 0.0, esc)
	if estilo.brilho_corpo > 0.0:
		# cel de 2 tons + 1 brilho, luz do alto a esquerda (estilo combinado da
		# 16F): o tom escuro e a lua crescente embaixo-direita que sobra quando
		# o disco claro, um pouco menor, vai para cima-esquerda.
		var sombra := cor.darkened(0.24 * estilo.brilho_corpo)
		sombra.a = alfa
		draw_circle(Vector2.ZERO, R, sombra, true, -1.0, true)
		draw_circle(Vector2(-R * 0.06, -R * 0.06), R * 0.92, cor, true, -1.0, true)
		draw_set_transform(centro + Vector2(-R * 0.40, -R * 0.44) * esc, -0.6, esc * Vector2(1.0, 0.62))
		draw_circle(Vector2.ZERO, R * 0.17, Color(1, 1, 1, 0.55 * estilo.brilho_corpo * alfa), true, -1.0, true)
		draw_set_transform(centro, 0.0, esc)
	else:
		draw_circle(Vector2.ZERO, R, cor, true, -1.0, true)

	# --- rosto (quadro do olhar; o squash vale nos eixos da tela, como no jogo) ---
	var raio_tela := R * float(_ctx.get("zoom", 1.0)) * minf(esc.x, esc.y)
	if raio_tela >= 7.0:
		var ang := deg_to_rad(float(_s.get("ang", 0.0)))
		var xf := Transform2D(Vector2(esc.x, 0), Vector2(0, esc.y), centro) * Transform2D(ang, Vector2.ZERO)
		draw_set_transform_matrix(xf)
		var expr := "neutro"
		var idx := int(_s.get("expr", 0))
		if morto:
			expr = "morto"
		elif idx >= 0 and idx < _expressoes.size():
			expr = str(_expressoes[idx])
		RostoPalco.new(self, R, t_jogo, semente, cor, raio_tela < 11.0, xf, estilo.cor_contorno).desenhar(expr)
	draw_set_transform(centro, 0.0, esc)

	# --- contorno (as mesmas regras de cor do jogo) ---
	var cor_c := estilo.cor_contorno
	var larg_c := estilo.contorno_px
	if _flag(FLAG_ATORDOADO):
		cor_c = Color8(255, 220, 60)
		larg_c *= 1.8
	elif _flag(FLAG_ATACANDO):
		cor_c = Color(1, 1, 1)
		larg_c *= 1.5
	elif flash > 0.0:
		cor_c = Color8(255, 100, 100)
		larg_c *= 1.5
	elif _flag(FLAG_ADRENALINA):
		var pulso := 0.5 + 0.5 * sin(t_jogo * 6.6)
		cor_c = Color8(int(120 + 135 * pulso), 40, 40)
		larg_c *= 1.3
	cor_c.a *= alfa
	if larg_c > 0.0:
		draw_arc(Vector2.ZERO, R - larg_c * 0.5, 0, TAU, 72, cor_c, larg_c, true)
	draw_set_transform(Vector2.ZERO)

	if estilo.mostrar_status and not morto:
		_desenhar_status(centro, R, t_jogo, estilo)


func _desenhar_status(centro: Vector2, R: float, t_jogo: float, estilo: EstiloPalco) -> void:
	var ang := deg_to_rad(float(_s.get("ang", 0.0)))
	# escudo dos buffs: bolha
	var escudo := float(_s.get("escudo", 0.0))
	if escudo > 0.0:
		draw_circle(centro, R * 1.22, Color(0.55, 0.9, 1.0, 0.10 + 0.12 * escudo), true, -1.0, true)
		draw_arc(centro, R * 1.22, 0, TAU, 72, Color(0.7, 0.95, 1.0, 0.45 + 0.4 * escudo), maxf(3.0, estilo.contorno_px * 0.8), true)
	# super armor: anel dourado
	if _flag(FLAG_SUPER_ARMOR):
		draw_arc(centro, R * 1.1, 0, TAU, 72, Color8(255, 200, 60, 220), maxf(4.0, estilo.contorno_px * 1.2), true)
	# bloqueando: escudo em arco na frente
	if _flag(FLAG_BLOQUEANDO):
		draw_arc(centro, R * 1.28, ang - 0.9, ang + 0.9, 24, Color8(170, 220, 255, 230), maxf(6.0, R * 0.12), true)
	# status dominante (maior prioridade): anel ou particulas na cor dele
	var dominante: Dictionary = {}
	for st in _status:
		if dominante.is_empty() or int(st.get("prioridade", 0)) > int(dominante.get("prioridade", 0)):
			dominante = st
	if not dominante.is_empty():
		var cor_st := UtilPalco.cor(dominante.get("cor", 0xFFFFFF), 0.85)
		if str(dominante.get("estilo", "")) == "particula":
			for k in 6:
				var a := t_jogo * 2.2 + k * TAU / 6.0
				draw_circle(centro + Vector2(cos(a), sin(a)) * R * 1.12, R * 0.07, cor_st, true, -1.0, true)
		else:
			draw_arc(centro, R * 1.08, 0, TAU, 72, cor_st, maxf(3.0, estilo.contorno_px * 0.9), true)
	# atordoado: estrelas girando sobre a cabeca
	if _flag(FLAG_ATORDOADO):
		for k in 3:
			var a := t_jogo * 4.0 + k * TAU / 3.0
			_estrela(centro + Vector2(cos(a) * R * 0.75, -R * 1.25 + sin(a) * R * 0.22), R * 0.16, Color8(255, 230, 90))
	# dormindo
	if _flag(FLAG_DORMINDO):
		var fonte := ThemeDB.fallback_font
		for k in 2:
			var sobe := fmod(t_jogo * 0.8 + k * 0.5, 1.0)
			draw_string(fonte, centro + Vector2(R * 0.6 + k * R * 0.3, -R * (1.0 + sobe)), "z", HORIZONTAL_ALIGNMENT_LEFT, -1, int(R * 0.5), Color(1, 1, 1, 1.0 - sobe))


func _estrela(c: Vector2, r: float, cor: Color) -> void:
	var pts := PackedVector2Array()
	for k in 8:
		var a := k * PI / 4.0
		pts.append(c + Vector2(cos(a), sin(a)) * (r if k % 2 == 0 else r * 0.4))
	draw_colored_polygon(pts, cor)
