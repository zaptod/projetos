extends SceneTree
## Validacao HEADLESS de uma timeline (sem janela, sem GPU):
##
##   godot --headless --path palco --script res://ferramentas/validar.gd -- --timeline=T.json [--saida=R.json]
##
## Confere o schema (Timeline.validar) e resolve TODAS as pecas que a luta
## pede na biblioteca (lutadores, armas, objetos, eventos, arena), dizendo
## qual arquivo vai entrar e quais cairam na reserva.
## Saida: 0 = valida; 1 = invalida; 2 = nao consegui ler.

func _initialize() -> void:
	var args := {}
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--") and "=" in a:
			args[a.substr(2, a.find("=") - 2)] = a.substr(a.find("=") + 1)
	var caminho := str(args.get("timeline", "res://exemplos/exemplo.timeline.json"))
	var tl := Timeline.carregar(caminho)
	if tl == null:
		printerr("validar: ", Timeline.ultimo_erro)
		_gravar(args, {"ok": false, "erros": [Timeline.ultimo_erro], "legivel": false})
		quit(2)
		return
	var erros := tl.validar()
	var bib := Biblioteca.new()
	if erros.is_empty():
		var arena = tl.dados.get("arena")
		if typeof(arena) == TYPE_DICTIONARY:
			bib.arena(str(arena.get("nome", "")), str(arena.get("tema", "")))
		for slot in ["p1", "p2"]:
			var c := tl.cabecalho_lutador(slot)
			bib.lutador(str(c.get("nome", "")), str(c.get("classe", "")))
			var arma = c.get("arma")
			if typeof(arma) == TYPE_DICTIONARY:
				bib.arma(str(arma.get("tipo", "")), str(arma.get("estilo", "")))
		for o in tl.trilhas().get("objetos", []):
			bib.objeto(str(o.get("tipo", "")), str(o.get("elemento", "")), str(o.get("nome", "")))
		# so o que vira efeito na tela pede peca (texto, movimento e
		# projetil_fim da revisao 3 sao da edicao: nao caem no _padrao)
		for ev in tl.dados.get("eventos", []):
			if Timeline.EVENTOS_COM_VFX.has(str(ev.get("tipo", ""))):
				bib.evento(str(ev.get("tipo", "")), str(ev.get("tier", "")))
	for e in erros:
		printerr("validar: ", e)
	# o plano de quadros que o render faria, com o hitstop do ESTILO GLOBAL:
	# quanto o video fica mais longo que a luta, sem abrir janela
	var quadros := -1
	var parados := -1
	if erros.is_empty():
		var carregado = load("res://biblioteca/estilo.tres") if ResourceLoader.exists("res://biblioteca/estilo.tres") else null
		var estilo: EstiloPalco = carregado if carregado is EstiloPalco else EstiloPalco.new()
		var plano := PlanoQuadros.montar(tl.duracao(), tl.dados.get("remapeamento"), 30)
		var paradas := []
		for ev in tl.dados.get("eventos", []):
			if ev.get("tipo") == "acerto":
				var seg := estilo.hitstop_do_acerto(ev)
				if seg > 0.0:
					paradas.append([float(ev["i"]) / tl.hz, seg])
		var sem := plano.total()
		if not paradas.is_empty():
			plano.com_hitstop(paradas)
		quadros = plano.total()
		parados = quadros - sem
	var por_tipo := {}
	if typeof(tl.dados.get("eventos")) == TYPE_ARRAY:
		for ev in tl.dados["eventos"]:
			if typeof(ev) == TYPE_DICTIONARY:
				var t := str(ev.get("tipo", ""))
				por_tipo[t] = int(por_tipo.get(t, 0)) + 1
	var resumo := {
		"ok": erros.is_empty(), "legivel": true, "erros": erros, "timeline": caminho,
		"revisao": tl.revisao(), "eventos_por_tipo": por_tipo,
		"passos": tl.n, "hz": tl.hz, "duracao": tl.duracao(),
		"eventos": tl.dados.get("eventos", []).size() if typeof(tl.dados.get("eventos")) == TYPE_ARRAY else -1,
		"sons": (tl.dados["sons"].get("itens", []).size() if typeof(tl.dados.get("sons")) == TYPE_DICTIONARY else 0),
		"pecas": bib.escolhas, "reservas": bib.reservas.keys(),
		"quadros": quadros, "quadros_de_hitstop": parados,
	}
	_gravar(args, resumo)
	print("validar: %s -> %s (%d passos, %d erro(s), %d peca(s) resolvidas)" % [
		caminho, "OK" if erros.is_empty() else "FALHOU", tl.n, erros.size(), bib.escolhas.size()])
	quit(0 if erros.is_empty() else 1)


func _gravar(args: Dictionary, d: Dictionary) -> void:
	if not args.has("saida"):
		return
	var f := FileAccess.open(str(args["saida"]), FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(d, "  "))
