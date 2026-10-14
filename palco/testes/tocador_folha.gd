extends SceneTree
## O tocador de folha do Atelie e a traducao de gatilhos.
##
##   godot --headless --path palco --script res://testes/tocador_folha.gd
##
## Saida 0 = tudo certo ("0 falha(s)"). Quem roda pela suite e
## palco/testes/test_folha_animada.py (e random_builds/builds/palco/prova_e3.py).

const Tocador := preload("res://nucleo/tocador_folha.gd")
const Gatilhos := preload("res://nucleo/gatilhos_animacao.gd")
const DT := 1.0 / 30.0

var falhas := PackedStringArray()


func _checar(cond: bool, nome: String) -> void:
	if not cond:
		falhas.append(nome)
		printerr("FALHOU: ", nome)


func _folha(pasta: String, n: int, loop: bool, gatilho: String) -> String:
	DirAccess.make_dir_recursive_absolute(pasta)
	var img := Image.create_empty(8 * n, 8, false, Image.FORMAT_RGBA8)
	img.fill(Color(1, 1, 1, 1))
	img.save_png(pasta.path_join("folha.png"))
	var quadros := []
	for k in n:
		quadros.append({"x": k * 8, "y": 0, "w": 8, "h": 8})
	var f := FileAccess.open(pasta.path_join("animacao.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"quadros": quadros, "fps": 30, "loop": loop, "gatilho": gatilho}))
	f.close()
	return pasta


func _init() -> void:
	var tocador: Node2D = Tocador.new()
	_checar(tocador.gatilho_animacao == "", "tocador novo sem gatilho")
	tocador.free()
	_checar(Gatilhos.da_timeline({"tipo": "acerto"}) == "acerto", "acerto")
	_checar(Gatilhos.da_timeline({"tipo": "ko"}) == "ko", "ko")
	_checar(Gatilhos.da_timeline({}, {"golpe_fase": 2}) == "golpe_fase", "golpe_fase da amostra")
	_checar(Gatilhos.reconhece("ocioso"), "reconhece ocioso")

	# GOD-3: a animacao de EVENTO da arma toca ate o fim. O palco manda
	# `ocioso`/`golpe_fase` a arma em TODO quadro; antes o `projetil_fim` virava
	# `ocioso` no quadro seguinte e durava 1 quadro de video.
	var raiz := ProjectSettings.globalize_path("user://tocador_folha_teste")
	var arma: Node2D = Tocador.new()
	arma.catalogo_peca = {"id": "arma.estilo.teste", "estados": [
		{"id": "parada", "animacoes": [{"id": "parada", "gatilho": "ocioso", "loop": true,
			"pasta": _folha(raiz.path_join("parada"), 2, true, "ocioso")}]},
		{"id": "golpe", "animacoes": [{"id": "golpe", "gatilho": "golpe_fase", "loop": false,
			"pasta": _folha(raiz.path_join("golpe"), 3, false, "golpe_fase")}]},
		{"id": "fim", "animacoes": [{"id": "fim", "gatilho": "projetil_fim", "loop": false,
			"pasta": _folha(raiz.path_join("fim"), 4, false, "projetil_fim")}]},
	]}
	arma._preparar_catalogo()
	_checar(arma.gatilho_animacao == "ocioso", "repousa no ocioso")
	arma.gatilho("projetil_fim")
	var vistos := []
	for k in 5:
		arma.gatilho("ocioso" if k % 2 == 0 else "golpe_fase")   # como o _arma do palco
		arma.avancar(DT)
		vistos.append("%s:%d" % [arma.gatilho_animacao, arma.indice])
	_checar(vistos.slice(0, 3) == ["projetil_fim:1", "projetil_fim:2", "projetil_fim:3"],
		"o projetil_fim toca os 4 quadros: %s" % str(vistos))
	_checar(str(vistos[3]).begins_with("ocioso"), "acabou: volta ao ocioso (%s)" % str(vistos))
	# destravado: o quadro volta a mandar
	arma.gatilho("golpe_fase")
	_checar(arma.gatilho_animacao == "golpe_fase", "depois do evento o golpe_fase volta a valer")
	# um evento novo corta o anterior (so os gatilhos de quadro esperam)
	arma.gatilho("projetil_fim")
	arma.avancar(DT)
	arma.gatilho("ocioso")
	_checar(arma.gatilho_animacao == "projetil_fim", "evento novo trava de novo")
	# evento que a peca nao tem nao trava nada
	arma.gatilho("arma_puxada")
	arma.avancar(DT)
	arma.avancar(DT)
	arma.avancar(DT)
	arma.gatilho("ocioso")
	_checar(arma.gatilho_animacao == "ocioso", "fim do evento destrava")
	arma.free()

	print("tocador_folha: %d falha(s)" % falhas.size())
	quit(1 if falhas.size() > 0 else 0)
