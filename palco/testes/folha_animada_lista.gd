extends SceneTree
## A FOLHA ANIMADA com canais em LISTA (07/10/2026): o palco passa ao
## configurar a trilha inteira do objeto (`ang`, `r`... como listas), e o
## float() de uma lista dava SCRIPT ERROR a cada projetil da Oficina (o fogo
## do Adrian). Com `_numero()` a lista vira o padrao e a amostra numerica
## continua valendo.
##
##   godot --headless --path palco --script res://testes/folha_animada_lista.gd
##
## Saida 0 = tudo certo. Quem roda pela suite e palco/testes/test_folha_animada.py.

var falhas := PackedStringArray()


func _checar(cond: bool, nome: String) -> void:
	if not cond:
		falhas.append(nome)
		printerr("FALHOU: ", nome)


func _init() -> void:
	var script = load("res://biblioteca/efeitos/folha_animada.gd")
	var peca = script.new()
	# a trilha como o palco passa: canais em lista
	peca.configurar({"tipo": "projetil", "ang": [10.0, 20.0], "r": [0.3, 0.3], "dir": [1, 2]}, {})
	_checar(is_equal_approx(peca._ang, 0.0), "configurar com ang em lista cai no padrao 0")
	peca.configurar({"tipo": "projetil", "ang": 90.0}, {})
	_checar(is_equal_approx(peca._ang, deg_to_rad(90.0)), "configurar com ang numerico")
	peca.atualizar({"r": [0.5], "ang": [45.0], "prog": [0.1]}, {"dt_mundo": [1]})
	_checar(is_equal_approx(peca._r, 0.0), "amostra com r em lista mantem o r anterior")
	_checar(is_equal_approx(peca._prog, -1.0), "amostra com prog em lista cai no padrao")
	peca.atualizar({"r": 0.5, "ang": 45.0, "prog": 0.25}, {"dt_mundo": 1.0 / 30.0})
	_checar(is_equal_approx(peca._r, 0.5), "amostra numerica: r")
	_checar(is_equal_approx(peca._ang, deg_to_rad(45.0)), "amostra numerica: ang")
	_checar(is_equal_approx(peca._prog, 0.25), "amostra numerica: prog")
	peca.free()
	print("folha_animada_lista: %d falha(s)" % falhas.size())
	quit(1 if falhas.size() > 0 else 0)
