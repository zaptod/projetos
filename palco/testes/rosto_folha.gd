extends SceneTree
## O ROSTO do Atelie pendurado no lutador (GOD-1, auditoria de 11/10/2026).
##
## Uma biblioteca de mentira (folhas geradas aqui, em user://, nada da arte
## do Adrian): `lutador.rosto.boca` com 2 estados (`neutro` e `furia`), cada um
## com `parado`/`expr` (loop, 2 quadros) e `grito`/`golpe_fase` (sem loop, 4
## quadros). O que falhava antes:
##   - com `expr` e `golpe_fase` no MESMO quadro a boca trocava duas vezes e o
##     grito ficava congelado no quadro 0;
##   - o tocador guardava so o ultimo estado: a expressao nunca escolhia o rosto;
##   - o filho pendurado nao recebia `avancar` nem `ajustar_corpo`;
##   - com o lutador marcador (sem gatilho/avancar) o rosto nao recebia nada.
##
##   godot --headless --path palco --script res://testes/rosto_folha.gd
##
## Saida 0 = tudo certo. Quem roda pela suite e palco/testes/test_folha_animada.py.

const Tocador := preload("res://nucleo/tocador_folha.gd")
const Palco := preload("res://nucleo/palco.gd")
const Timeline := preload("res://nucleo/timeline.gd")
const DT := 1.0 / 30.0

var falhas := PackedStringArray()


func _checar(cond: bool, nome: String) -> void:
	if not cond:
		falhas.append(nome)
		printerr("FALHOU: ", nome)


## Folha de `n` quadros quadrados de `lado` px; o lado diferencia as carinhas.
func _folha(pasta: String, n: int, lado: int, loop: bool, gatilho: String) -> String:
	DirAccess.make_dir_recursive_absolute(pasta)
	var img := Image.create_empty(lado * n, lado, false, Image.FORMAT_RGBA8)
	img.fill(Color(1, 1, 1, 1))
	img.save_png(pasta.path_join("folha.png"))
	var quadros := []
	for k in n:
		quadros.append({"x": k * lado, "y": 0, "w": lado, "h": lado})
	var f := FileAccess.open(pasta.path_join("animacao.json"), FileAccess.WRITE)
	f.store_string(JSON.stringify({"quadros": quadros, "fps": 30, "loop": loop, "gatilho": gatilho}))
	f.close()
	return pasta


func _boca(raiz: String) -> Node2D:
	var estados := []
	var lado := {"neutro": 8, "furia": 16}
	for nome in ["neutro", "furia"]:
		estados.append({"id": nome, "animacoes": [
			{"id": "parado", "gatilho": "expr", "loop": true,
				"pasta": _folha(raiz.path_join(nome + "/parado"), 2, lado[nome], true, "expr")},
			{"id": "grito", "gatilho": "golpe_fase", "loop": false,
				"pasta": _folha(raiz.path_join(nome + "/grito"), 4, lado[nome], false, "golpe_fase")},
		]})
	var boca: Node2D = Tocador.new()
	boca.catalogo_peca = {"id": "lutador.rosto.boca", "estados": estados}
	boca._preparar_catalogo()
	return boca


func _corpo(raiz: String) -> Node2D:
	var corpo: Node2D = Tocador.new()
	corpo.catalogo_peca = {"id": "lutador.corpo", "estados": [{"id": "parado", "animacoes": [
		{"id": "parado", "gatilho": "ocioso", "loop": true,
			"pasta": _folha(raiz.path_join("corpo/parado"), 2, 32, true, "ocioso")}]}]}
	corpo._preparar_catalogo()
	return corpo


func _init() -> void:
	var raiz := ProjectSettings.globalize_path("user://rosto_folha_teste")

	# --- o rosto comeca no 1o estado, nao no ultimo
	var boca := _boca(raiz)
	_checar(boca.estado_atual == "neutro", "comeca no neutro (1o estado), e nao no ultimo")
	_checar(boca.gatilho_animacao == "expr" and int(boca.textura.get_size().y) == 8,
		"repousa no parado do neutro")

	# --- o golpe pelo pai TocadorFolha: um gatilho por quadro, como o palco manda
	var corpo := _corpo(raiz)
	corpo.add_child(boca)
	var indices := []
	var gatilhos := []
	for k in 3:
		corpo.estado("furia")
		corpo.gatilho("golpe_fase")
		corpo.ajustar_corpo(170.0)
		corpo.avancar(DT)
		indices.append(boca.indice)
		gatilhos.append(boca.gatilho_animacao)
	_checar(indices == [1, 2, 3], "o grito anda 1 -> 2 -> 3 (antes congelava no 0): %s" % str(indices))
	_checar(gatilhos == ["golpe_fase", "golpe_fase", "golpe_fase"], "a boca toca o grito: %s" % str(gatilhos))
	_checar(boca.estado_atual == "furia", "a expressao escolhe o estado: %s" % boca.estado_atual)
	_checar(int(boca.textura.get_size().y) == 16, "a folha do grito e a da furia")
	_checar(is_equal_approx(boca.corpo_px, 170.0), "o filho cresce com o corpo: corpo_px %s" % boca.corpo_px)
	# 4o quadro: o grito (sem loop) acaba e a boca volta ao repouso da furia
	corpo.gatilho("expr")
	corpo.avancar(DT)
	_checar(boca.gatilho_animacao == "expr" and int(boca.textura.get_size().y) == 16,
		"fim do grito: repouso na furia")

	# --- trocar a carinha no meio do grito nao volta o grito ao comeco
	corpo.gatilho("golpe_fase")
	corpo.avancar(DT)
	corpo.avancar(DT)
	var antes: int = boca.indice
	corpo.estado("neutro")
	_checar(boca.gatilho_animacao == "golpe_fase" and boca.indice == antes and int(boca.textura.get_size().y) == 8,
		"troca de carinha no grito: mesma posicao (%d), folha do neutro" % boca.indice)

	# --- carinha que falta: a da familia, depois a neutra (boca-de-uma-carinha)
	corpo.estado("berserk")      # familia furia
	_checar(boca.estado_atual == "furia", "berserk sem desenho usa a furia (familia): %s" % boca.estado_atual)
	corpo.estado("tristeza")     # familia dor: nao ha; cai na neutra
	_checar(boca.estado_atual == "neutro", "tristeza sem familia desenhada usa a neutra: %s" % boca.estado_atual)
	_checar(boca.herdado == {"berserk": "furia", "tristeza": "neutro"},
		"o que falta desenhar fica anotado para o relatorio: %s" % str(boca.herdado))
	corpo.free()

	# --- o lutador marcador (sem gatilho/avancar): o palco repassa direto ao rosto
	var marcador := Node2D.new()
	marcador.scale = Vector2(0.5, 0.5)
	var boca2 := _boca(raiz)
	marcador.add_child(boca2)
	var palco = Palco.new()
	palco.tl = Timeline.new()
	palco.tl.dados = {"tabelas": {"expressoes": ["neutro", "focado", "glacial", "determinado", "furia"]}}
	_checar(palco._nome_expr({"expr": 4}) == "furia", "o indice expr vira o nome da expressao")
	_checar(palco._nome_expr({"expr": 99}) == "", "indice fora da tabela nao quebra")
	palco._repassar(marcador, "estado", [palco._nome_expr({"expr": 4})])
	palco._repassar(marcador, "gatilho", ["golpe_fase"])
	palco._repassar(marcador, "ajustar_corpo", [170.0], marcador.scale.x)
	palco._repassar(marcador, "avancar", [DT])
	_checar(boca2.estado_atual == "furia" and boca2.gatilho_animacao == "golpe_fase" and boca2.indice == 1,
		"marcador: o rosto recebe estado, gatilho e avancar (%s %s %d)" % [boca2.estado_atual, boca2.gatilho_animacao, boca2.indice])
	_checar(is_equal_approx(boca2.corpo_px, 340.0), "marcador com escala 0,5: o tamanho desconta a escala do pai (%s)" % boca2.corpo_px)
	marcador.free()
	palco.free()

	print("rosto_folha: %d falha(s)" % falhas.size())
	quit(1 if falhas.size() > 0 else 0)
