extends Node2D
## A VITRINE do palco (16E): um video de revisao com as pecas da biblioteca
## ANIMADAS, pagina por pagina, cada uma com o nome em cima. Mostra o que a
## biblioteca RESOLVE (as mesmas regras de nome do palco), entao uma peca nova
## aparece aqui sem mexer neste arquivo.
##
##   python main.py palco vitrine            (o Python grava e confere o mp4)
##   godot --path palco res://ferramentas/vitrine.tscn --fixed-fps 30 --write-movie X.avi -- --relatorio=R.json
##
## Paginas: os 24 rostos (visao geral e a 408 px), acertos e eventos, efeitos
## por tipo x elemento, o HUD sobre uma luta de mentira e as armas por tipo.
## Sem som (e revisao do desenho; o som e o do jogo, julgado no A/B).
## Mesmas guardas do palco: rc 3 sem --fixed-fps 30, rc 4 janela minimizada.

const FPS := 30
const RC_DELTA := 3
const RC_SEM_DESENHO := 4
const ESTILO := "res://biblioteca/estilo.tres"
const CORES_CORPO := [0xE0605E, 0x8F5AE5, 0x5DBB6F, 0x6B84E8, 0xFF7FB8, 0xF5A623]
const ELEMENTOS := ["FOGO", "GELO", "RAIO", "TREVAS", "LUZ", "NATUREZA", "ARCANO", "CAOS", "SANGUE", "VOID",
	"TEMPO", "GRAVITACAO"]
const PLANOS := ["PRESSÃO", "ISCA", "PRA PAREDE", "ESMAGAR", "TROCAÇÃO", "ACABAR"]
const TIPOS_ARMA := ["Reta", "Dupla", "Corrente", "Arremesso", "Arco", "Orbital", "Mágica", "Transformável"]
const EVENTOS := [
	["acerto", "light", "acerto leve"], ["acerto", "medium", "acerto médio"], ["acerto", "heavy", "acerto pesado"],
	["acerto", "colossal", "acerto colossal"], ["acerto_critico", "heavy", "crítico"], ["bloqueio", "", "bloqueio"],
	["parry", "", "parry"], ["esquiva", "", "esquiva"], ["dash", "", "dash"], ["parede", "", "parede"],
	["wall_splat", "", "wall splat"], ["obstaculo", "", "obstáculo"], ["skill", "", "skill (arcano)"],
	["escudo_quebrou", "", "escudo quebrou"], ["cura", "", "cura"], ["ko", "", "KO"],
]

var tela := Vector2(1080, 1920)
var estilo: EstiloPalco
var bib := Biblioteca.new()
var paginas: Array = []      # [[titulo, segundos, funcao de montar]]
var inicio_pag: Array = []   # quadro em que cada pagina comeca
var total := 0
var quadro := -1
var pagina := -1
var movie := false
var relatorio_em := ""
var avisos := PackedStringArray()
var t0_ms := 0

var cena: Node2D              # o que a pagina montou (apagado na troca)
var rotulos: Node2D           # nomes e titulo, por cima de tudo
var textos: Array = []        # [posicao, texto, tamanho, cor]
var titulo := ""
var titulo_embaixo := false   # a pagina do HUD usa o topo
var itens: Array = []         # [no, funcao(no, t, ctx)]
var _fonte: Font


func _ready() -> void:
	t0_ms = Time.get_ticks_msec()
	movie = OS.has_feature("movie")
	tela = Vector2(get_viewport().get_visible_rect().size)
	var args := {}
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and "=" in a:
			args[a.substr(2, a.find("=") - 2)] = a.substr(a.find("=") + 1)
	relatorio_em = str(args.get("relatorio", ""))
	var carregado = load(ESTILO) if ResourceLoader.exists(ESTILO) else null
	estilo = (carregado as EstiloPalco).duplicate() if carregado is EstiloPalco else EstiloPalco.new()
	RenderingServer.set_default_clear_color(estilo.cor_fundo)
	var negrito := FontVariation.new()
	negrito.base_font = ThemeDB.fallback_font
	negrito.variation_embolden = 0.9
	_fonte = negrito
	paginas = [
		["ROSTOS · as 24 expressões", 4.0, _pag_rostos_todos],
		["ROSTOS a 408 px (1/4)", 2.5, _pag_rostos_grandes.bind(0)],
		["ROSTOS a 408 px (2/4)", 2.5, _pag_rostos_grandes.bind(6)],
		["ROSTOS a 408 px (3/4)", 2.5, _pag_rostos_grandes.bind(12)],
		["ROSTOS a 408 px (4/4)", 2.5, _pag_rostos_grandes.bind(18)],
		["ACERTOS E EVENTOS", 5.0, _pag_eventos],
		["EFEITOS · tipo × elemento (1/2)", 5.0, _pag_efeitos.bind(0)],
		["EFEITOS · tipo × elemento (2/2)", 5.0, _pag_efeitos.bind(6)],
		["HUD · nome, vida e plano", 6.0, _pag_hud],
		["ARMAS · os 8 tipos", 4.0, _pag_armas],
	]
	# as folhas de sprite (formato da Oficina) aparecem sozinhas, 12 por pagina
	var folhas := _achar_folhas("res://biblioteca/efeitos/")
	for desde in range(0, folhas.size(), 12):
		paginas.append(["FOLHAS ANIMADAS (%d)" % folhas.size(), 5.0, _pag_folhas.bind(folhas.slice(desde, desde + 12))])
	var so := str(args.get("so", ""))
	if so != "":
		var escolhidas: Array = []
		for p in paginas:
			if str(p[0]).to_lower().contains(so.to_lower()):
				escolhidas.append(p)
		paginas = escolhidas
	for p in paginas:
		inicio_pag.append(total)
		total += int(round(float(p[1]) * FPS))
	if not movie:
		Engine.max_fps = FPS
	rotulos = Node2D.new()
	rotulos.z_index = 100
	add_child(rotulos)
	rotulos.draw.connect(_desenhar_rotulos)
	print("[vitrine] %d paginas, %d quadros (%.1f s)" % [paginas.size(), total, total / float(FPS)])


func _process(delta: float) -> void:
	quadro += 1
	if movie:
		if quadro == 0 and absf(delta - 1.0 / FPS) > 1e-5:
			avisos.append("delta do 1o quadro = %.6f: falta --fixed-fps %d" % [delta, FPS])
			_sair(RC_DELTA)
			return
		if quadro >= 1 and Engine.get_frames_drawn() < quadro:
			avisos.append("quadro %d sem desenho: janela minimizada?" % quadro)
			_sair(RC_SEM_DESENHO)
			return
	elif quadro >= total:
		quadro = 0
	if quadro >= total or total == 0:
		return
	var k := pagina
	while k + 1 < paginas.size() and quadro >= int(inicio_pag[k + 1]):
		k += 1
	if k != pagina:
		_trocar(k)
	var t: float = (quadro - int(inicio_pag[pagina])) / float(FPS)
	var ctx := {"estilo": estilo, "quadro": quadro, "fps": FPS, "t_jogo": t, "dt_mundo": 1.0 / FPS, "zoom": 1.0,
		"px_por_m": UtilPalco.PX_POR_M, "palco": self, "timeline": null, "corte": false, "tela": tela}
	for item in itens:
		if is_instance_valid(item[0]):
			item[1].call(item[0], t, ctx)
	rotulos.queue_redraw()
	if (movie or relatorio_em != "") and quadro >= total - 1:
		_sair(0)


func _trocar(k: int) -> void:
	pagina = k
	if cena != null:
		cena.queue_free()
	cena = Node2D.new()
	add_child(cena)
	move_child(rotulos, -1)
	itens.clear()
	textos.clear()
	titulo = str(paginas[k][0])
	titulo_embaixo = titulo.begins_with("HUD")
	paginas[k][2].call()


func _rotulo(pos: Vector2, texto: String, tamanho := 34, cor := Color.WHITE) -> void:
	textos.append([pos, texto, tamanho, cor])


func _desenhar_rotulos() -> void:
	# faixa do titulo
	var y0 := tela.y - 150.0 if titulo_embaixo else 0.0
	rotulos.draw_rect(Rect2(0, y0, tela.x, 150), Color(0, 0, 0, 0.55), true)
	rotulos.draw_string_outline(_fonte, Vector2(0, y0 + 100), titulo, HORIZONTAL_ALIGNMENT_CENTER, tela.x, 54, 10, Color.BLACK)
	rotulos.draw_string(_fonte, Vector2(0, y0 + 100), titulo, HORIZONTAL_ALIGNMENT_CENTER, tela.x, 54, Color(1, 0.92, 0.6))
	for r in textos:
		var p: Vector2 = r[0]
		rotulos.draw_string_outline(_fonte, p - Vector2(200, 0), r[1], HORIZONTAL_ALIGNMENT_CENTER, 400, r[2], 8, Color.BLACK)
		rotulos.draw_string(_fonte, p - Vector2(200, 0), r[1], HORIZONTAL_ALIGNMENT_CENTER, 400, r[2], r[3])


func _ctx0() -> Dictionary:
	return {"estilo": estilo, "quadro": maxi(quadro, 0), "fps": FPS, "t_jogo": 0.0, "dt_mundo": 0.0, "zoom": 1.0,
		"px_por_m": UtilPalco.PX_POR_M, "palco": self, "timeline": null, "corte": false, "tela": tela}


# ------------------------------------------------------------ pecas
func _lutador(pos: Vector2, raio_px: float, cor: int, lado: int, nome := "") -> Node:
	var no = bib.lutador(nome, "").instantiate()
	cena.add_child(no)
	no.position = pos
	if no.has_method("configurar"):
		no.configurar({"cor": cor, "cor_lado": lado, "raio_corpo": raio_px / UtilPalco.PX_POR_M, "slot": "p1"}, _ctx0())
	if no.get("_expressoes") != null:
		no.set("_expressoes", RostoPalco.EXPRESSOES)
	return no


func _amostra_lutador(expr: int, ang: float, extra := {}) -> Dictionary:
	var s := {"x": 0.0, "y": 0.0, "z": 0.0, "ang": ang, "expr": expr, "flags": 0, "esc_x": 1.0, "esc_y": 1.0,
		"flash": 0.0, "escudo": 0.0, "_status": []}
	s.merge(extra, true)
	return s


func _pag_rostos_todos() -> void:
	var colunas := 4
	var cel := Vector2(tela.x / colunas, 285)
	for k in 24:
		var c := Vector2((k % colunas + 0.5) * cel.x, 175 + (k / colunas) * cel.y + 118)
		var no := _lutador(c, 96, CORES_CORPO[k % CORES_CORPO.size()], 0xFFFFFF)
		var fase := k * 0.37
		itens.append([no, func(n, t, ctx): n.atualizar(_amostra_lutador(k, 90.0 + 14.0 * sin(t * 1.6 + fase)), ctx)])
		_rotulo(c + Vector2(0, 142), RostoPalco.EXPRESSOES[k], 34)


func _pag_rostos_grandes(desde: int) -> void:
	for j in 6:
		var k := desde + j
		var c := Vector2((j % 2 + 0.5) * tela.x / 2.0, 190 + (j / 2) * 580 + 240)
		var no := _lutador(c, 204, CORES_CORPO[k % CORES_CORPO.size()], 0xFFFFFF)
		itens.append([no, func(n, t, ctx): n.atualizar(_amostra_lutador(k, 90.0 + 8.0 * sin(t * 1.3 + j)), ctx)])
		_rotulo(c + Vector2(0, 268), RostoPalco.EXPRESSOES[k], 44)


func _pag_eventos() -> void:
	var colunas := 4
	var cel := Vector2(tela.x / colunas, 430)
	for k in EVENTOS.size():
		var c := Vector2((k % colunas + 0.5) * cel.x, 200 + (k / colunas) * cel.y + 190)
		var alvo := _lutador(c, 60, 0x9AA3B5, 0xFFFFFF)
		alvo.modulate = Color(1, 1, 1, 0.5)
		itens.append([alvo, func(n, t, ctx): n.atualizar(_amostra_lutador(0, 90.0), ctx)])
		var raiz := Node2D.new()
		raiz.position = c
		raiz.scale = Vector2.ONE * 0.62
		cena.add_child(raiz)
		var ev: Array = EVENTOS[k]
		itens.append([raiz, _tocar_evento.bind(ev, k)])
		_rotulo(c + Vector2(0, 205), str(ev[2]), 32)


## Dispara o efeito a cada 1,2 s (o efeito se apaga sozinho).
func _tocar_evento(raiz: Node2D, t: float, ctx: Dictionary, ev: Array, k: int) -> void:
	var ciclo := 1.2
	if int(round(t * FPS)) % int(ciclo * FPS) == 0:
		var tipo := str(ev[0])
		var dados := {"tipo": tipo, "tier": str(ev[1]), "i": quadro + k * 7, "dir": -35.0, "ang": -90.0,
			"elemento": "ARCANO", "vx": 1.0, "vy": -0.3, "dano_pct": 0.12, "intensidade": 7.0, "x": 0.0, "y": 0.0}
		if tipo == "acerto_critico":
			dados["tipo"] = "acerto"
			dados["critico"] = true
		var no = bib.evento(str(dados["tipo"]), str(ev[1])).instantiate()
		raiz.add_child(no)
		if no.has_method("configurar"):
			no.configurar(dados, ctx)
	for filho in raiz.get_children():
		if filho.has_method("atualizar") and not filho.is_queued_for_deletion():
			filho.atualizar({}, ctx)


func _pag_efeitos(desde: int) -> void:
	var tipos := ["projetil", "area", "beam"]
	var alto := 285.0
	for j in 6:
		var el: String = ELEMENTOS[desde + j]
		var y := 210.0 + j * alto + alto * 0.5
		_rotulo(Vector2(tela.x * 0.5, y - alto * 0.5 + 30), el, 30, Color(1, 1, 1, 0.85))
		for i in tipos.size():
			var tipo: String = tipos[i]
			var c := Vector2((i + 0.5) * tela.x / 3.0, y + 18)
			var dados := {"tipo": tipo, "elemento": el, "cor": 0xFFFFFF, "id": j * 3 + i, "raio_max": 1.05,
				"de": [(c.x - 150.0) / 100.0, c.y / 100.0], "ate": [(c.x + 150.0) / 100.0, c.y / 100.0]}
			var no = bib.objeto(tipo, el, "").instantiate()
			cena.add_child(no)
			no.position = c if tipo != "beam" else Vector2.ZERO
			if no.has_method("configurar"):
				no.configurar(dados, _ctx0())
			itens.append([no, _mover_objeto.bind(tipo, c, j * 0.9 + i)])
	for i in tipos.size():
		_rotulo(Vector2((i + 0.5) * tela.x / 3.0, 200), ["projétil", "área", "beam"][i], 36, Color(1, 0.92, 0.6))


func _mover_objeto(no: Node2D, t: float, ctx: Dictionary, tipo: String, c: Vector2, fase: float) -> void:
	match tipo:
		"projetil":
			no.position = c + Vector2(cos(t * 2.6 + fase) * 110.0, sin(t * 2.6 + fase) * 55.0)
			# r = 0,45 m: na luta a camera amplia ~2x, aqui a vitrine e 1:1
			no.atualizar({"x": no.position.x / 100.0, "y": no.position.y / 100.0, "r": 0.45, "ang": rad_to_deg(t * 2.6 + fase) + 90.0, "prog": fmod(t / 2.5, 1.0)}, ctx)
		"area":
			var ciclo := fmod(t / 2.5 + fase * 0.1, 1.0)
			no.atualizar({"x": c.x / 100.0, "y": c.y / 100.0, "r": 1.05 * (0.55 + 0.45 * minf(1.0, ciclo * 4.0)),
				"ativ": 1 if ciclo > 0.18 else 0, "prog": ciclo}, ctx)
		"beam":
			no.atualizar({"larg": 11.0, "prog": fmod(t / 2.5 + fase * 0.1, 1.0) * 0.85}, ctx)


func _pag_hud() -> void:
	var a := _lutador(Vector2(tela.x * 0.33, tela.y * 0.55), 110, 0xE0605E, 0xE74C3C, "Isandro Lumeprego")
	var b := _lutador(Vector2(tela.x * 0.67, tela.y * 0.55), 110, 0x6B84E8, 0x3498DB, "Silas o Sombrio")
	var hud = bib.hud().instantiate()
	cena.add_child(hud)
	if hud.has_method("configurar"):
		hud.configurar({"lutadores": [
			{"nome": "Isandro Lumeprego", "cor_lado": 0xE74C3C},
			{"nome": "Silas o Sombrio", "cor_lado": 0x3498DB}], "planos": PLANOS}, _ctx0())
	var golpes := Node2D.new()
	cena.add_child(golpes)
	itens.append([a, _mover_lutador.bind(0)])
	itens.append([b, _mover_lutador.bind(1)])
	itens.append([hud, _hud_falso.bind(a, b, golpes)])


func _mover_lutador(n: Node2D, t: float, ctx: Dictionary, lado: int) -> void:
	if lado == 0:
		n.position = Vector2(tela.x * 0.33 + sin(t * 2.0) * 90.0, tela.y * 0.55 + cos(t * 1.4) * 60.0)
		n.atualizar(_amostra_lutador(3 if t < 4.5 else 8, 0.0), ctx)
	else:
		n.position = Vector2(tela.x * 0.67 - sin(t * 2.2) * 80.0, tela.y * 0.55 - cos(t * 1.1) * 70.0)
		n.atualizar(_amostra_lutador(11 if t < 4.5 else 15, 180.0, {"flags": 2 if t >= 4.5 else 0}), ctx)


func _hud_falso(hud: Node, t: float, ctx: Dictionary, a: Node2D, b: Node2D, golpes: Node2D) -> void:
	# a vida cai em degraus (um por golpe) e o plano troca a cada 1,5 s
	var golpes_b := mini(6, int(t / 0.7))
	var hp_b := 1.0 - golpes_b * 0.167 if t < 4.5 else 0.0
	var hp_a := 1.0 - mini(3, int(t / 1.4)) * 0.12
	var p1 := {"hp": hp_a, "plano": int(t / 1.5) % PLANOS.size(), "plano_p": fmod(t / 1.5, 1.0)}
	var p2 := {"hp": hp_b, "plano": (int(t / 1.5) + 3) % PLANOS.size(), "plano_p": fmod(t / 1.5 + 0.3, 1.0)}
	hud.atualizar({"p1": p1, "p2": p2}, ctx)
	if int(round(t * FPS)) % 21 == 0 and t > 0.1 and t < 4.6:
		var no = bib.evento("acerto", "heavy").instantiate()
		golpes.add_child(no)
		no.position = b.position.lerp(a.position, 0.25)
		if no.has_method("configurar"):
			no.configurar({"tipo": "acerto", "tier": "heavy", "i": quadro, "dir": 180.0, "dano_pct": 0.17}, ctx)
	for filho in golpes.get_children():
		if filho.has_method("atualizar") and not filho.is_queued_for_deletion():
			filho.atualizar({}, ctx)


func _pag_armas() -> void:
	for k in TIPOS_ARMA.size():
		var c := Vector2((k % 2 + 0.5) * tela.x / 2.0 - 90.0, 200 + (k / 2) * 420 + 210)
		var corpo := _lutador(c, 70, CORES_CORPO[k % CORES_CORPO.size()], 0xFFFFFF)
		itens.append([corpo, func(n, t, ctx): n.atualizar(_amostra_lutador(3, 0.0), ctx)])
		var arma = bib.arma(TIPOS_ARMA[k], "").instantiate()
		cena.add_child(arma)
		arma.position = c + Vector2(55, 0)
		if arma.has_method("configurar"):
			arma.configurar({"tipo": TIPOS_ARMA[k], "cor": 0xD0D6E0, "raio_corpo": 0.7, "slot": "p1"}, _ctx0())
		itens.append([arma, _golpe.bind(k)])
		_rotulo(c + Vector2(90, 190), TIPOS_ARMA[k], 38)


func _golpe(arma: Node2D, t: float, ctx: Dictionary, k: int) -> void:
	var ciclo := fmod(t / 1.6 + k * 0.13, 1.0)
	var fase := clampi(int(ciclo * 5.0) + 1, 1, 5)
	arma.rotation = sin(ciclo * TAU) * 0.9
	var comp := 170.0
	var s := {"_comprimento_px": comp, "golpe_fase": fase, "golpe_p": fmod(ciclo * 5.0, 1.0), "flags": 0,
		"arma_ang": rad_to_deg(arma.rotation), "arma_gx": 0.0, "arma_gy": 0.0, "arma_px": comp / 100.0, "arma_py": 0.0}
	if arma.has_method("atualizar"):
		arma.atualizar(s, ctx)
	else:
		arma.scale = Vector2.ONE * comp / 100.0


## As cenas da biblioteca feitas com efeitos/folha_animada.gd.
func _achar_folhas(pasta: String) -> Array:
	var achadas: Array = []
	var dir := DirAccess.open(pasta)
	if dir == null:
		return achadas
	for sub in dir.get_directories():
		achadas.append_array(_achar_folhas(pasta + sub + "/"))
	for arquivo in dir.get_files():
		if arquivo.ends_with(".tscn") and FileAccess.get_file_as_string(pasta + arquivo).contains("folha_animada.gd"):
			achadas.append(pasta + arquivo)
	achadas.sort()
	return achadas


func _pag_folhas(lista: Array) -> void:
	var colunas := 3
	var cel := Vector2(tela.x / colunas, 420)
	for k in lista.size():
		var caminho: String = lista[k]
		var c := Vector2((k % colunas + 0.5) * cel.x, 200 + (k / colunas) * cel.y + 180)
		var evento := caminho.contains("/eventos/")
		var raiz := Node2D.new()
		raiz.position = c
		cena.add_child(raiz)
		itens.append([raiz, _tocar_folha.bind(load(caminho), evento, k)])
		_rotulo(c + Vector2(0, 200), caminho.get_file().get_basename() + ("" if not evento else " (evento)"), 30)
		_rotulo(c + Vector2(0, 236), caminho.get_base_dir().replace("res://biblioteca/efeitos/", ""), 24, Color(1, 1, 1, 0.6))


func _tocar_folha(raiz: Node2D, t: float, ctx: Dictionary, cena_folha: PackedScene, evento: bool, k: int) -> void:
	if evento:
		if int(round(t * FPS)) % int(1.5 * FPS) == 0:
			var no = cena_folha.instantiate()
			raiz.add_child(no)
			if no.has_method("configurar"):
				no.configurar({"tipo": "acerto", "i": quadro + k, "dir": -20.0, "elemento": "NATUREZA"}, ctx)
		for filho in raiz.get_children():
			if filho.has_method("atualizar") and not filho.is_queued_for_deletion():
				filho.atualizar({}, ctx)
		return
	if raiz.get_child_count() == 0:
		var no = cena_folha.instantiate()
		raiz.add_child(no)
		if no.has_method("configurar"):
			no.configurar({"tipo": "projetil", "id": k, "elemento": "NATUREZA"}, ctx)
	var peca = raiz.get_child(0)
	var a := t * 1.8 + k
	peca.position = Vector2(cos(a) * 90.0, sin(a) * 60.0)
	if peca.has_method("atualizar"):
		peca.atualizar({"x": 0.0, "y": 0.0, "r": 0.45, "ang": rad_to_deg(a) + 90.0, "prog": fmod(t / 5.0, 1.0)}, ctx)


# ------------------------------------------------------------ saida
func _sair(rc: int) -> void:
	if relatorio_em != "":
		var f := FileAccess.open(relatorio_em, FileAccess.WRITE)
		if f != null:
			f.store_string(JSON.stringify({"ok": rc == 0, "rc": rc, "quadros": total, "fps": FPS,
				"duracao": total / float(FPS), "tela": [tela.x, tela.y], "movie": movie,
				"paginas": paginas.map(func(p): return [p[0], p[1]]), "pecas": bib.escolhas,
				"reservas": bib.reservas.keys(), "avisos": avisos, "laco_ms": Time.get_ticks_msec() - t0_ms}, "  "))
			f.close()
	for a in avisos:
		printerr("[vitrine] ", a)
	get_tree().quit(rc)
