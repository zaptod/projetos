extends SceneTree
## Paridade Python x Godot da corrente nova (timeline revisao 4), sem janela:
##
##   godot --headless --path palco --script res://ferramentas/paridade_corrente.gd -- \
##       --timeline=T.gcpf --saida=R.json --passos=0,10.5,123.25
##
## Para cada lutador com `arma.corrente`, em cada passo pedido, escreve o que
## o PALCO leu: os canais da bola pela amostragem do Timeline (interpolada),
## a mao e a bola que a peca da corrente usa e a corrente que ela desenharia
## (os pontos, em metros). O teste em Python
## (random_builds/tests/test_palco_corrente_regressions.py) refaz as mesmas
## contas a partir do mesmo arquivo e compara. Saida 0 = escreveu; 2 = nao leu.

func _initialize() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and "=" in a:
			args[a.substr(2, a.find("=") - 2)] = a.substr(a.find("=") + 1)
	var tl := Timeline.carregar(str(args.get("timeline", "")))
	if tl == null:
		printerr("paridade: ", Timeline.ultimo_erro)
		quit(2)
		return
	var passos: Array = []
	for txt in str(args.get("passos", "0")).split(","):
		passos.append(float(txt))
	var cena: PackedScene = load("res://biblioteca/armas/tipos/corrente.tscn")
	var saida := {"revisao": tl.revisao(), "erros": tl.validar(), "lutadores": {}}
	for slot in ["p1", "p2"]:
		var corr := tl.corrente_do(slot)
		if corr.is_empty():
			continue
		var c := tl.cabecalho_lutador(slot)
		var dados: Dictionary = c["arma"].duplicate(true)
		dados["slot"] = slot
		dados["raio_corpo"] = c.get("raio_corpo", 0.85)
		var no = cena.instantiate()
		no.configurar(dados, {})
		var amostras := []
		var t0 := Time.get_ticks_usec()
		for p in passos:
			var s := tl.lutador(slot, p)
			no.atualizar(s, {"timeline": tl, "passo": p})
			var k := clampi(int(floor(p)), 0, tl.n - 1)
			var mao: Vector2 = no._mao(k) / UtilPalco.PX_POR_M
			var bola: Vector2 = no._bola(k, no._mao(k)) / UtilPalco.PX_POR_M
			var pontos := []
			for q in no._pontos:
				pontos.append([q.x / UtilPalco.PX_POR_M, q.y / UtilPalco.PX_POR_M])
			amostras.append({"p": p, "bola_x": s.get("bola_x"), "bola_y": s.get("bola_y"),
				"bola_vx": s.get("bola_vx"), "bola_vy": s.get("bola_vy"),
				"mao_k": [mao.x, mao.y], "bola_k": [bola.x, bola.y], "inicio": no._inicio(k),
				"ativo": no._ativo, "pontos": pontos})
		var us := Time.get_ticks_usec() - t0
		no.free()
		saida["lutadores"][slot] = {"corrente": corr, "amostras": amostras,
			"us_por_quadro": us / maxf(1.0, float(passos.size()))}
	var f := FileAccess.open(str(args.get("saida", "user://paridade.json")), FileAccess.WRITE)
	f.store_string(JSON.stringify(saida, "", true, true))
	f.close()
	print("paridade: %d passo(s), %d lutador(es) com corrente" % [passos.size(), saida["lutadores"].size()])
	quit(0)
