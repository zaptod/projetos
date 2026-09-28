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
	# todo script do palco compila (o que a biblioteca nao carregou acima)
	for s in ["res://nucleo/palco.gd", "res://nucleo/sons.gd", "res://biblioteca/lutadores/rosto.gd",
			"res://biblioteca/hud/hud_padrao.gd", "res://ferramentas/validar.gd"]:
		var script = load(s)
		_checar(script is GDScript and script.can_instantiate(), "compila: " + s)
	_checar(load("res://palco.tscn") is PackedScene, "a cena principal carrega")
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
	_checar(real.reservas.size() == 6, "biblioteca real: 6 pedidos no _padrao (%d)" % real.reservas.size())
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
