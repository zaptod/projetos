extends SceneTree
## Testes do nucleo do palco, sem janela:
##
##   godot --headless --path palco --script res://ferramentas/testes.gd
##
## Saida 0 = todos passaram. Quem roda pela suite e
## random_builds/tests/test_palco_regressions.py (pula com motivo sem Godot).

var falhas := PackedStringArray()
var feitos := 0


func _checar(cond: bool, nome: String) -> void:
	feitos += 1
	if not cond:
		falhas.append(nome)
		printerr("FALHOU: ", nome)


func _initialize() -> void:
	_testar_slug()
	_testar_plano()
	_testar_biblioteca()
	_testar_timeline()
	_testar_revisao_3()
	_testar_revisao_4()
	# todo script do palco compila (o que a biblioteca nao carregou acima)
	for s in ["res://nucleo/palco.gd", "res://nucleo/sons.gd", "res://biblioteca/lutadores/rosto.gd",
			"res://biblioteca/hud/hud_padrao.gd", "res://ferramentas/validar.gd", "res://ferramentas/vitrine.gd",
			"res://biblioteca/efeitos/objetos/objeto_cc0.gd", "res://biblioteca/efeitos/folha_animada.gd",
			"res://biblioteca/armas/tipos/corrente.gd"]:
		var script = load(s)
		_checar(script is GDScript and script.can_instantiate(), "compila: " + s)
	_checar(load("res://palco.tscn") is PackedScene, "a cena principal carrega")
	_checar(load("res://ferramentas/vitrine.tscn") is PackedScene, "a vitrine carrega")
	print("testes do palco: %d checagens, %d falha(s)" % [feitos, falhas.size()])
	quit(0 if falhas.is_empty() else 1)


func _testar_slug() -> void:
	_checar(UtilPalco.slug("Mágica") == "magica", "slug Mágica")
	_checar(UtilPalco.slug("Transformável") == "transformavel", "slug Transformável")
	_checar(UtilPalco.slug("Machado-Martelo") == "machado_martelo", "slug Machado-Martelo")
	_checar(UtilPalco.slug("Piromante (Fogo)") == "piromante_fogo", "slug Piromante (Fogo)")
	_checar(UtilPalco.slug("  Lança  ") == "lanca", "slug Lança")


func _testar_plano() -> void:
	# sem remapeamento: a gravacao inteira, 1 quadro a cada 2 passos
	var p := PlanoQuadros.montar(1456.0 / 60.0, null, 30)
	_checar(p.total() == 728, "plano sem corte: 728 quadros (%d)" % p.total())
	_checar(p.mapear(0.0) == 0 and p.mapear(1.0) == 30, "plano sem corte: t=1 s no quadro 30")
	# o corte do duelo_00016 (fight.json): 2,43 s + 20,8 s
	var c := PlanoQuadros.montar(1456.0 / 60.0, {"trechos": [[0.0, 2.43], [3.47, 20.8]]}, 30)
	_checar(c.total() == 73 + 624, "plano com corte: 697 quadros (%d)" % c.total())
	_checar(c.mapear(3.0) == -1, "evento dentro do corte sai")
	_checar(c.mapear(3.47) == 73, "inicio do 2o trecho no quadro 73 (%d)" % c.mapear(3.47))
	_checar(c.velocidade(73) == 0.0 and c.inicio_de_trecho(73), "jump cut zera o relogio dos efeitos")
	_checar(is_equal_approx(c.t_src[74], 3.47 + 1.0 / 30.0), "quadro 74 mostra 3,47 s + 1 quadro")
	# camera lenta do palco: 1 s a 0,5x vira 60 quadros
	var l := PlanoQuadros.montar(2.0, {"trechos": [[0.0, 1.0, 1.0], [1.0, 1.0, 0.5]]}, 30)
	_checar(l.total() == 90, "camera lenta 0,5x: 90 quadros (%d)" % l.total())
	_checar(l.mapear(1.5) == 60, "camera lenta: 1,5 s no quadro 60 (%d)" % l.mapear(1.5))
	_checar(is_equal_approx(l.velocidade(40), 0.5), "camera lenta anda meio quadro por quadro")
	# hitstop do render: 0,1 s parado no acerto de t=1 s
	var h := PlanoQuadros.montar(2.0, null, 30)
	h.com_hitstop([[1.0, 0.1]])
	_checar(h.total() == 63, "hitstop acrescenta 3 quadros (%d)" % h.total())
	_checar(h.mapear(1.0) == 30 and h.mapear(1.5) == 48, "sons depois do hitstop andam 3 quadros")
	_checar(h.velocidade(31) == 0.0 and h.parado[31] == 1, "quadro de hitstop e parado")


func _nome(cena: PackedScene) -> String:
	var no := cena.instantiate()
	var nome := str(no.name)
	no.free()
	return nome


func _testar_biblioteca() -> void:
	var b := Biblioteca.new()
	b.raiz = "res://ferramentas/teste_biblioteca/"
	_checar(_nome(b.arma("Transformável", "Machado-Martelo")) == "EstiloMachadoMartelo", "arma: o ESTILO vence o tipo")
	_checar(_nome(b.arma("Reta", "Katana")) == "TipoReta", "arma: sem estilo, vale o TIPO")
	_checar(_nome(b.arma("Arco", "Arco Longo")) == "Padrao", "arma: sem tipo, vale o _padrao")
	_checar(b.reservas.has("armas:Arco/Arco Longo"), "arma no _padrao aparece no relatorio")
	var reserva := b.lutador("Ninguem", "Classe Nenhuma")
	var no := reserva.instantiate()
	_checar(no.get("categoria") == "lutadores", "sem _padrao: entra a reserva embutida")
	_checar(str(b.escolhas.get("lutadores:Ninguem/Classe Nenhuma", "")).begins_with("(reserva"), "reserva embutida registrada")
	no.free()
	# a biblioteca de verdade tem _padrao em todas as categorias
	var real := Biblioteca.new()
	for cena in [real.arma("X", "Y"), real.lutador("X", "Y"), real.objeto("projetil", "FOGO", "X"),
			real.evento("acerto", "heavy"), real.arena("X", "Y"), real.hud()]:
		_checar(cena is PackedScene, "biblioteca real resolve alguma peca")
	# o projetil de FOGO tem arte propria (16E): 5 dos 6 pedidos no _padrao
	_checar(real.reservas.size() == 5, "biblioteca real: 5 pedidos no _padrao (%d)" % real.reservas.size())
	# efeitos por (tipo x elemento): o par > o padrao do tipo > o padrao geral
	var ef := Biblioteca.new()
	ef.objeto("projetil", "GRAVITAÇÃO", "")
	_checar(str(ef.escolhas.get("efeitos:projetil/GRAVITAÇÃO/", "")).ends_with("objetos/projetil/gravitacao.tscn"), "efeito: o par tipo x elemento")
	ef.objeto("area", "ELEMENTO NOVO", "")
	_checar(str(ef.escolhas.get("efeitos:area/ELEMENTO NOVO/", "")).ends_with("objetos/area/_padrao.tscn"), "efeito: elemento sem arte cai no padrao do TIPO")
	ef.objeto("orbe", "FOGO", "")
	_checar(str(ef.escolhas.get("efeitos:orbe/FOGO/", "")).ends_with("objetos/_padrao.tscn"), "efeito: tipo sem arte cai no padrao geral")
	for tipo in ["projetil", "area", "beam"]:
		for el in UtilPalco.PALETAS:
			if el == "DEFAULT":
				continue
			var c := ef.objeto(tipo, el, "")
			var peca_ef = c.instantiate()
			_checar(peca_ef.get("aditivo") != null, "efeito %s/%s usa o objeto_cc0" % [tipo, el])
			peca_ef.free()
	# folha de sprite (formato da Oficina): evento toca uma volta e se apaga
	var img := Image.create(64, 32, false, Image.FORMAT_RGBA8)
	var folha = load("res://biblioteca/efeitos/folha_animada.gd").new()
	folha.folha = ImageTexture.create_from_image(img)
	folha.colunas = 4
	folha.linhas = 2
	folha.quadros = 6
	folha.fps = 12.0
	folha.laco = false
	folha.configurar({"tipo": "acerto", "dir": 0.0}, {})
	_checar(is_equal_approx(folha._vida(), 0.5), "folha: 6 quadros a 12 fps vivem 0,5 s")
	for _q in 14:
		folha.atualizar({}, {"dt_mundo": 1.0 / 30.0})
	_checar(not folha.is_queued_for_deletion(), "folha: viva aos 0,47 s")
	for _q in 2:
		folha.atualizar({}, {"dt_mundo": 1.0 / 30.0})
	_checar(folha.is_queued_for_deletion(), "folha: o evento se apaga no fim da volta")
	# o rosto: as 24 expressoes do jogo e as pecas do Kenney carregam
	_checar(RostoPalco.EXPRESSOES.size() == 24, "rosto: 24 expressoes (%d)" % RostoPalco.EXPRESSOES.size())
	for nome in RostoPalco.PECAS:
		var tex: Texture2D = RostoPalco.PECAS[nome]
		_checar(tex != null and tex.get_width() >= 100, "rosto: peca %s carregou" % nome)
	# nitidas a 408 px: com a bolinha de 408 px de diametro (R = 204 na tela),
	# nenhuma peca de nenhuma das 24 expressoes e AMPLIADA (o png sempre diminui)
	var maior := {}
	for expr in RostoPalco.EXPRESSOES:
		var r := RostoPalco.new(RostoPalco.Gravador.new(), 204.0, 1.0, 0, Color.RED, false)
		r.desenhar(expr)
		for nome in r.ampliacao:
			maior[nome] = maxf(float(maior.get(nome, 0.0)), float(r.ampliacao[nome]))
	_checar(maior.size() >= 12, "rosto: as expressoes usam as pecas do Kenney (%d)" % maior.size())
	for nome in maior:
		_checar(float(maior[nome]) <= 1.0, "rosto: %s nitida a 408 px (ampliada %.2fx)" % [nome, maior[nome]])
	for chave in real.escolhas:
		_checar(not str(real.escolhas[chave]).begins_with("(reserva"), "biblioteca real sem reserva embutida: " + chave)


func _doc(n: int) -> Dictionary:
	var canais_l := {}
	for c in Timeline.CANAIS_LUTADOR:
		var v := []
		v.resize(n)
		v.fill(0.0)
		canais_l[c] = v
	var bloco := func(nomes: Array) -> Dictionary:
		var d := {}
		for c in nomes:
			var v := []
			v.resize(n)
			v.fill(1.0)
			d[c] = v
		return d
	return {
		"formato": "neural-fights/timeline", "versao": 1, "hz": 60, "n": n,
		"lutadores": [{"slot": "p1", "raio_corpo": 0.8}, {"slot": "p2", "raio_corpo": 0.9}],
		"trilhas": {"global": bloco.call(Timeline.CANAIS_GLOBAIS), "camera": bloco.call(Timeline.CANAIS_CAMERA),
			"lutadores": {"p1": canais_l.duplicate(true), "p2": canais_l.duplicate(true)},
			"objetos": [{"id": 1, "tipo": "orbe", "i0": 2, "i1": 4, "x": [0, 0, 0], "y": [0, 0, 0], "r": [1, 1, 1], "estado": [0, 0, 0]}],
			"efeitos": []},
		"eventos": [{"i": 1, "t": 1.0 / 60.0, "tipo": "acerto"}],
		"sons": {"versao": 1, "relogio": "video", "itens": [{"t": 0.0, "id": "slash_light", "volume": 0.5, "pitch": 1.0}]},
		"remapeamento": null,
	}


func _testar_timeline() -> void:
	var ok := Timeline.de_dicionario(_doc(10))
	_checar(ok.validar().is_empty(), "timeline minima valida: %s" % str(ok.validar()))
	var casos := {
		"versao errada": func(d): d["versao"] = 2,
		"canal curto": func(d): d["trilhas"]["lutadores"]["p2"]["x"].pop_back(),
		"objeto fora do intervalo": func(d): d["trilhas"]["objetos"][0]["i1"] = 99,
		"evento fora da luta": func(d): d["eventos"][0]["i"] = 10,
		"som sem id": func(d): d["sons"]["itens"][0].erase("id"),
		"trechos sobrepostos": func(d): d["remapeamento"] = {"relogio": "gravacao", "trechos": [[0.0, 0.1], [0.05, 0.05]]},
	}
	for nome in casos:
		var d := _doc(10)
		casos[nome].call(d)
		_checar(not Timeline.de_dicionario(d).validar().is_empty(), "timeline invalida recusada: " + nome)
	# angulo interpola pelo caminho curto (170 -> -170 passa por 180)
	var a := Timeline.amostra({"ang": [170.0, -170.0]}, ["ang"], 0.5)
	_checar(absf(absf(float(a["ang"])) - 180.0) < 0.01, "angulo pelo caminho curto (%s)" % str(a["ang"]))
	var b := Timeline.amostra({"x": [0.0, 2.0], "expr": [3, 7]}, ["x", "expr"], 0.5)
	_checar(is_equal_approx(float(b["x"]), 1.0) and int(b["expr"]) == 3, "continuo interpola, discreto pega o passo de baixo")


## Revisao 4: a bola da corrente nova. Doc sintetico: a bola gira em volta da
## mao (1,5 m, 9 m/s), o golpe 2 comeca no passo 20 e os passos 41..44 sao
## hitstop (o tempo de jogo nao anda e nada se mexe).
func _doc_corrente(n: int) -> Dictionary:
	var d := _doc(n)
	var raio := 0.8
	var mao := Vector2(raio * 0.9, raio * 0.15)
	var bx := []
	var by := []
	var bvx := []
	var bvy := []
	var tj := []
	var gid := []
	var t := 0.0
	for k in n:
		var kk := mini(k, 40) if k <= 44 else k - 4
		var a := kk * 0.1
		bx.append(mao.x + cos(a) * 1.5)
		by.append(mao.y + sin(a) * 1.5)
		bvx.append(-sin(a) * 9.0)
		bvy.append(cos(a) * 9.0)
		if k > 0 and not (k >= 41 and k <= 44):
			t += 1.0 / 60.0
		tj.append(t)
		gid.append(1 if k < 20 else 2)
	var lp1: Dictionary = d["trilhas"]["lutadores"]["p1"]
	lp1["bola_x"] = bx
	lp1["bola_y"] = by
	lp1["bola_vx"] = bvx
	lp1["bola_vy"] = bvy
	lp1["golpe_id"] = gid
	d["trilhas"]["global"]["tj"] = tj
	d["revisao"] = 4
	d["lutadores"][0]["arma"] = {"tipo": "Corrente", "estilo": "Mangual", "cor": 0xC0C0C0,
		"corrente": {"comp_m": 2.0, "n_elos": 16, "cabeca": "bola_espinhos", "material": "elos",
			"familia": "pesada", "raio_bola_m": 0.25, "v_ref_ms": 20.0,
			"mao": {"avanco_r": 0.9, "lateral_r": 0.15}}}
	return d


func _testar_revisao_4() -> void:
	var tl := Timeline.de_dicionario(_doc_corrente(80))
	_checar(tl.validar().is_empty(), "revisao 4 valida: %s" % str(tl.validar()))
	_checar(not tl.corrente_do("p1").is_empty() and tl.corrente_do("p2").is_empty(), "corrente_do so de quem tem bola")
	var ruins := {
		"canal da bola faltando": func(d): d["trilhas"]["lutadores"]["p1"].erase("bola_vy"),
		"canal da bola curto": func(d): d["trilhas"]["lutadores"]["p1"]["bola_x"].pop_back(),
		"cabecalho sem canais": func(d): d["lutadores"][1]["arma"] = d["lutadores"][0]["arma"],
		"canais sem cabecalho": func(d): d["lutadores"][0]["arma"].erase("corrente"),
		"sem n_elos": func(d): d["lutadores"][0]["arma"]["corrente"].erase("n_elos"),
	}
	for nome in ruins:
		var dr := _doc_corrente(80)
		ruins[nome].call(dr)
		_checar(not Timeline.de_dicionario(dr).validar().is_empty(), "revisao 4 recusa: " + nome)
	var s := tl.lutador("p1", 10.5)
	var bx: Array = tl.canal_lutador("p1", "bola_x")
	_checar(s.has("bola_x") and is_equal_approx(float(s["bola_x"]), (float(bx[10]) + float(bx[11])) / 2.0),
		"bola_x interpola entre os passos")
	_checar(not tl.lutador("p2", 3.0).has("bola_x"), "lutador sem corrente nao tem bola")

	var cena: PackedScene = load("res://biblioteca/armas/tipos/corrente.tscn")
	_checar(cena is PackedScene, "a peca da corrente carrega")
	var no = cena.instantiate()
	var dados: Dictionary = tl.cabecalho_lutador("p1")["arma"].duplicate(true)
	dados["slot"] = "p1"
	dados["raio_corpo"] = 0.8
	no.configurar(dados, {})
	var quadro := func(p: float) -> PackedVector2Array:
		no.atualizar(tl.lutador("p1", p), {"timeline": tl, "passo": p})
		return no._pontos.duplicate()
	var a := quadro.call(60.0) as PackedVector2Array
	_checar(no._ativo and a.size() >= 5, "a corrente nova desenha (%d pontos)" % a.size())
	var mao := Vector2(0.72, 0.12) * UtilPalco.PX_POR_M
	var bola := Vector2(float(bx[60]), float(tl.canal_lutador("p1", "bola_y")[60])) * UtilPalco.PX_POR_M
	_checar(a[0].distance_to(mao) < 0.01, "a ponta da corrente na mao")
	_checar(a[a.size() - 1].distance_to(bola) < 0.01, "a outra ponta na bola (%s x %s)" % [a[a.size() - 1], bola])
	var segs := PackedFloat32Array()
	for j in range(1, a.size()):
		segs.append(a[j].distance_to(a[j - 1]))
	var mn := 1e9
	var mx := 0.0
	for v in segs:
		mn = minf(mn, v)
		mx = maxf(mx, v)
	_checar(mx - mn < 0.05 * mx, "elos do mesmo tamanho (%.2f..%.2f)" % [mn, mx])
	var total := 0.0
	for v in segs:
		total += v
	_checar(total <= 2.0 * UtilPalco.PX_POR_M + 0.5 and total >= a[0].distance_to(a[a.size() - 1]) - 0.5,
		"a corrente nao passa do comprimento (%.1f px)" % total)
	# sem estado: ir e voltar (seek, corte de tedio) da a MESMA corrente
	quadro.call(5.0)
	quadro.call(33.5)
	var de_novo := quadro.call(60.0) as PackedVector2Array
	_checar(de_novo == a, "sem estado: o mesmo passo da a mesma corrente depois de um seek")
	# hitstop: o tempo de jogo parado congela a corrente com o mundo
	var h1 := quadro.call(41.0) as PackedVector2Array
	var h2 := quadro.call(44.0) as PackedVector2Array
	_checar(h1 == h2, "no hitstop a corrente fica parada")
	# a janela nunca passa de 60 passos e respeita o inicio do golpe
	_checar(no._inicio(25) == 20, "a integracao parte do inicio do golpe (%d)" % no._inicio(25))
	_checar(79 - no._inicio(79) <= 60, "janela de no maximo 60 passos (%d)" % no._inicio(79))
	no.free()
	# luta SEM a chave: a mesma peca cai na corrente antiga, sem erro
	var velha = cena.instantiate()
	var d_velha := {"tipo": "Corrente", "estilo": "Mangual", "slot": "p1", "raio_corpo": 0.8}
	velha.configurar(d_velha, {})
	velha.atualizar(Timeline.de_dicionario(_doc(10)).lutador("p1", 2.0), {"timeline": Timeline.de_dicionario(_doc(10)), "passo": 2.0})
	_checar(not velha._ativo and velha.rastro_proprio == false, "sem a bola, a corrente antiga (e o rastro de antes)")
	velha.free()


## Revisao 3 da timeline: os eventos novos passam, os malformados nao, e a
## timeline antiga (sem nenhum deles e sem `revisao`) continua valida.
func _testar_revisao_3() -> void:
	var antiga := Timeline.de_dicionario(_doc(10))
	_checar(antiga.revisao() == 1, "sem o campo, a revisao e 1")
	var novos := [
		{"i": 2, "t": 2 / 60.0, "tipo": "acerto", "alvo": "p2", "ponto": [1.5, 2.5], "projetil": 7},
		{"i": 2, "t": 2 / 60.0, "tipo": "projetil_fim", "id": 7, "objeto": "projetil", "dono": "p1",
			"motivo": "acerto", "alvo": "p2", "x": 1.5, "y": 2.5, "elemento": "FOGO"},
		{"i": 2, "t": 2 / 60.0, "tipo": "explosao", "origem": "impacto", "x": 1.5, "y": 2.5, "elemento": "FOGO", "tamanho": 1.2},
		{"i": 3, "t": 3 / 60.0, "tipo": "choque", "origem": "projeteis", "x": 3.0, "y": 3.0, "cor1": 0xFF0000, "cor2": 0x0000FF},
		{"i": 3, "t": 3 / 60.0, "tipo": "refletido", "id": 8, "de": "p1", "para": "p2", "x": 3.0, "y": 3.0},
		{"i": 4, "t": 4 / 60.0, "tipo": "texto", "texto_id": 1, "texto": "FATAL!", "estilo": "fatal", "x": 1.0, "y": 1.0},
		{"i": 4, "t": 4 / 60.0, "tipo": "movimento", "slot": "p1", "gatilho": "dash", "vfx": ["afterimage", "linhas"], "x": 1.0, "y": 1.0},
		{"i": 5, "t": 5 / 60.0, "tipo": "tipo_que_ainda_nao_existe", "qualquer": 1},
	]
	var d := _doc(10)
	d["revisao"] = 99
	d["eventos"] = novos
	var tl := Timeline.de_dicionario(d)
	_checar(tl.validar().is_empty(), "revisao 3 valida: %s" % str(tl.validar()))
	_checar(tl.revisao() == 99, "revisao maior que a conhecida continua valida")
	var ruins := {
		"motivo desconhecido": func(e): e[1]["motivo"] = "evaporou",
		"texto sem texto": func(e): e[5].erase("texto"),
		"ponto torto": func(e): e[0]["ponto"] = [1.0],
		"movimento sem lista": func(e): e[6]["vfx"] = "afterimage",
		"explosao sem x": func(e): e[2].erase("x"),
	}
	for nome in ruins:
		var dr := _doc(10)
		var evs: Array = novos.duplicate(true)
		ruins[nome].call(evs)
		dr["eventos"] = evs
		_checar(not Timeline.de_dicionario(dr).validar().is_empty(), "revisao 3 recusa: " + nome)
	var dz := _doc(10)
	dz["revisao"] = 0
	_checar(not Timeline.de_dicionario(dz).validar().is_empty(), "revisao 0 recusada")
	# explosao e choque viram efeito com o que a biblioteca ja tem; texto e
	# movimento nao pedem peca
	_checar(Timeline.EVENTOS_COM_VFX.has("explosao") and Timeline.EVENTOS_COM_VFX.has("choque"), "explosao e choque desenham")
	_checar(not Timeline.EVENTOS_COM_VFX.has("texto") and not Timeline.EVENTOS_COM_VFX.has("movimento"), "texto e movimento nao desenham")
	var cena: PackedScene = load("res://biblioteca/efeitos/eventos/_padrao.tscn")
	for ev in [novos[2], novos[3], {"i": 1, "tipo": "explosao", "origem": "area", "x": 0.0, "y": 0.0, "cor": 0xFF6432, "tamanho": 2.0}]:
		var no = cena.instantiate()
		no.configurar(ev, {})
		for _q in 3:
			no.atualizar({}, {"dt_mundo": 1.0 / 30.0})
		_checar(not no.is_queued_for_deletion(), "vfx %s/%s vivo no 3o quadro" % [ev["tipo"], ev.get("origem", "")])
		for _q in 20:
			no.atualizar({}, {"dt_mundo": 1.0 / 30.0})
		_checar(no.is_queued_for_deletion(), "vfx %s/%s se apaga" % [ev["tipo"], ev.get("origem", "")])
		no.free()
