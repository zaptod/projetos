extends SceneTree
## A ARMA como peca (16F): a cena com o `nucleo/peca.gd` (a que a Oficina
## exporta: empunhadura na origem, ponta em +x, `comprimento_ref`) estica ate
## o comprimento que a timeline manda, com a empunhadura na MAO e a ponta na
## ponta da hitbox. Antes a peca com o peca.gd ficava no tamanho desenhado:
## o palco so escalava a peca SEM `atualizar`, e o peca.gd tem um vazio.
##
##   godot --headless --path palco --script res://testes/arma_estica.gd
##   ... -- --cena=<arma.tscn> --meta=<arma.json>   (a cena da Oficina)
##
## Saida 0 = tudo certo. Quem roda pela suite e palco/testes/test_arma_estica.py,
## que exporta a cena de um PNG gerado por codigo e passa os dois caminhos.

const PX := UtilPalco.PX_POR_M
# a mao em (1, 2) m e a ponta em (4, 6) m: 500 px de arma, inclinada
const MAO := Vector2(1.0, 2.0)
const PONTA := Vector2(4.0, 6.0)
const TOL := 0.5

var falhas := PackedStringArray()
var feitos := 0
var palco
var lixo: Array = []


func _checar(cond: bool, nome: String) -> void:
	feitos += 1
	if not cond:
		falhas.append(nome)
		printerr("FALHOU: ", nome)


func _initialize() -> void:
	palco = load("res://nucleo/palco.gd").new()
	palco.estilo = load("res://biblioteca/estilo.tres")
	var args := {}
	for a in OS.get_cmdline_user_args():
		var i := str(a).find("=")
		if i > 0:
			args[str(a).substr(0, i)] = str(a).substr(i + 1)

	# a peca montada como a Oficina monta, com a arte desenhada aqui
	var ref := 300.0
	_testar_peca(_cena_de_codigo(ref, Vector2(10, 40)), ref, Vector2(10, 40), Vector2(310, 40), "peca de codigo")
	# a cena que a Oficina exportou de verdade (o teste Python passa)
	if args.has("--cena"):
		var cena = load(str(args["--cena"]))
		var meta = JSON.parse_string(FileAccess.get_file_as_string(str(args.get("--meta", ""))))
		_checar(cena is PackedScene, "a cena exportada carrega")
		_checar(typeof(meta) == TYPE_DICTIONARY, "os metadados exportados carregam")
		if cena is PackedScene and typeof(meta) == TYPE_DICTIONARY:
			var e: Array = meta["empunhadura"]
			var p: Array = meta["ponta"]
			_testar_peca(cena, float(meta["comprimento_ref"]), Vector2(e[0], e[1]), Vector2(p[0], p[1]), "cena da Oficina")
			print("cena da Oficina: conferida (", args["--cena"], ")")
	_testar_padrao()
	_testar_arma_dupla()
	_testar_sem_script()

	for no in lixo:
		if is_instance_valid(no):
			no.free()
	palco.free()
	print("arma estica: %d checagens, %d falha(s)" % [feitos, falhas.size()])
	quit(0 if falhas.is_empty() else 1)


## A cena da arma como a `painel/sprites/exportar.py` escreve: raiz com o
## peca.gd e o comprimento_ref, a arte num Sprite2D com a empunhadura na origem.
func _cena_de_codigo(ref: float, empunhadura: Vector2) -> PackedScene:
	var img := Image.create(320, 80, false, Image.FORMAT_RGBA8)
	img.fill_rect(Rect2i(10, 30, 300, 20), Color(0.8, 0.8, 0.85))
	var raiz := Node2D.new()
	raiz.name = "EstiloTeste"
	raiz.set_script(load("res://nucleo/peca.gd"))
	raiz.set("comprimento_ref", ref)
	var arte := Sprite2D.new()
	arte.name = "Arte"
	arte.texture = ImageTexture.create_from_image(img)
	arte.centered = false
	arte.offset = -empunhadura
	raiz.add_child(arte)
	arte.owner = raiz
	var cena := PackedScene.new()
	cena.pack(raiz)
	raiz.free()
	return cena


func _amostra(mao: Vector2, ponta: Vector2) -> Dictionary:
	return {"flags": 0, "z": 0.0, "arma_gx": mao.x, "arma_gy": mao.y, "arma_px": ponta.x,
		"arma_py": ponta.y, "arma_ang": 0.0, "golpe_fase": 0, "golpe_p": 0.0}


## O `_arma` do palco de verdade, num quadro, com esta peca no slot p1.
func _quadro(no: Node2D, s: Dictionary) -> void:
	var linha := Line2D.new()
	lixo.append(linha)
	palco.arm = {"p1": no}
	palco.arm_sec = {}          # a segunda lamina do teste da dupla nao vaza para os outros
	palco.rastro = {"p1": linha}
	palco._arma("p1", s, 0.0, false, {"t_jogo": 0.0, "estilo": palco.estilo, "quadro": 0})


func _quadro_dupla(primeira: Node2D, segunda: Node2D, s: Dictionary) -> void:
	var linha := Line2D.new()
	lixo.append(linha)
	palco.arm = {"p1": primeira}
	palco.arm_sec = {"p1": segunda}
	palco.rastro = {"p1": linha}
	palco._arma("p1", s, 0.0, false, {"t_jogo": 0.0, "estilo": palco.estilo, "quadro": 0})


func _perto(a: Vector2, b: Vector2) -> bool:
	return a.distance_to(b) <= TOL


## Ponto da ARTE (px da textura) -> mundo, passando pelo Sprite2D e pela raiz.
func _no_mundo(no: Node2D, ponto_da_arte: Vector2) -> Vector2:
	var arte := no.get_node("Arte") as Sprite2D
	return no.transform * (arte.transform * (ponto_da_arte + arte.offset))


func _testar_peca(cena: PackedScene, ref: float, empunhadura: Vector2, ponta_arte: Vector2, rotulo: String) -> void:
	var no: Node2D = cena.instantiate()
	lixo.append(no)
	_checar(is_equal_approx(float(no.get("comprimento_ref")), ref), "%s: comprimento_ref %s (%s)" % [rotulo, ref, no.get("comprimento_ref")])
	var mao := MAO * PX
	var ponta := PONTA * PX
	var L := mao.distance_to(ponta)
	_quadro(no, _amostra(MAO, PONTA))
	_checar(_perto(no.position, mao), "%s: a origem fica na mao (%s)" % [rotulo, no.position])
	_checar(is_equal_approx(no.scale.x, L / ref) and is_equal_approx(no.scale.y, L / ref),
		"%s: estica %s px -> %s px (escala %s)" % [rotulo, ref, L, no.scale])
	_checar(_perto(no.transform * Vector2(ref, 0), ponta), "%s: +x no comprimento_ref cai na ponta da timeline" % rotulo)
	var e := _no_mundo(no, empunhadura)
	var p := _no_mundo(no, ponta_arte)
	_checar(_perto(e, mao), "%s: a empunhadura da ARTE fica na mao (%s, mao %s)" % [rotulo, e, mao])
	_checar(_perto(p, ponta), "%s: a ponta da ARTE vai a ponta da hitbox (%s, ponta %s)" % [rotulo, p, ponta])
	# o quadro seguinte manda outro comprimento: a peca acompanha, sem estado
	var curta := MAO + Vector2(1.5, 0.0)
	_quadro(no, _amostra(MAO, curta))
	_checar(is_equal_approx(no.scale.x, 150.0 / ref), "%s: o golpe curto (150 px) encolhe a peca (%s)" % [rotulo, no.scale])
	_checar(_perto(_no_mundo(no, ponta_arte), curta * PX), "%s: no golpe curto a ponta da arte segue a da timeline" % rotulo)
	_checar(_perto(_no_mundo(no, empunhadura), mao), "%s: no golpe curto a mao nao sai do lugar" % rotulo)


## A arma padrao (e as filhas, como a corrente) se desenha NO comprimento:
## o palco nao a escala, e ela recebe o comprimento em `_comprimento_px`.
func _testar_padrao() -> void:
	var no: Node2D = load("res://biblioteca/armas/_padrao.tscn").instantiate()
	lixo.append(no)
	no.configurar({"tipo": "Reta", "cor": 0xFFFFFF}, {})
	var s := _amostra(MAO, PONTA)
	_quadro(no, s)
	_checar(no.scale == Vector2.ONE, "padrao: escala 1 (%s)" % no.scale)
	_checar(is_equal_approx(float(s.get("_comprimento_px", 0.0)), 500.0), "padrao: recebe _comprimento_px 500")
	_checar(is_equal_approx(float(no.get("_L")), 500.0), "padrao: desenha com L = 500 (%s)" % no.get("_L"))
	var corrente: Node2D = load("res://biblioteca/armas/tipos/corrente.tscn").instantiate()
	lixo.append(corrente)
	UtilPalco.esticar_arma(corrente, 500.0)
	_checar(corrente.scale == Vector2.ONE, "corrente: nao e esticada por escala")


## A segunda peca de Dupla fica na outra mao, aponta para o lado oposto e
## inverte Y ao apontar para a esquerda: assim a arte nao fica de cabeca para baixo.
func _testar_arma_dupla() -> void:
	var primeira := _cena_de_codigo(100.0, Vector2.ZERO).instantiate()
	var segunda := _cena_de_codigo(100.0, Vector2.ZERO).instantiate()
	lixo.append(primeira)
	lixo.append(segunda)
	var s := _amostra(Vector2(1.0, 0.0), Vector2(3.0, 0.0))
	s["x"] = 0.0
	s["y"] = 0.0
	_quadro_dupla(primeira, segunda, s)
	_checar(_perto(segunda.position, Vector2(-100.0, 0.0)), "dupla: empunhadura espelhada fica na outra mao")
	# a arte tem 100 px e e esticada 2x: a ponta e o ponto LOCAL (100, 0)
	_checar(_perto(segunda.transform * Vector2(100.0, 0.0), Vector2(-300.0, 0.0)), "dupla: ponta espelhada aponta para o outro lado")
	_checar(segunda.scale.y < 0.0, "dupla: lamina que aponta para a esquerda espelha Y")


## Peca SEM script (uma imagem solta): como antes, escala por 100 px.
func _testar_sem_script() -> void:
	var no := Node2D.new()
	lixo.append(no)
	_quadro(no, _amostra(MAO, PONTA))
	_checar(is_equal_approx(no.scale.x, 5.0), "sem script: 100 px viram 500 (escala %s)" % no.scale)
	UtilPalco.esticar_arma(no, 0.0)
	_checar(no.scale.x > 0.0, "comprimento zero nao zera a escala")
