extends Node2D
## O PALCO (Onda 16D): le um trabalho (job) e a timeline, monta o plano de
## quadros e desenha UM quadro do video por _process. O tempo vem SO do
## contador de quadros; o palco nunca decide nada da luta.
##
## Linha de comando (o Python monta tudo isto; ver docs/palco/README.md):
##   godot --path palco --fixed-fps 30 --write-movie X.avi -- --job=J.json
##   godot --path palco -- --timeline=T.json          (previa em tempo real)
## Sem argumento nenhum (F5 no editor) toca exemplos/exemplo.timeline.json.
##
## Codigos de saida: 0 ok; 2 job/timeline ilegivel ou invalida; 3 delta do 1o
## quadro != 1/30 (faltou --fixed-fps 30); 4 quadro sem desenho (janela
## MINIMIZADA: o Movie Maker grava quadro vazio COM som e sai 0 sem esta
## guarda). O ultimo quadro gravado e o do quit(): saimos NO ultimo quadro.

const FPS := 30
const RC_JOB := 2
const RC_DELTA := 3
const RC_SEM_DESENHO := 4
const EXEMPLO := "res://exemplos/exemplo.timeline.json"
const ESTILO := "res://biblioteca/estilo.tres"
const GATILHOS_ANIMACAO := preload("res://nucleo/gatilhos_animacao.gd")
const PX := UtilPalco.PX_POR_M
# Eventos que viram efeito na tela (a lista mora em Timeline). Os outros
# (tell, plano, virada, combo, texto...) sao da edicao/HUD; as pecas recebem
# todos em evento().
const EVENTOS_COM_VFX := Timeline.EVENTOS_COM_VFX
const TREMOR_TIER := {"light": 0.10, "medium": 0.2, "heavy": 0.38, "colossal": 0.6}
# Marcas da animacao "golpe" de uma arma, por fase (1..5). Portugues ou ingles.
const MARCAS := {
	1: ["preparo", "anticipation"], 2: ["golpe", "attack"], 3: ["impacto", "impact"],
	4: ["seguimento", "follow"], 5: ["recuperacao", "recovery"],
}

@onready var mundo: Node2D = $Mundo
@onready var camada_arena: Node2D = $Mundo/Arena
@onready var camada_solo: Node2D = $Mundo/Solo
@onready var camada_lutadores: Node2D = $Mundo/Lutadores
@onready var camada_armas: Node2D = $Mundo/Armas
@onready var camada_objetos: Node2D = $Mundo/Objetos
@onready var camada_efeitos: Node2D = $Mundo/Efeitos
@onready var camada_rotulos: CanvasLayer = $Rotulos
@onready var camada_tela: CanvasLayer = $Tela
@onready var mesa: MesaDeSom = $MesaDeSom

var job: Dictionary = {}
var tl: Timeline
var plano: PlanoQuadros
var bib := Biblioteca.new()
var estilo: EstiloPalco
var quadro := -1
var total := 0
var movie := false
var tela := Vector2(1080, 1920)
var relatorio_em := ""
var sons_por_quadro := {}
var eventos_por_quadro := {}
var lut := {}
var arm := {}
var arm_sec := {}          # segunda lamina da arma Dupla, espelhada na outra mao
var cab := {}
var rotulo := {}
# Quadro a partir do qual os nomes sobre os lutadores somem (job
# `nomes_ate_quadro`; -1 = nunca). O duelo de producao esconde os nomes
# quando o veredito da edicao entra: o nome grande do vencedor ficava por
# cima da placa do palco (conferencia de 07/10/2026).
var nomes_ate := -1
var rastro := {}
var orbital_px := {}      # slot -> alcance real da hitbox do Orbital, em px
var obj_nos := {}
var atelie_efeitos := {}
var vfx: Array = []
## folha de efeito em loop (ou que nunca acaba) some depois disto
const VFX_FOLHA_MAX_S := 3.0
# As pecas ficam SEM tipo de proposito: os metodos (configurar, atualizar,
# evento) sao do script de cada peca, e peca sem script tambem vale.
var arena_no = null
var hud_no = null
var barras: Array[ColorRect] = []
var clarao: ColorRect
var trauma := 0.0
var tj_ant := 0.0
var avisos := PackedStringArray()
var t0_ms := 0
var n_sons := 0
var sons_no_corte := 0
var n_eventos := 0
var eventos_no_corte := 0
var vfx_criados := 0
var _marcas_cache := {}
## Rosto do Atelie que mostrou OUTRA carinha no lugar da pedida (a pedida nao
## esta desenhada): "<parte>/<nivel>/<alvo>/<vNN>" -> {pedida: usada}. O
## lutador_padrao anota; vai para o relatorio, para dizer o que falta desenhar.
var rosto_herdado := {}


func _ready() -> void:
	t0_ms = Time.get_ticks_msec()
	movie = _modo_movie()
	tela = Vector2(get_viewport().get_visible_rect().size)
	var args := _ler_args()
	if not _preparar(args):
		_sair(RC_JOB)
		return
	if not movie:
		Engine.max_fps = FPS
	if args.has("minimizar"):
		# SO para o teste da guarda rc 4: minimizada, a janela nao desenha
		get_window().mode = Window.MODE_MINIMIZED
	print("[palco] %s | %s | tela %s | %d quadros (%.2f s) | %d sons, %d eventos" % [
		RenderingServer.get_video_adapter_name(), RenderingServer.get_current_rendering_driver_name(),
		tela, total, total / float(FPS), n_sons, n_eventos])


## O Movie Maker liga a feature "movie" (medido na 4.7.2: nao existe
## Engine.is_movie_maker_enabled, e OS.get_cmdline_args() NAO traz o
## --write-movie). Errar isto aqui deixou um render de 2 s gravando por 10 min
## em loop de previa (1,1 GB de AVI): por isso job tambem encerra (ver _process).
static func _modo_movie() -> bool:
	return OS.has_feature("movie")


func _ler_args() -> Dictionary:
	var args := {}
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and "=" in a:
			args[a.substr(2, a.find("=") - 2)] = a.substr(a.find("=") + 1)
	return args


# ------------------------------------------------------------------ preparo
func _preparar(args: Dictionary) -> bool:
	if args.has("job"):
		var texto := FileAccess.get_file_as_string(args["job"])
		var dados = JSON.parse_string(texto) if not texto.is_empty() else null
		if typeof(dados) != TYPE_DICTIONARY:
			avisos.append("job ilegivel: %s" % args["job"])
			return false
		job = dados
	relatorio_em = str(args.get("relatorio", job.get("relatorio", "")))
	nomes_ate = int(job.get("nomes_ate_quadro", -1))
	var carregado = load(ESTILO) if ResourceLoader.exists(ESTILO) else null
	estilo = (carregado as EstiloPalco).duplicate() if carregado is EstiloPalco else EstiloPalco.new()
	for campo in estilo.sobrepor(job.get("estilo", {})):
		avisos.append("estilo: campo desconhecido '%s' (ignorado)" % campo)
	var caminho := str(args.get("timeline", job.get("timeline", EXEMPLO)))
	tl = Timeline.carregar(caminho)
	if tl == null:
		avisos.append(Timeline.ultimo_erro)
		return false
	var problemas := tl.validar()
	if not problemas.is_empty():
		for p in problemas:
			avisos.append("timeline: " + p)
		return false
	var remap = job.get("remapeamento", tl.dados.get("remapeamento"))
	plano = PlanoQuadros.montar(tl.duracao(), remap, FPS)
	var paradas := []
	for ev in tl.dados.get("eventos", []):
		if ev.get("tipo") == "acerto":
			var s := estilo.hitstop_do_acerto(ev)
			if s > 0.0:
				paradas.append([float(ev["i"]) / tl.hz, s])
	if not paradas.is_empty():
		plano.com_hitstop(paradas)
	total = plano.total()
	var limite := int(args.get("quadros", job.get("quadros", 0)))
	if limite > 0:
		total = mini(total, limite)
	if total <= 0:
		avisos.append("o plano tem 0 quadros")
		return false
	for ev in tl.dados.get("eventos", []):
		var f := plano.mapear(float(ev["i"]) / tl.hz)
		if f < 0:
			eventos_no_corte += 1
			continue
		if not eventos_por_quadro.has(f):
			eventos_por_quadro[f] = []
		eventos_por_quadro[f].append(ev)
		n_eventos += 1
	var sons: Array = []
	if typeof(job.get("sons")) == TYPE_ARRAY:
		sons = job["sons"]
	elif typeof(tl.dados.get("sons")) == TYPE_DICTIONARY:
		sons = tl.dados["sons"].get("itens", [])
	for s in sons:
		var f := plano.mapear(float(s.get("t", 0.0)))
		if f < 0:
			sons_no_corte += 1
			continue
		if not sons_por_quadro.has(f):
			sons_por_quadro[f] = []
		sons_por_quadro[f].append(s)
		n_sons += 1
	mesa.preparar(estilo, bib, job.get("sons_arquivos", {}))
	var arena: Dictionary = tl.dados.get("arena", {}) if typeof(tl.dados.get("arena")) == TYPE_DICTIONARY else {}
	# fora da arena: a cor do estilo (a `cor_ambiente` do jogo e marrom e
	# brigava com o quadro de hoje, que e azul-escuro)
	RenderingServer.set_default_clear_color(estilo.cor_fundo)
	_montar_cena(arena)
	return true


func _instanciar(cena: PackedScene, pai: Node) -> Node:
	var no := cena.instantiate()
	pai.add_child(no)
	return no


func _ctx_base() -> Dictionary:
	return {"estilo": estilo, "quadro": maxi(quadro, 0), "fps": FPS, "t_jogo": tj_ant, "dt_mundo": 0.0,
		"zoom": 1.0, "px_por_m": PX, "palco": self, "timeline": tl, "corte": false, "tela": tela, "passo": 0.0}


func _montar_cena(arena: Dictionary) -> void:
	var ctx := _ctx_base()
	if not arena.is_empty():
		arena_no = _instanciar(bib.arena(str(arena.get("nome", "")), str(arena.get("tema", ""))), camada_arena)
		if arena_no.has_method("configurar"):
			arena_no.configurar(arena, ctx)
	for slot in ["p1", "p2"]:
		var c := tl.cabecalho_lutador(slot)
		cab[slot] = c
		var no = _instanciar(bib.lutador(str(c.get("nome", "")), str(c.get("classe", ""))), camada_lutadores)
		if no.has_method("configurar"):
			no.configurar(c, ctx)
		lut[slot] = no
		var arma = c.get("arma")
		if typeof(arma) == TYPE_DICTIONARY:
			var dados_arma: Dictionary = arma.duplicate()
			dados_arma["raio_corpo"] = c.get("raio_corpo", 0.85)
			dados_arma["slot"] = slot
			if UtilPalco.slug(str(arma.get("tipo", ""))) == "orbital":
				var alcance = arma.get("alcance_m")
				orbital_px[slot] = (float(alcance) if alcance != null else 1.5 * float(c.get("raio_corpo", 0.85))) * PX
			var na = _instanciar(bib.arma(str(arma.get("tipo", "")), str(arma.get("estilo", ""))), camada_armas)
			if na.has_method("configurar"):
				na.configurar(dados_arma, ctx)
			var anim := na.get_node_or_null("Anim") as AnimationPlayer
			if anim != null:
				anim.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
			arm[slot] = na
			if UtilPalco.slug(str(arma.get("tipo", ""))) == "dupla":
				var segunda = _instanciar(bib.arma(str(arma.get("tipo", "")), str(arma.get("estilo", ""))), camada_armas)
				if segunda.has_method("configurar"):
					segunda.configurar(dados_arma, ctx)
				var anim_segunda := segunda.get_node_or_null("Anim") as AnimationPlayer
				if anim_segunda != null:
					anim_segunda.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
				arm_sec[slot] = segunda
		if estilo.mostrar_nomes:
			var lb := Label.new()
			lb.text = str(c.get("rotulo", c.get("nome", slot)))
			lb.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			lb.size = Vector2(tela.x * 0.8, estilo.nome_px * 1.5)
			lb.add_theme_font_size_override("font_size", int(estilo.nome_px * tela.y / 1920.0))
			lb.add_theme_color_override("font_color", UtilPalco.cor(c.get("cor_nome", c.get("cor_lado", 0xFFFFFF))).lightened(0.25))
			lb.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
			lb.add_theme_constant_override("outline_size", int(estilo.nome_px * 0.28))
			camada_rotulos.add_child(lb)
			rotulo[slot] = lb
	if bool(job.get("hud", false)):
		hud_no = _instanciar(bib.hud(), camada_tela)
		if hud_no.has_method("configurar"):
			hud_no.configurar({"lutadores": [cab["p1"], cab["p2"]]}, ctx)
	for k in 2:
		var barra := ColorRect.new()
		barra.color = Color.BLACK
		barra.size = Vector2(tela.x, 0)
		barra.position = Vector2(0, 0 if k == 0 else tela.y)
		camada_tela.add_child(barra)
		barras.append(barra)
	clarao = ColorRect.new()
	clarao.color = Color(1, 1, 1, 0)
	clarao.size = tela
	clarao.mouse_filter = Control.MOUSE_FILTER_IGNORE
	camada_tela.add_child(clarao)


# ------------------------------------------------------------------ laco
func _process(delta: float) -> void:
	quadro += 1
	if movie:
		if quadro == 0 and absf(delta - 1.0 / FPS) > 1e-5:
			avisos.append("delta do 1o quadro = %.6f, esperado 1/%d: falta --fixed-fps %d" % [delta, FPS, FPS])
			printerr("[palco] ERRO: " + avisos[-1])
			_sair(RC_DELTA)
			return
		if quadro >= 1 and Engine.get_frames_drawn() < quadro:
			avisos.append("quadro %d sem desenho (frames_drawn=%d): janela minimizada?" % [quadro, Engine.get_frames_drawn()])
			printerr("[palco] ERRO: " + avisos[-1])
			_sair(RC_SEM_DESENHO)
			return
	elif quadro >= total and (job.is_empty() or bool(job.get("preview", false))):
		# Previa do editor ou do simulador manual: recomeca do inicio.
		quadro = 0
		_limpar_transitorios()
	if quadro >= total:
		return
	_desenhar_quadro(quadro)
	# Com job (o Python chamou), o ultimo quadro SEMPRE encerra, com ou sem
	# Movie Maker: um render nunca pode ficar rodando em loop.
	if (movie or (not job.is_empty() and not bool(job.get("preview", false)))) and quadro >= total - 1:
		_escrever_relatorio(true, 0)
		get_tree().quit(0)


func _limpar_transitorios() -> void:
	for v in vfx:
		if is_instance_valid(v):
			v.queue_free()
	vfx.clear()
	for slot in rastro:
		rastro[slot].clear_points()
	trauma = 0.0


func _desenhar_quadro(f: int) -> void:
	var t := plano.t_src[f]
	var p := tl.passo_de(t)
	var i := clampi(int(floor(p)), 0, tl.n - 1)
	var corte := plano.inicio_de_trecho(f)
	var g := tl.global(p)
	var tj := float(g.get("tj", 0.0))
	var dt_mundo := 0.0 if corte else maxf(0.0, tj - tj_ant)
	tj_ant = tj
	if corte and f > 0:
		_limpar_transitorios()
	var cam := tl.camera(p)
	var zoom := tela.x / maxf(50.0, float(cam.get("lv", 10.0)) * PX)
	var ctx := {"estilo": estilo, "quadro": f, "fps": FPS, "t_jogo": tj, "dt_mundo": dt_mundo,
		"zoom": zoom, "px_por_m": PX, "palco": self, "timeline": tl, "corte": corte, "tela": tela,
		"passo": p}

	var efeitos_lutador := {"p1": [], "p2": []}
	for e in tl.vivas("efeitos", i):
		if efeitos_lutador.has(e.get("alvo")):
			var efeito: Dictionary = e.duplicate(true)
			efeito.merge(tl.amostra_trilha(e, p), true)
			efeitos_lutador[e["alvo"]].append(efeito)
	var amostras := {}
	for slot in ["p1", "p2"]:
		var s := tl.lutador(slot, p)
		s["_efeitos"] = efeitos_lutador[slot]
		amostras[slot] = s
		var no = lut[slot]
		no.position = Vector2(float(s["x"]), float(s["y"])) * PX
		if no.has_method("atualizar"):
			no.atualizar(s, ctx)
		# Canais da amostra tambem sao gatilhos do catalogo (expressao e fase
		# do golpe). O tocador ignora os que a peca nao declarou.
		if no.has_method("gatilho"):
			if str(s.get("expr", "")) != "":
				no.gatilho("expr")
			elif int(s.get("golpe_fase", 0)) > 0:
				no.gatilho("golpe_fase")
		if no.has_method("ajustar_corpo"):
			no.ajustar_corpo(2.0 * float(cab[slot].get("raio_corpo", 0.85)) * PX)
		if no.has_method("avancar"):
			no.avancar(dt_mundo)
		else:
			no.scale = Vector2.ONE * float(cab[slot].get("raio_corpo", 0.85)) * PX / maxf(1.0, float(no.get("raio_ref") if no.get("raio_ref") != null else 100.0))
		_arma(slot, s, p, corte, ctx)
	_objetos(p, i, ctx)
	_atelie_efeitos(i, p, amostras, ctx)
	for ev in eventos_por_quadro.get(f, []):
		_evento(ev, amostras, ctx)
	_envelhecer_vfx(ctx)
	for s in sons_por_quadro.get(f, []):
		mesa.tocar(s, f)

	# camera: centro e largura visivel da timeline + tremor do palco
	trauma = maxf(0.0, trauma - 2.2 / FPS)
	var tremor := Vector2.ZERO
	if trauma > 0.0 and estilo.tremor > 0.0:
		tremor = Vector2(sin(f * 1.7 + 0.3) + sin(f * 3.1), cos(f * 2.3) + sin(f * 1.1 + 1.0)) * 0.5 \
			* trauma * trauma * estilo.tremor_max_px * estilo.tremor
	var centro := Vector2(float(cam.get("x", 0.0)) + float(cam.get("ox", 0.0)), float(cam.get("y", 0.0)) + float(cam.get("oy", 0.0))) * PX
	mundo.scale = Vector2.ONE * zoom
	mundo.position = tela / 2.0 - centro * zoom + tremor

	for slot in rotulo:
		var s: Dictionary = amostras[slot]
		var morto := (int(s.get("flags", 0)) & 2) != 0
		var oculto := (int(s.get("flags", 0)) & (1 << 16)) != 0
		var lb: Label = rotulo[slot]
		lb.visible = not oculto and (nomes_ate < 0 or quadro < nomes_ate)
		var topo := Vector2(float(s["x"]), float(s["y"]) - (0.0 if morto else float(s.get("z", 0.0))) - float(cab[slot].get("raio_corpo", 0.85)) * 1.18) * PX
		var na_tela := mundo.transform * topo
		# O nome nunca sai da tela: o texto (e nao a caixa, que e larga) e
		# empurrado para dentro com uma margem. No A/B de 28/09 o nome de quem
		# lutava junto a parede saia cortado.
		var fonte := lb.get_theme_font("font")
		var tam := lb.get_theme_font_size("font_size")
		var largura_texto := fonte.get_string_size(lb.text, HORIZONTAL_ALIGNMENT_LEFT, -1, tam).x if fonte else 0.0
		var margem := tela.x * 0.03
		var meio := clampf(na_tela.x, margem + largura_texto / 2.0, tela.x - margem - largura_texto / 2.0)
		lb.position = Vector2(meio - lb.size.x / 2.0, maxf(margem, na_tela.y - lb.size.y))
	if hud_no != null and hud_no.has_method("atualizar"):
		hud_no.atualizar(amostras, ctx)
	var alto := tela.y * 0.085 if estilo.letterbox and float(g.get("letterbox", 0.0)) > 0.0 else 0.0
	barras[0].size = Vector2(tela.x, alto)
	barras[1].size = Vector2(tela.x, alto)
	barras[1].position = Vector2(0, tela.y - alto)
	clarao.color.a = clarao.color.a * 0.72


func _arma(slot: String, s: Dictionary, p: float, corte: bool, ctx: Dictionary) -> void:
	var no = arm.get(slot)
	if no == null:
		return
	var flags := int(s.get("flags", 0))
	var morto := (flags & 2) != 0
	no.visible = (flags & (1 << 16)) == 0
	var z := 0.0 if morto else float(s.get("z", 0.0))
	var grip := Vector2(float(s["arma_gx"]), float(s["arma_gy"]) - z) * PX
	var ponta := Vector2(float(s["arma_px"]), float(s["arma_py"]) - z) * PX
	var L := grip.distance_to(ponta)
	if orbital_px.has(slot) and not morto:
		# Orbital: a timeline grava a peca a 1x o raio (como o render de hoje),
		# mas a hitbox e um setor de 1,5x. O palco desenha no alcance REAL
		# (decisao de 28/09: "o que acerta e o que aparece").
		var direcao := (ponta - grip).normalized() if L > 0.5 else Vector2.from_angle(deg_to_rad(float(s.get("arma_ang", 0.0))))
		ponta = grip + direcao * float(orbital_px[slot])
		L = float(orbital_px[slot])
	no.position = grip
	no.rotation = (ponta - grip).angle() if L > 0.5 else deg_to_rad(float(s.get("arma_ang", 0.0)))
	s["_comprimento_px"] = L
	# Antes a escala so valia para a peca SEM `atualizar`: a cena com o
	# peca.gd (que tem atualizar vazio) ficava no tamanho desenhado (16F).
	UtilPalco.esticar_arma(no, L)
	if no.has_method("atualizar"):
		no.atualizar(s, ctx)
	if no.has_method("gatilho"):
		no.gatilho("golpe_fase" if int(s.get("golpe_fase", 0)) > 0 else "ocioso")
	if no.has_method("ajustar_corpo"):
		no.ajustar_corpo(2.0 * float(cab[slot].get("raio_corpo", 0.85)) * PX)
	if no.has_method("avancar"):
		no.avancar(float(ctx.get("dt_mundo", 0.0)))
		_seek_golpe(no, int(s.get("golpe_fase", 0)), float(s.get("golpe_p", 0.0)), float(ctx["t_jogo"]))
	_arma_segunda(slot, s, z, ctx, grip, ponta)


## A segunda lamina da Dupla e a imagem central da primeira no corpo: a
## empunhadura cai na outra mao e a ponta aponta para o lado oposto. Espelhar
## Y quando ela aponta para a esquerda conserva o lado de cima da arte.
func _arma_segunda(slot: String, s: Dictionary, z: float, ctx: Dictionary,
		grip: Vector2, ponta: Vector2) -> void:
	var no = arm_sec.get(slot)
	if no == null:
		return
	no.visible = (int(s.get("flags", 0)) & (1 << 16)) == 0
	var centro := Vector2(float(s["x"]), float(s["y"]) - z) * PX
	var grip_espelhada := centro * 2.0 - grip
	var ponta_espelhada := grip_espelhada - (ponta - grip)
	var L := grip_espelhada.distance_to(ponta_espelhada)
	no.position = grip_espelhada
	no.rotation = (ponta_espelhada - grip_espelhada).angle() if L > 0.5 else PI
	s["_comprimento_px"] = L
	UtilPalco.esticar_arma(no, L)
	if cos(no.rotation) < 0.0:
		no.scale.y = -absf(no.scale.y)
	else:
		no.scale.y = absf(no.scale.y)
	if no.has_method("atualizar"):
		no.atualizar(s, ctx)
		_seek_golpe(no, int(s.get("golpe_fase", 0)), float(s.get("golpe_p", 0.0)), float(ctx["t_jogo"]))


## A animacao "golpe" da peca vai para o PROGRESSO DA FASE do motor
## (golpe_fase + golpe_p): qualquer animacao cabe em qualquer duracao. As
## fases sao marcas na animacao (preparo, golpe, impacto, seguimento,
## recuperacao); sem marcas, a animacao e dividida em 5 partes iguais. Sem
## golpe, toca "parado" se existir (em loop pelo tempo de jogo).
func _seek_golpe(no: Node, fase: int, prog: float, t_jogo: float) -> void:
	var anim := no.get_node_or_null("Anim") as AnimationPlayer
	if anim == null:
		return
	if fase <= 0:
		if anim.has_animation("parado"):
			if anim.current_animation != "parado":
				anim.play("parado")
			var comp := maxf(0.001, anim.get_animation("parado").length)
			anim.seek(fmod(t_jogo, comp), true)
		elif anim.has_animation("golpe"):
			if anim.current_animation != "golpe":
				anim.play("golpe")
			anim.seek(0.0, true)
		return
	if not anim.has_animation("golpe"):
		return
	if anim.current_animation != "golpe":
		anim.play("golpe")
	var a := anim.get_animation("golpe")
	var marcas := _marcas(a)
	var ini: float = marcas[clampi(fase, 1, 5) - 1]
	var fim: float = marcas[clampi(fase, 1, 5)]
	anim.seek(ini + clampf(prog, 0.0, 1.0) * (fim - ini), true)


func _marcas(a: Animation) -> Array:
	if _marcas_cache.has(a):
		return _marcas_cache[a]
	var tempos := []
	for fase in range(1, 6):
		var t := -1.0
		for nome in MARCAS[fase]:
			if a.has_marker(nome):
				t = a.get_marker_time(nome)
				break
		tempos.append(t if t >= 0.0 else a.length * (fase - 1) / 5.0)
	tempos.append(a.length)
	_marcas_cache[a] = tempos
	return tempos


func _objetos(p: float, i: int, ctx: Dictionary) -> void:
	var vivos := {}
	for t in tl.vivas("objetos", i):
		var id := int(t.get("id", -1))
		vivos[id] = true
		var no = obj_nos.get(id)
		if no == null:
			var tipo := str(t.get("tipo", ""))
			var pai := camada_solo if tipo in ["area", "trap", "portal"] else camada_objetos
			no = _instanciar(bib.objeto(tipo, str(t.get("elemento", "")), str(t.get("nome", "")), str(t.get("forma", ""))), pai)
			if no.has_method("configurar"):
				no.configurar(t, ctx)
			obj_nos[id] = no
		var a := tl.amostra_trilha(t, p)
		if a.has("x"):
			no.position = Vector2(float(a["x"]), float(a["y"])) * PX
		if no.has_method("gatilho"):
			no.gatilho(str(t.get("tipo", "")))
		if no.has_method("ajustar_corpo"):
			var dono := str(t.get("dono", ""))
			no.ajustar_corpo(2.0 * float(cab.get(dono, {}).get("raio_corpo", 0.85)) * PX)
		if no.has_method("avancar"):
			no.avancar(float(ctx.get("dt_mundo", 0.0)))
		elif no.has_method("atualizar"):
			no.atualizar(a, ctx)
		else:
			no.rotation = deg_to_rad(float(a.get("ang", 0.0)))
			if a.has("r"):
				var ref = no.get("raio_ref")
				no.scale = Vector2.ONE * float(a["r"]) * PX / maxf(1.0, float(ref) if ref != null else 100.0)
	for id in obj_nos.keys():
		if not vivos.has(id):
			obj_nos[id].queue_free()
			obj_nos.erase(id)


## Status e buffs sao trilhas, nao eventos isolados. Cada folha fica presa ao
## lutador enquanto a trilha esta viva e desaparece junto com ela.
func _atelie_efeitos(i: int, p: float, amostras: Dictionary, ctx: Dictionary) -> void:
	var vivos := {}
	for efeito in tl.vivas("efeitos", i):
		var tipo := str(efeito.get("tipo", ""))
		if tipo not in ["status", "buff"]:
			continue
		var nome := str(efeito.get("status", efeito.get("nome", "")))
		var slot := str(efeito.get("alvo", ""))
		if nome == "" or not amostras.has(slot):
			continue
		var chave := "%s:%s" % [tipo, str(efeito.get("id", ""))]
		vivos[chave] = true
		var no = atelie_efeitos.get(chave)
		if no == null:
			var cena := bib.efeito_lutador(tipo, nome)
			if cena == null:
				continue
			no = _instanciar(cena, camada_efeitos)
			atelie_efeitos[chave] = no
		var s: Dictionary = amostras[slot]
		no.position = Vector2(float(s["x"]), float(s["y"]) - float(s.get("z", 0.0))) * PX
		if no.has_method("gatilho"):
			no.gatilho(tipo)
		if no.has_method("ajustar_corpo"):
			no.ajustar_corpo(2.0 * float(cab[slot].get("raio_corpo", 0.85)) * PX)
		if no.has_method("avancar"):
			no.avancar(float(ctx.get("dt_mundo", 0.0)))
	# Flags tambem sao estados ativos do personagem (nao viram trilha de
	# efeito). A tabela da propria timeline define qual bit cada nome ocupa.
	var flags: Array = tl.dados.get("tabelas", {}).get("flags", [])
	for slot in amostras:
		var ativos := int(amostras[slot].get("flags", 0))
		for bit in flags.size():
			if (ativos & (1 << bit)) == 0:
				continue
			var nome_flag := str(flags[bit])
			var chave_flag := "estado_lutador:%s:%s" % [slot, nome_flag]
			vivos[chave_flag] = true
			var no_flag = atelie_efeitos.get(chave_flag)
			if no_flag == null:
				var cena_flag := bib.estado_lutador(nome_flag)
				if cena_flag == null:
					continue
				no_flag = _instanciar(cena_flag, camada_efeitos)
				atelie_efeitos[chave_flag] = no_flag
			var amostra: Dictionary = amostras[slot]
			no_flag.position = Vector2(float(amostra["x"]), float(amostra["y"]) - float(amostra.get("z", 0.0))) * PX
			if no_flag.has_method("gatilho"):
				no_flag.gatilho(nome_flag)
			if no_flag.has_method("ajustar_corpo"):
				no_flag.ajustar_corpo(2.0 * float(cab[slot].get("raio_corpo", 0.85)) * PX)
			if no_flag.has_method("avancar"):
				no_flag.avancar(float(ctx.get("dt_mundo", 0.0)))
	for chave in atelie_efeitos.keys():
		if not vivos.has(chave):
			atelie_efeitos[chave].queue_free()
			atelie_efeitos.erase(chave)


func _evento(ev: Dictionary, amostras: Dictionary, ctx: Dictionary) -> void:
	var tipo := str(ev.get("tipo", ""))
	if tipo == "obstaculo" and arena_no != null and arena_no.has_method("evento"):
		arena_no.evento(tipo, ev, ctx)
	for chave in ["slot", "alvo", "autor", "iniciador"]:
		var slot = ev.get(chave)
		if lut.has(slot) and lut[slot].has_method("evento"):
			lut[slot].evento(tipo, ev, ctx)
	var gatilho := GATILHOS_ANIMACAO.da_timeline(ev)
	for slot in lut:
		if lut[slot].has_method("gatilho"):
			lut[slot].gatilho(gatilho)
	for slot in arm:
		if arm[slot].has_method("gatilho"):
			arm[slot].gatilho(gatilho)
	var nome_skill := str(ev.get("nome", ""))
	var tipo_skill := str(ev.get("tipo_skill", ""))
	if not EVENTOS_COM_VFX.has(tipo) and not bib.tem_folha_evento(tipo, str(ev.get("elemento", "")), nome_skill, tipo_skill):
		return
	var pos := Vector2.ZERO
	if tipo == "acerto" and typeof(ev.get("ponto")) == TYPE_ARRAY:
		# revisao 3: o acerto por projetil traz o PONTO do impacto (onde o
		# projetil estava), como o flash do render
		pos = Vector2(float(ev["ponto"][0]), float(ev["ponto"][1])) * PX
	elif tipo == "acerto":
		# no ponto do corpo do alvo que encara o autor
		var dir := deg_to_rad(float(ev.get("dir", 0.0)))
		var raio := float(cab.get(str(ev.get("alvo")), {}).get("raio_corpo", 0.85))
		pos = (Vector2(float(ev.get("x", 0.0)), float(ev.get("y", 0.0)) - float(ev.get("z", 0.0))) - Vector2(cos(dir), sin(dir)) * raio * 0.8) * PX
	elif ev.has("x") and ev.has("y"):
		pos = Vector2(float(ev["x"]), float(ev["y"]) - float(ev.get("z", 0.0))) * PX
	elif tipo == "obstaculo":
		var obst: Array = tl.dados.get("arena", {}).get("obstaculos", [])
		var k := int(ev.get("indice", -1))
		if k >= 0 and k < obst.size():
			pos = Vector2(float(obst[k].get("x", 0)), float(obst[k].get("y", 0))) * PX
	else:
		var slot = ev.get("slot", ev.get("alvo", ev.get("iniciador")))
		if amostras.has(slot):
			var s: Dictionary = amostras[slot]
			pos = Vector2(float(s["x"]), float(s["y"]) - float(s.get("z", 0.0))) * PX
	# O KO vai para o CHAO (abaixo dos lutadores): no A/B de 28/09 a explosao
	# por cima cobria o corpo caido, que e o que o desfecho tem de mostrar.
	var camada := camada_solo if tipo == "ko" else camada_efeitos
	var variante := ""
	if tipo == "movimento":
		variante = str(ev.get("gatilho", ""))
	elif tipo == "projetil_fim":
		variante = str(ev.get("motivo", ""))
	elif tipo == "agarrao_desfecho":
		variante = str(ev.get("modo", ""))
	elif tipo == "acerto":
		if bool(ev.get("critico", false)):
			variante = "critico"
		else:
			var arma: Dictionary = cab.get(str(ev.get("autor", "")), {}).get("arma", {})
			var tipo_arma := UtilPalco.slug(str(arma.get("tipo", "")))
			variante = "projetil_arma" if tipo_arma in ["arremesso", "arco"] else str(arma.get("arquetipo_animacao", ""))
	var no = _instanciar(bib.evento(tipo, str(ev.get("tier", "")), str(ev.get("elemento", "")), variante,
		nome_skill, tipo_skill), camada)
	no.position = pos
	if no.has_method("gatilho"):
		no.gatilho(gatilho)
		if no.get("segue_animacao") == "mao do lutador":
			var dono := str(ev.get("slot", ""))
			if amostras.has(dono):
				var s: Dictionary = amostras[dono]
				no.position = Vector2(float(s["arma_gx"]), float(s["arma_gy"]) - float(s.get("z", 0.0))) * PX
		if no.has_method("ajustar_corpo"):
			var raio := float(cab.get(str(ev.get("slot", "")), {}).get("raio_corpo", 0.85))
			no.ajustar_corpo(2.0 * raio * PX)
	if no.has_method("configurar"):
		no.configurar(ev, ctx)
	vfx.append(no)
	vfx_criados += 1
	match tipo:
		"acerto":
			trauma += float(TREMOR_TIER.get(str(ev.get("tier", "light")), 0.1))
		"wall_splat":
			trauma += 0.45
		"ko":
			trauma += 0.8
			clarao.color.a = 0.55
		"choque":
			# o render treme a camera no choque de projeteis (aplicar_shake 11)
			trauma += 0.35
	trauma = minf(trauma, 1.0)


func _envelhecer_vfx(ctx: Dictionary) -> void:
	var vivos: Array = []
	for v in vfx:
		if not is_instance_valid(v) or v.is_queued_for_deletion():
			continue
		if v.has_method("avancar"):
			# folha do Atelie (08/10/2026): toca os quadros e some quando a
			# animacao sem loop acaba (antes ficava parada no 1o quadro)
			v.avancar(float(ctx["dt_mundo"]))
			var vida := float(v.get_meta("idade", 0.0)) + float(ctx["dt_mundo"])
			v.set_meta("idade", vida)
			if (not bool(v.get("loop")) and bool(v.get("_terminou"))) or vida > VFX_FOLHA_MAX_S:
				v.queue_free()
				continue
		elif v.has_method("atualizar"):
			v.atualizar({}, ctx)
		else:
			# efeito sem script: toca a animacao "Anim" pela idade e some no fim
			var idade := float(v.get_meta("idade", 0.0)) + float(ctx["dt_mundo"])
			v.set_meta("idade", idade)
			var anim := v.get_node_or_null("Anim") as AnimationPlayer
			var comp := 0.5
			if anim != null and anim.get_animation_list().size() > 0:
				var nome: String = anim.get_animation_list()[0] if anim.current_animation == "" else anim.current_animation
				if anim.current_animation == "":
					anim.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
					anim.play(nome)
				comp = anim.get_animation(nome).length
				anim.seek(minf(idade, comp), true)
			if idade >= comp:
				v.queue_free()
				continue
		if is_instance_valid(v) and not v.is_queued_for_deletion():
			vivos.append(v)
	vfx = vivos


# ------------------------------------------------------------------ saida
func _sair(rc: int) -> void:
	_escrever_relatorio(false, rc)
	for a in avisos:
		printerr("[palco] ", a)
	get_tree().quit(rc)


func _escrever_relatorio(ok: bool, rc: int) -> void:
	if relatorio_em.is_empty():
		return
	var parados := 0
	if plano != null:
		for b in plano.parado:
			parados += b
	var d := {
		"ok": ok,
		"rc": rc,
		"quadros": total,
		"fps": FPS,
		"duracao": total / float(FPS),
		"movie": movie,
		"tela": [tela.x, tela.y],
		"timeline": tl.caminho if tl != null else str(job.get("timeline", "")),
		"plano": {"trechos": plano.trechos if plano != null else [], "quadros_de_hitstop": parados},
		"sons": mesa.relatorio().merged({"agendados": n_sons, "no_corte": sons_no_corte}) if mesa != null else {},
		"eventos": {"agendados": n_eventos, "no_corte": eventos_no_corte, "vfx": vfx_criados},
		"pecas": bib.escolhas,
		"reservas": bib.reservas.keys(),
		"nomes_ate_quadro": nomes_ate,
		"rosto_herdado": rosto_herdado,
		"pngs_ilegiveis": bib.pngs_ilegiveis.keys(),
		"avisos": avisos,
		"laco_ms": Time.get_ticks_msec() - t0_ms,
		"video": {"adaptador": RenderingServer.get_video_adapter_name(),
			"driver": RenderingServer.get_current_rendering_driver_name(),
			"metodo": RenderingServer.get_current_rendering_method()},
	}
	var f := FileAccess.open(relatorio_em, FileAccess.WRITE)
	if f == null:
		printerr("[palco] nao consegui escrever o relatorio em ", relatorio_em)
		return
	f.store_string(JSON.stringify(d, "  "))
	f.close()
