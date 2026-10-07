extends SceneTree
## A ponte do Atelie para o palco: o PNG que o painel grava em
## partes/<grupo>/... (destino do manifesto) entra na cadeia da Biblioteca
## antes da cena do mesmo nivel, e sem PNG a cadeia de hoje continua.
##
##   godot --headless --path palco --script res://testes/partes_palco.gd -- --biblioteca=<pasta>
##
## A <pasta> e uma biblioteca de mentira montada por palco/testes/test_partes_palco.py
## (manifesto + PNGs). Saida 0 = tudo certo.

var falhas := PackedStringArray()
var feitos := 0
var bib: Biblioteca


func _checar(cond: bool, nome: String) -> void:
	feitos += 1
	if not cond:
		falhas.append(nome)
		printerr("FALHOU: ", nome)


func _escolha(chave: String) -> String:
	return str(bib.escolhas.get(chave, ""))


func _instancia(cena: PackedScene) -> Node:
	var no := cena.instantiate()
	root.add_child(no)   # _ready: comprimento_ref / raio_ref
	return no


func _initialize() -> void:
	var pasta := ""
	var trilhas_arquivo := ""
	for a in OS.get_cmdline_user_args():
		if str(a).begins_with("--biblioteca="):
			pasta = str(a).substr(13).replace("\\", "/").rstrip("/") + "/"
		elif str(a).begins_with("--trilhas="):
			trilhas_arquivo = str(a).substr(10)
	_checar(pasta != "", "recebeu --biblioteca")
	bib = Biblioteca.new()
	bib.raiz = pasta

	# --- arma: estilo > tipo; a Corrente fica fora ---
	var garras := _instancia(bib.arma("Dupla", "Garras"))
	_checar(_escolha("armas:Dupla/Garras").ends_with("partes/arma/arma/estilo/garras/base.png"), "garras pelo PNG do estilo: " + _escolha("armas:Dupla/Garras"))
	_checar(garras.get("modo") == "arma", "garras e peca de arma")
	# o .json ao lado do PNG manda na empunhadura e na ponta (100,128 -> 900,128)
	_checar(absf(float(garras.get("comprimento_ref")) - 800.0) < 0.01, "o .json da garras da comprimento 800: %s" % str(garras.get("comprimento_ref")))
	var sai := _instancia(bib.arma("Dupla", "Sai"))
	_checar(_escolha("armas:Dupla/Sai").ends_with("partes/arma/arma/tipo/dupla/base.png"), "sai sem estilo cai no PNG do tipo: " + _escolha("armas:Dupla/Sai"))
	_checar(absf(float(sai.get("comprimento_ref")) - 1024.0) < 0.01, "sem .json o gabarito: mao na borda esquerda, ponta na direita (1024)")
	_checar(sai.get("textura") is Texture2D, "a textura do PNG carregou")
	bib.arma("Corrente", "Mangual")
	_checar(not _escolha("armas:Corrente/Mangual").ends_with(".png"), "a Corrente nao troca a peca de Verlet pelo PNG: " + _escolha("armas:Corrente/Mangual"))
	bib.arma("Reta", "Sabre")
	_checar(_escolha("armas:Reta/Sabre") == "(reserva embutida)", "sem PNG nem cena, a cadeia de hoje: " + _escolha("armas:Reta/Sabre"))

	# --- objeto: skill > elemento > comum ---
	var comum := _instancia(bib.objeto("projetil", "DEFAULT", "Impacto Sônico"))
	_checar(_escolha("efeitos:projetil/DEFAULT/Impacto Sônico").ends_with("partes/skill/projetil/comum/_/base.png"), "projetil sem elemento no PNG comum: " + _escolha("efeitos:projetil/DEFAULT/Impacto Sônico"))
	_checar(comum.get("tingir") == "elemento", "o comum herda tingir=elemento do manifesto")
	_checar(comum.get("girar") == true, "projetil gira com o angulo")
	bib.objeto("projetil", "FOGO", "Bola de Fogo")
	_checar(_escolha("efeitos:projetil/FOGO/Bola de Fogo").ends_with("partes/skill/projetil/elemento/fogo/base.png"), "elemento vence o comum: " + _escolha("efeitos:projetil/FOGO/Bola de Fogo"))
	var area := _instancia(bib.objeto("area", "NATUREZA", "Raízes"))
	_checar(_escolha("efeitos:area/NATUREZA/Raízes").ends_with("partes/skill/area_chao/comum/_/base.png"), "area no chao comum: " + _escolha("efeitos:area/NATUREZA/Raízes"))
	_checar(area.get("girar") == false, "a area nao gira")
	area.configurar({"elemento": "NATUREZA"}, {})
	area.atualizar({"r": 2.0, "ativ": 1}, {"dt_mundo": 1.0 / 30.0})
	_checar(absf(float(area.get("_r")) - 2.0) < 0.001, "o objeto segue o raio da trilha")
	bib.objeto("beam", "FOGO", "Chamas do Dragão")
	_checar(not _escolha("efeitos:beam/FOGO/Chamas do Dragão").ends_with(".png"), "beam fica fora (precisa de codigo para esticar)")
	bib.objeto("projetil_arma", "", "Lirdobrek", "faca")
	_checar(_escolha("efeitos:projetil_arma//Lirdobrek").ends_with("partes/arma/projetil_arma/forma/faca/base.png"), "projetil da arma pela forma: " + _escolha("efeitos:projetil_arma//Lirdobrek"))

	# --- evento: variante > elemento > tier > tipo ---
	var acerto := _instancia(bib.evento("acerto", "heavy", "", "esmagamento"))
	_checar(_escolha("efeitos:evento/acerto/heavy//esmagamento").ends_with("partes/efeito/evento/tipo/acerto/base.png"), "acerto no PNG do tipo: " + _escolha("efeitos:evento/acerto/heavy//esmagamento"))
	_checar(absf(float(acerto.get("tamanho_m")) - 1.9) < 0.001, "acerto pesado estoura maior (1,9 m)")
	bib.evento("acerto", "light", "", "corte")
	_checar(_escolha("efeitos:evento/acerto/light//corte").ends_with("partes/efeito/evento/variante/acerto_corte/base.png"), "variante vence o tipo: " + _escolha("efeitos:evento/acerto/light//corte"))
	bib.evento("skill", "", "GELO", "")
	_checar(_escolha("efeitos:evento/skill//GELO/").ends_with("partes/efeito/conjuracao/comum/_/base.png"), "conjuracao comum para elemento sem PNG: " + _escolha("efeitos:evento/skill//GELO/"))
	bib.evento("parede", "", "", "")
	_checar(not _escolha("efeitos:evento/parede///").ends_with(".png"), "evento sem PNG segue a cadeia de hoje")
	# o evento parado estoura e some sozinho
	var vida := 0
	while is_instance_valid(acerto) and not acerto.is_queued_for_deletion() and vida < 100:
		acerto.atualizar({}, {"dt_mundo": 1.0 / 30.0})
		vida += 1
	_checar(vida > 5 and vida < 20, "o evento vive ~0,35 s (%d quadros)" % vida)

	# --- em volta do lutador ---
	_checar(bib.tem_peca_lutador("estados", "atordoado"), "estado atordoado pelo PNG")
	_checar(bib.tem_peca_lutador("buffs", "Escudo de Brasas"), "buff pelo PNG da skill")
	_checar(not bib.tem_peca_lutador("status", "envenenado"), "status sem PNG continua por codigo")
	var camada := _instancia(bib.peca_lutador("estados", "atordoado"))
	_checar(absf(float(camada.get("raio_ref")) - 256.0) < 0.01, "camada no gabarito do lutador (raio 256)")

	_testar_trilhas_reais(trilhas_arquivo)
	_testar_png_ilegivel()
	_testar_borda_transparente(pasta)
	_testar_ordem_do_comum(pasta)
	_testar_provisoria_da_biblioteca_real()

	for no in root.get_children():
		no.queue_free()
	print("partes do palco: %d checagens, %d falha(s)" % [feitos, falhas.size()])
	quit(0 if falhas.is_empty() else 1)


## configurar com o CABECALHO DE VERDADE da trilha (palco.gd passa `t`
## inteiro: os canais vem juntos, como listas). Antes, `ang` lista dava
## SCRIPT ERROR e a invocacao saia com 57% do tamanho.
func _testar_trilhas_reais(arquivo: String) -> void:
	_checar(arquivo != "" and FileAccess.file_exists(arquivo), "recebeu --trilhas")
	var dados = JSON.parse_string(FileAccess.get_file_as_string(arquivo)) if arquivo != "" else null
	if typeof(dados) != TYPE_DICTIONARY:
		return
	var trilhas: Dictionary = dados["trilhas"]
	var esperado := {"summon": 1.6, "trap": 2.0}
	for tipo in ["projetil", "summon", "orbe", "area", "trap", "projetil_arma"]:
		var t: Dictionary = trilhas[tipo]
		var cena := bib.objeto(tipo, str(t.get("elemento", "")), str(t.get("nome", "")), str(t.get("forma", "")))
		var chave := "efeitos:%s/%s/%s" % [tipo, t.get("elemento", ""), t.get("nome", "")]
		_checar(_escolha(chave).ends_with(".png"), "%s real pelo PNG: %s" % [tipo, _escolha(chave)])
		var no := _instancia(cena)
		no.configurar(t, {})
		var amostra := {}
		for campo in t:
			if typeof(t[campo]) == TYPE_ARRAY and campo != "pontos" and t[campo].size() > 0 and typeof(t[campo][0]) != TYPE_ARRAY:
				amostra[campo] = t[campo][0]
		no.atualizar(amostra, {"dt_mundo": 1.0 / 30.0})
		if esperado.has(tipo):
			_checar(absf(float(no.get("_largura_m")) - float(esperado[tipo])) < 0.001,
				"%s: a largura vem do cabecalho (%s m)" % [tipo, str(no.get("_largura_m"))])
		if amostra.has("r"):
			_checar(absf(float(no.get("_r")) - float(amostra["r"])) < 0.001, "%s: o raio vem da amostra" % tipo)
		if amostra.has("ang") and bool(no.get("girar")):
			_checar(absf(float(no.get("_ang")) - deg_to_rad(float(amostra["ang"]))) < 0.001, "%s: o angulo vem da amostra" % tipo)
	# sem elemento, o comum toma a cor do objeto (o Espirito e lilas, nao branco)
	var espirito := _instancia(bib.objeto("summon", "DEFAULT", "Invocação: Espírito"))
	espirito.configurar(trilhas["summon"], {})
	var cor: Color = espirito.get("_cor")
	_checar(cor != Color.WHITE and cor.b > cor.g, "invocacao sem elemento na cor dela: %s" % str(cor))


## PNG que nao abre: a peca em volta do lutador cai no desenho por codigo
## (antes: marcador magenta), e o arquivo nao e reaberto a cada pedido.
func _testar_png_ilegivel() -> void:
	_checar(not bib.tem_peca_lutador("status", "queimando"), "PNG quebrado nao vira peca (cai no codigo)")
	_checar(bib.pngs_ilegiveis.size() == 1, "o PNG quebrado vai ao relatorio: %s" % str(bib.pngs_ilegiveis.keys()))
	var antes: int = bib._texturas.size()
	bib.tem_peca_lutador("status", "queimando")
	bib.peca_lutador("status", "queimando")
	_checar(bib._texturas.size() == antes, "a falha fica guardada (nao reabre)")
	_checar(not _escolha("lutadores:peca/status/queimando").ends_with(".png"), "peca_lutador tambem pula o PNG quebrado")


## Sem franja escura: o transparente do Atelie e (0,0,0,0) e o filtro puxaria
## esse preto para a borda. A textura vai pre-multiplicada e a peca desenha com
## mistura pre-multiplicada (o GDScript nao alcanca o fix_alpha_border do
## importador). Conferido: a peca tem a mistura, e nos mipmaps nenhum pixel
## tem cor acima do alfa (o que seria a borda escura/clara na mistura).
func _testar_borda_transparente(pasta: String) -> void:
	var tex := bib.textura_png(pasta + "partes/skill/projetil/comum/_/base.png")
	_checar(tex != null, "o PNG comum abre")
	if tex == null:
		return
	var peca := _instancia(bib.objeto("projetil", "", "Sem Elemento"))
	var mat = peca.get("material")
	_checar(mat is CanvasItemMaterial and mat.blend_mode == CanvasItemMaterial.BLEND_MODE_PREMULT_ALPHA,
		"a peca do Atelie desenha com mistura pre-multiplicada")
	var img := tex.get_image()
	_checar(img.has_mipmaps(), "a textura tem mipmaps (a peca aparece reduzida)")
	var dentro := img.get_pixel(256, 256)
	_checar(dentro.is_equal_approx(Color(1, 0, 1, 1)), "o opaco nao muda: %s" % str(dentro))
	# o nivel 2 de mipmap (128 px) mistura a borda do quadrado com o transparente
	var ofs := img.get_mipmap_offset(2)
	var dados := img.get_data()
	var pior := 0.0
	for y in 128:
		for x in 128:
			var k := ofs + (y * 128 + x) * 4
			var a := float(dados[k + 3])
			pior = maxf(pior, maxf(float(dados[k]), float(dados[k + 2])) - a)
	_checar(pior <= 1.0, "nos mipmaps a cor nunca passa do alfa (pre-multiplicada): %s" % str(pior))
	var peca_cor := PecaPng._pre(Color(1, 1, 1, 0.5))
	_checar(peca_cor.is_equal_approx(Color(0.5, 0.5, 0.5, 0.5)), "apagar escurece junto (sem virar brilho somado)")


## A ordem entre o Comum e a cena por elemento (Grimorio builds/comum-tingido-ordem).
func _testar_ordem_do_comum(pasta: String) -> void:
	var casos := {
		"seu-vence": ["objetos/projetil/gelo.tscn", "partes/skill/projetil/comum/_/base.png"],
		"comum-vence": ["partes/skill/projetil/comum/_/base.png", "partes/skill/projetil/comum/_/base.png"],
		"provisoria-fica": ["objetos/projetil/gelo.tscn", "objetos/projetil/trevas.tscn"],
	}
	for ordem in casos:
		var b := Biblioteca.new()
		b.raiz = pasta
		b.ordem_do_comum = ordem
		b.objeto("projetil", "GELO", "Lança de Gelo")
		b.objeto("projetil", "TREVAS", "Necrose")
		var gelo := str(b.escolhas.get("efeitos:projetil/GELO/Lança de Gelo", ""))
		var trevas := str(b.escolhas.get("efeitos:projetil/TREVAS/Necrose", ""))
		_checar(gelo.ends_with(casos[ordem][0]), "%s, arte da Oficina por elemento: %s" % [ordem, gelo])
		_checar(trevas.ends_with(casos[ordem][1]), "%s, cena CC0 por elemento: %s" % [ordem, trevas])
	# o PNG por ELEMENTO do Atelie vence o Comum em qualquer ordem
	for ordem in casos:
		var b := Biblioteca.new()
		b.raiz = pasta
		b.ordem_do_comum = ordem
		b.objeto("projetil", "FOGO", "Bola de Fogo")
		_checar(str(b.escolhas.get("efeitos:projetil/FOGO/Bola de Fogo", "")).ends_with("partes/skill/projetil/elemento/fogo/base.png"),
			"%s: PNG do elemento vence" % ordem)


## Na biblioteca de verdade: so o Fogo da Oficina e arte; as outras 38 sao CC0.
func _testar_provisoria_da_biblioteca_real() -> void:
	var real := Biblioteca.new()
	_checar(Biblioteca.ORDEM_DO_COMUM == "seu-vence", "padrao = a recomendada")
	_checar(not real.eh_provisoria("res://biblioteca/efeitos/objetos/projetil/fogo.tscn"), "o projetil Fogo da Oficina e arte do Adrian")
	_checar(real.eh_provisoria("res://biblioteca/efeitos/objetos/projetil/trevas.tscn"), "o projetil Trevas e CC0 provisorio")
	_checar(real.eh_provisoria("res://biblioteca/efeitos/objetos/area/fogo.tscn"), "a area Fogo e CC0 provisoria")
