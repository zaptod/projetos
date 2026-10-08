class_name Biblioteca
extends RefCounted
## Descoberta de pecas pelo NOME DO ARQUIVO, sem catalogo para editar.
##
## Cada pedido tem uma lista de candidatos, do mais especifico ao mais geral,
## e o primeiro arquivo que existir vence. O ultimo candidato e sempre um
## `_padrao`; se nem ele existir (alguem apagou), entra a reserva embutida
## (`nucleo/peca_reserva.gd`), que desenha um marcador: nada some da tela.
##
##   armas    estilos/<estilo> > tipos/<tipo> > _padrao
##   lutador  nomes/<nome> > classes/<classe> > classes/<classe sem parenteses> > _padrao
##   objeto   skills/<skill> > <tipo>/<elemento> > <tipo>/_padrao > _padrao
##   evento   eventos/<tipo>_<variante> > eventos/<tipo>_<elemento> >
##            eventos/<tipo>_<tier> > eventos/<tipo> > eventos/_padrao
##   peca de lutador  lutadores/<categoria>/<nome> > <categoria>/_padrao
##   arena    <nome> > temas/<tema> > _padrao
##   hud      _padrao
##   som      sons/<id>.wav|.ogg|.mp3 (so sobrepoe a biblioteca do jogo)
##
## Os nomes passam por UtilPalco.slug: "Mágica" procura "magica.tscn".
##
## O PNG do ATELIE (palco/biblioteca/partes/<grupo>/..., no destino que o
## manifesto `manifesto_slots.json` da a cada lugar) entra na MESMA cadeia,
## logo antes da cena do mesmo nivel: o mais especifico vence, e no mesmo
## nivel o desenho do Atelie vence a cena antiga. Sem PNG, a cadeia de hoje.
## Um candidato que comeca com "png:" e o id de um slot do manifesto:
##   armas    png:estilo > estilos/<estilo> > png:tipo > tipos/<tipo> > _padrao
##            (a Corrente fica fora: a peca dela e a de Verlet, F4 a parte)
##   objeto   png:skill > skills/<skill> > png:elemento > [Comum x cena por
##            elemento: ORDEM_DO_COMUM] > <tipo>/_padrao > _padrao
##            (beam e portal ficam fora: precisam de codigo para esticar/ligar a e b)
##   evento   png:variante > <tipo>_<variante> > png:elemento > ... > png:tipo > <tipo> > _padrao
##   em volta do lutador (estados, status, buffs, canais, transformacoes)
##            png > lutadores/<categoria>/<nome> > <categoria>/_padrao

const RAIZ := "res://biblioteca/"
const EXTENSOES := [".tscn", ".scn"]
const EXT_SOM := [".wav", ".ogg", ".mp3"]
const RESERVA := "res://nucleo/peca_reserva.gd"
const PECA_PNG := "res://nucleo/peca_png.gd"
const TOCADOR_FOLHA := "res://nucleo/tocador_folha.gd"
const PREFIXO_PNG := "png:"
## candidato de cena que so vale se NAO for arte provisoria (CC0)
const PREFIXO_ARTE := "arte:"
## Cena provisoria = cena cujo script raiz e um destes (as 38 cenas CC0 por
## elemento de 28/09 usam o objeto_cc0.gd; a arte da Oficina usa folha_animada).
const SCRIPTS_PROVISORIOS := ["res://biblioteca/efeitos/objetos/objeto_cc0.gd"]
## Quem ganha quando ha o Comum do Atelie (tingido) E uma cena por elemento
## (Grimorio builds/comum-tingido-ordem):
##   "seu-vence"       (padrao, a recomendada) a arte do Adrian por elemento
##                     (PNG do Atelie ou cena da Oficina, ex. projetil/fogo)
##                     vence o Comum; o Comum vence so a provisoria (CC0)
##   "comum-vence"     o Comum vence qualquer cena por elemento
##   "provisoria-fica" o Comum so onde nao ha cena nenhuma
## O PNG por ELEMENTO do Atelie vence o Comum nas tres.
const ORDEM_DO_COMUM := "seu-vence"

## objeto da timeline -> parte do manifesto (grupo skill). Beam e portal nao
## tem peca de um PNG so (o feixe estica de a ate b; o portal liga a e b).
const PARTE_DO_OBJETO := {"projetil": "projetil", "area": "area_chao", "summon": "invocacao", "trap": "estrutura"}
## objetos que NAO giram com o angulo (o chao da area, a estrutura da trap)
const OBJETO_PARADO := {"area": true, "trap": true}
## evento -> parte do manifesto no grupo efeito que fala do ELEMENTO
const EVENTO_POR_ELEMENTO := {"skill": "conjuracao", "explosao": "impacto"}
## tamanho (m) do estouro de um evento parado (o KO e maior)
const TAMANHO_EVENTO := {"ko": 4.0, "acerto_light": 1.2, "acerto_medium": 1.5, "acerto_heavy": 1.9, "acerto_colossal": 2.4}
## categoria de peca do lutador -> (parte, nivel) da camada_estado no manifesto
const CAMADA := {"estados": ["estado", "comum"], "status": ["status", "comum"], "buffs": ["buffs", "skill"],
	"canais": ["canais", "skill"], "transformacoes": ["transformacoes", "skill"]}

var raiz := RAIZ          # os testes apontam para uma biblioteca de mentira
var _cache := {}          # caminho -> PackedScene
var escolhas := {}        # "categoria:pedido" -> caminho escolhido (relatorio)
var reservas := {}        # pedidos que cairam no _padrao ou na reserva embutida
var _destinos := {}       # id do slot -> caminho do PNG (pelo manifesto)
var _tingir_do_png := {}  # caminho do PNG -> `tingir` do slot no manifesto
var _manifesto_de := ""   # a raiz cujo manifesto esta em _destinos
var _texturas := {}       # caminho do PNG -> ImageTexture, ou null (nao abriu: nao tenta de novo)
var pngs_ilegiveis := {}  # caminho -> true (o relatorio diz)
var _provisoria := {}     # caminho da cena -> e arte provisoria (CC0)?
var ordem_do_comum := ORDEM_DO_COMUM   # os testes trocam
var _catalogo := {}                    # id -> peca, lido uma vez por raiz
var _catalogo_de := ""


## O catalogo e a autoridade dos ids do Atelie. `catalogo_ajustes` pode
## esconder/criar itens; por enquanto so preservamos os itens visiveis.
func _carregar_catalogo() -> void:
	if _catalogo_de == raiz:
		return
	_catalogo_de = raiz
	_catalogo.clear()
	var arquivo := raiz + "catalogo_animacoes.json"
	if not FileAccess.file_exists(arquivo):
		return
	var dados = JSON.parse_string(FileAccess.get_file_as_string(arquivo))
	if typeof(dados) != TYPE_DICTIONARY:
		return
	var ajustes = null
	if FileAccess.file_exists(raiz + "catalogo_ajustes.json"):
		ajustes = JSON.parse_string(FileAccess.get_file_as_string(raiz + "catalogo_ajustes.json"))
	var escondidas: Array = ajustes.get("escondidas", []) if typeof(ajustes) == TYPE_DICTIONARY else []
	for peca in dados.get("pecas", []):
		if typeof(peca) == TYPE_DICTIONARY and not str(peca.get("id", "")) in escondidas:
			_catalogo[str(peca["id"])] = peca


## A primeira peca da lista que JA tem folha do Adrian vence; sem nenhuma,
## a primeira que existe no catalogo (o chamador cai no marcador neutro).
func resolver_peca(ids: Array) -> Dictionary:
	_carregar_catalogo()
	var primeira := {}
	for id in ids:
		if _catalogo.has(str(id)):
			var peca: Dictionary = _catalogo[str(id)]
			if _tem_folha_catalogo(peca):
				return peca.duplicate(true)
			if primeira.is_empty():
				primeira = peca
	return primeira.duplicate(true)


## Cena do catalogo apenas quando a cadeia encontrou uma folha do Atelie.
## `null` deixa o chamador conservar o marcador/efeito que ja existia.
func cena_catalogada(ids: Array) -> PackedScene:
	var peca := resolver_peca(ids)
	return _cena_catalogo(peca) if not peca.is_empty() and _tem_folha_catalogo(peca) else null


func tem_folha_catalogada(ids: Array) -> bool:
	var peca := resolver_peca(ids)
	return not peca.is_empty() and _tem_folha_catalogo(peca)


func tem_folha_evento(tipo: String, elemento := "", skill := "", tipo_skill := "") -> bool:
	return tem_folha_catalogada(["skill." + UtilPalco.slug(skill), "skill.tipo." + UtilPalco.slug(tipo_skill),
		"evento." + UtilPalco.slug(tipo), "efeito." + UtilPalco.slug(tipo),
		"elemento." + UtilPalco.slug(elemento), "efeito.generico"])


func _pasta_catalogo(peca: Dictionary, estado: String, animacao: String) -> String:
	_carregar_catalogo()
	var cadeia: Array = [str(peca.get("id", ""))] + Array(peca.get("heranca", []))
	for id in cadeia:
		var pasta := raiz + "animacoes/" + str(id) + "/" + estado + "/" + animacao
		if FileAccess.file_exists(pasta.path_join("folha.png")) and FileAccess.file_exists(pasta.path_join("animacao.json")):
			return pasta
	return ""


func _cena_catalogo(peca: Dictionary) -> PackedScene:
	var no := Node2D.new()
	no.name = "TocadorFolha"
	no.set_script(load(TOCADOR_FOLHA))
	var configuracao := peca.duplicate(true)
	for estado in configuracao.get("estados", []):
		for animacao in estado.get("animacoes", []):
			animacao["pasta"] = _pasta_catalogo(peca, str(estado.get("id", "")), str(animacao.get("id", "")))
	no.set("catalogo_peca", configuracao)
	var cena := PackedScene.new()
	cena.pack(no)
	no.free()
	return cena


func _tem_folha_catalogo(peca: Dictionary) -> bool:
	for estado in peca.get("estados", []):
		for animacao in estado.get("animacoes", []):
			if _pasta_catalogo(peca, str(estado.get("id", "")), str(animacao.get("id", ""))) != "":
				return true
	return false


## Le o manifesto da biblioteca uma vez (por raiz): id do slot -> caminho do
## PNG. O manifesto e a autoridade do destino, como no painel que grava.
func _carregar_destinos() -> void:
	if _manifesto_de == raiz:
		return
	_manifesto_de = raiz
	_destinos.clear()
	_tingir_do_png.clear()
	var arquivo := raiz + "manifesto_slots.json"
	if not FileAccess.file_exists(arquivo):
		return
	var json := JSON.new()
	if json.parse(FileAccess.get_file_as_string(arquivo)) != OK or typeof(json.data) != TYPE_DICTIONARY:
		return
	for slot in json.data.get("slots", []):
		if typeof(slot) != TYPE_DICTIONARY or str(slot.get("grupo", "")) == "lutador":
			continue
		var destino := str(slot.get("destino", "")).replace("\\", "/")
		if destino.begins_with("palco/biblioteca/"):
			var caminho := raiz + destino.trim_prefix("palco/biblioteca/")
			_destinos[str(slot.get("id", ""))] = caminho
			_tingir_do_png[caminho] = str(slot.get("tingir", "nenhum"))


## O caminho do PNG do slot `id`, ou "" (slot fora do manifesto, sem
## desenho, ou PNG que nao abre: a cadeia segue para o desenho de hoje).
func png_do_slot(id_slot: String) -> String:
	_carregar_destinos()
	var caminho := str(_destinos.get(id_slot, ""))
	if caminho == "" or not FileAccess.file_exists(caminho):
		return ""
	return caminho if textura_png(caminho) != null else ""


## A textura do PNG do Atelie, lida UMA vez (a falha tambem fica guardada:
## um PNG quebrado nao e reaberto a cada evento). O transparente do Atelie e
## (0,0,0,0) e o filtro (e os mipmaps) puxariam esse preto para a borda:
## franja escura. O importador do Godot resolve com `fix_alpha_border`, que o
## GDScript nao alcanca (Image nao expoe); aqui a textura vai PRE-MULTIPLICADA
## e a peca desenha com mistura pre-multiplicada (peca_png.gd), o que da a
## mesma borda limpa, inclusive nos mipmaps.
func textura_png(caminho: String) -> Texture2D:
	if _texturas.has(caminho):
		return _texturas[caminho]
	var tex: Texture2D = null
	var imagem := Image.load_from_file(ProjectSettings.globalize_path(caminho))
	if imagem != null and not imagem.is_empty():
		if imagem.get_format() != Image.FORMAT_RGBA8:
			imagem.convert(Image.FORMAT_RGBA8)
		imagem.premultiply_alpha()
		imagem.generate_mipmaps()
		tex = ImageTexture.create_from_image(imagem)
	else:
		pngs_ilegiveis[caminho] = true
		push_warning("[palco] PNG do Atelie nao abre, segue o desenho de hoje: " + caminho)
	_texturas[caminho] = tex
	return tex


## A cena e arte provisoria (CC0)? Pelo script raiz, sem instanciar.
func eh_provisoria(caminho: String) -> bool:
	if _provisoria.has(caminho):
		return _provisoria[caminho]
	var provisoria := false
	var cena = load(caminho) if ResourceLoader.exists(caminho) else null
	if cena is PackedScene:
		var estado: SceneState = cena.get_state()
		for k in estado.get_node_property_count(0):
			if estado.get_node_property_name(0, k) == "script":
				var script = estado.get_node_property_value(0, k)
				provisoria = script is Script and SCRIPTS_PROVISORIOS.has(script.resource_path)
	_provisoria[caminho] = provisoria
	return provisoria


static func _id_slot(grupo: String, parte: String, nivel: String, chave: String, estado := "base") -> String:
	return PREFIXO_PNG + "%s/%s/%s/%s/%s" % [grupo, parte, nivel, chave, estado]


func _achar(categoria: String, candidatos: Array) -> String:
	for rel in candidatos:
		if str(rel).is_empty():
			continue
		if str(rel).begins_with(PREFIXO_PNG):
			var png := png_do_slot(str(rel).trim_prefix(PREFIXO_PNG))
			if png != "":
				return png
			continue
		var so_arte := str(rel).begins_with(PREFIXO_ARTE)
		var nome := str(rel).trim_prefix(PREFIXO_ARTE)
		for ext in EXTENSOES:
			var caminho: String = raiz + categoria + "/" + nome + str(ext)
			if ResourceLoader.exists(caminho) and not (so_arte and eh_provisoria(caminho)):
				return caminho
	return ""


## A ordem entre o Comum do Atelie e a cena por elemento (ORDEM_DO_COMUM).
static func ordem_comum_e_elemento(ordem: String, png_comum: String, cena_elemento: String) -> Array:
	if cena_elemento == "":
		return [png_comum]
	match ordem:
		"comum-vence":
			return [png_comum, cena_elemento]
		"provisoria-fica":
			return [cena_elemento, png_comum]
		_:
			return [PREFIXO_ARTE + cena_elemento, png_comum, cena_elemento]


## O .json que o painel grava ao lado do PNG; {} quando nao ha (nunca exigido).
static func opcoes_do_png(caminho_png: String) -> Dictionary:
	var caminho_json := caminho_png.get_basename() + ".json"
	if not FileAccess.file_exists(caminho_json):
		return {}
	var json := JSON.new()
	if json.parse(FileAccess.get_file_as_string(caminho_json)) != OK or typeof(json.data) != TYPE_DICTIONARY:
		return {}
	return json.data


static func _vetor(valor, padrao: Vector2) -> Vector2:
	if typeof(valor) == TYPE_ARRAY and valor.size() >= 2:
		return Vector2(float(valor[0]), float(valor[1]))
	return padrao


## A peca de UM PNG (nucleo/peca_png.gd), empacotada na hora. `ajustes` sao
## os campos da peca para o lugar dela (modo, girar, tamanho...); o .json do
## painel, se existir, sobrepoe tingir e a geometria.
func _cena_png(caminho: String, ajustes: Dictionary) -> PackedScene:
	var textura := textura_png(caminho)
	if textura == null:
		return null
	var no := Node2D.new()
	no.name = "PecaPng"
	no.set_script(load(PECA_PNG))
	no.set("textura", textura)
	no.set("origem_png", caminho)
	for campo in ajustes:
		no.set(campo, ajustes[campo])
	# tingir: o .json do painel, senao o do slot no manifesto ("elemento" no
	# comum de skill e efeito: a mesma arte serve aos 12 elementos)
	var extra := opcoes_do_png(caminho)
	var tingir := str(extra.get("tingir", _tingir_do_png.get(caminho, "nenhum")))
	no.set("tingir", tingir if (tingir == "elemento" or tingir.begins_with("#")) else "")
	no.set("empunhadura", _vetor(extra.get("empunhadura"), no.get("empunhadura")))
	no.set("ponta", _vetor(extra.get("ponta"), no.get("ponta")))
	for campo in ["tamanho_m", "duracao_s"]:
		if extra.has(campo):
			no.set(campo, float(extra[campo]))
	no.call("preparar")
	var cena := PackedScene.new()
	cena.pack(no)
	no.free()
	return cena


func _cena(categoria: String, pedido: String, candidatos: Array, ajustes_png := {}) -> PackedScene:
	var caminho := _achar(categoria, candidatos)
	var chave := categoria + ":" + pedido
	if caminho.ends_with(".png"):
		var chave_cache := caminho + "|" + str(ajustes_png)
		if not _cache.has(chave_cache):
			var feita := _cena_png(caminho, ajustes_png)
			if feita == null:
				# PNG que nao abre: a cadeia segue sem ele (o relatorio diz)
				escolhas[chave] = "(png ilegivel: %s)" % caminho
				var sem_png := []
				for c in candidatos:
					if not str(c).begins_with(PREFIXO_PNG):
						sem_png.append(c)
				var resto := _cena(categoria, pedido + "#sem_png", sem_png)
				return resto
			_cache[chave_cache] = feita
		escolhas[chave] = caminho
		return _cache[chave_cache]
	if caminho.is_empty():
		escolhas[chave] = "(reserva embutida)"
		reservas[chave] = true
		return _reserva(categoria)
	escolhas[chave] = caminho
	if caminho.get_file().begins_with("_padrao"):
		reservas[chave] = true
	if not _cache.has(caminho):
		var cena = load(caminho)
		if not (cena is PackedScene):
			escolhas[chave] = "(reserva embutida: %s nao carregou)" % caminho
			reservas[chave] = true
			return _reserva(categoria)
		_cache[caminho] = cena
	return _cache[caminho]


func _reserva(categoria: String) -> PackedScene:
	var chave := "__reserva__" + categoria
	if _cache.has(chave):
		return _cache[chave]
	var raiz := Node2D.new()
	raiz.name = "Reserva_" + categoria
	raiz.set_script(load(RESERVA))
	raiz.set("categoria", categoria)
	var cena := PackedScene.new()
	cena.pack(raiz)
	raiz.free()
	_cache[chave] = cena
	return cena


static func _sem_parenteses(texto: String) -> String:
	var i := texto.find("(")
	return texto.substr(0, i).strip_edges() if i >= 0 else texto


func arma(tipo: String, estilo: String) -> PackedScene:
	var catalogada := resolver_peca(["arma.estilo." + UtilPalco.slug(estilo), "arma.tipo." + UtilPalco.slug(tipo), "arma.generica"])
	if not catalogada.is_empty() and _tem_folha_catalogo(catalogada):
		return _cena_catalogo(catalogada)
	# A Corrente nao entra pelo PNG da arma inteira: a peca dela e a corrente
	# de Verlet (armas/tipos/corrente), e a arte dela sao elos e cabecas (F4).
	var com_png := UtilPalco.slug(tipo) != "corrente"
	return _cena("armas", "%s/%s" % [tipo, estilo], [
		_id_slot("arma", "arma", "estilo", UtilPalco.slug(estilo)) if com_png and estilo != "" else "",
		"estilos/" + UtilPalco.slug(estilo) if estilo != "" else "",
		_id_slot("arma", "arma", "tipo", UtilPalco.slug(tipo)) if com_png and tipo != "" else "",
		"tipos/" + UtilPalco.slug(tipo) if tipo != "" else "",
		"_padrao",
	], {"modo": "arma"})


func lutador(nome: String, classe: String) -> PackedScene:
	var catalogada := resolver_peca(["lutador.nome." + UtilPalco.slug(nome), "classe." + UtilPalco.slug(classe), "lutador.corpo", "lutador.generico"])
	if not catalogada.is_empty() and _tem_folha_catalogo(catalogada):
		return _cena_catalogo(catalogada)
	return _cena("lutadores", "%s/%s" % [nome, classe], [
		"nomes/" + UtilPalco.slug(nome) if nome != "" else "",
		"classes/" + UtilPalco.slug(classe) if classe != "" else "",
		"classes/" + UtilPalco.slug(_sem_parenteses(classe)) if classe != "" else "",
		"_padrao",
	])


## O elemento como chave do manifesto ("" para sem elemento / DEFAULT).
static func _chave_elemento(elemento: String) -> String:
	var chave := UtilPalco.slug(elemento)
	return "" if chave == "default" else chave


static func candidatos_objeto_png(tipo: String, elemento: String, nome: String, forma := "") -> Array:
	var el := _chave_elemento(elemento)
	if tipo == "projetil_arma":
		return [_id_slot("arma", "projetil_arma", "forma", UtilPalco.slug(forma)) if forma != "" else "", "", ""]
	if tipo == "orbe":
		return ["", "", _id_slot("arma", "orbe", "tipo", "magica", "orbitando")]
	var parte := str(PARTE_DO_OBJETO.get(tipo, ""))
	if parte == "":
		return ["", "", ""]
	return [
		_id_slot("skill", parte, "skill", UtilPalco.slug(nome)) if nome != "" else "",
		_id_slot("skill", parte, "elemento", el) if el != "" else "",
		_id_slot("skill", parte, "comum", "_"),
	]


func objeto(tipo: String, elemento: String, nome: String, forma := "") -> PackedScene:
	var catalogada := cena_catalogada([
		"skill." + UtilPalco.slug(nome), "efeito." + UtilPalco.slug(tipo),
		"elemento." + UtilPalco.slug(elemento), "efeito.generico"])
	if catalogada != null:
		return catalogada
	var png := candidatos_objeto_png(tipo, elemento, nome, forma)
	return _cena("efeitos", "%s/%s/%s" % [tipo, elemento, nome], [
		png[0],
		"skills/" + UtilPalco.slug(nome) if nome != "" else "",
		png[1],
	] + ordem_comum_e_elemento(ordem_do_comum, png[2],
		"objetos/%s/%s" % [tipo, UtilPalco.slug(elemento)] if elemento != "" else "") + [
		"objetos/%s/_padrao" % tipo,
		"objetos/_padrao",
	], {"modo": "objeto", "girar": not OBJETO_PARADO.has(tipo)})


static func candidatos_evento(tipo: String, tier := "", elemento := "", variante := "") -> Array:
	var nome := UtilPalco.slug(tipo)
	return [
		"eventos/%s_%s" % [nome, UtilPalco.slug(variante)] if variante != "" else "",
		"eventos/%s_%s" % [nome, UtilPalco.slug(elemento)] if elemento != "" else "",
		"eventos/%s_%s" % [nome, UtilPalco.slug(tier)] if tier != "" else "",
		"eventos/" + nome,
		"eventos/_padrao",
	]


## A cadeia do evento com o PNG do Atelie antes de cada cena do mesmo nivel.
static func candidatos_evento_com_png(tipo: String, tier := "", elemento := "", variante := "") -> Array:
	var nome := UtilPalco.slug(tipo)
	var cenas := candidatos_evento(tipo, tier, elemento, variante)
	var por_elemento := str(EVENTO_POR_ELEMENTO.get(nome, ""))
	var el := _chave_elemento(elemento)
	return [
		_id_slot("efeito", "evento", "variante", "%s_%s" % [nome, UtilPalco.slug(variante)]) if variante != "" else "",
		cenas[0],
		_id_slot("efeito", por_elemento, "elemento", el) if por_elemento != "" and el != "" else "",
		cenas[1],
		_id_slot("efeito", "evento", "variante", "%s_%s" % [nome, UtilPalco.slug(tier)]) if tier != "" else "",
		cenas[2],
		_id_slot("efeito", "evento", "tipo", nome),
		_id_slot("efeito", por_elemento, "comum", "_") if por_elemento != "" else "",
		cenas[3],
		cenas[4],
	]


func evento(tipo: String, tier := "", elemento := "", variante := "", skill := "", tipo_skill := "") -> PackedScene:
	var catalogada := cena_catalogada([
		"skill." + UtilPalco.slug(skill), "skill.tipo." + UtilPalco.slug(tipo_skill),
		"evento." + UtilPalco.slug(tipo), "efeito." + UtilPalco.slug(tipo),
		"elemento." + UtilPalco.slug(elemento), "efeito.generico"])
	if catalogada != null:
		return catalogada
	var nome := UtilPalco.slug(tipo)
	var tamanho := float(TAMANHO_EVENTO.get("%s_%s" % [nome, UtilPalco.slug(tier)], TAMANHO_EVENTO.get(nome, 1.6)))
	return _cena("efeitos", "evento/%s/%s/%s/%s" % [tipo, tier, elemento, variante],
		candidatos_evento_com_png(tipo, tier, elemento, variante),
		{"modo": "evento", "tamanho_m": tamanho, "duracao_s": 0.6 if nome == "ko" else 0.35})


static func candidatos_peca_lutador(categoria: String, nome: String) -> Array:
	var pasta := UtilPalco.slug(categoria)
	return [
		"%s/%s" % [pasta, UtilPalco.slug(nome)] if nome != "" else "",
		"%s/_padrao" % pasta,
	]


## O PNG do Atelie da camada em volta do lutador (Em volta do lutador:
## estados e status por nome; buffs, canais e transformacoes por skill).
static func candidato_camada_png(categoria: String, nome: String) -> String:
	var pasta := UtilPalco.slug(categoria)
	if not CAMADA.has(pasta) or nome == "":
		return ""
	var parte: String = CAMADA[pasta][0]
	if CAMADA[pasta][1] == "comum":
		return _id_slot("camada_estado", parte, "comum", "_", UtilPalco.slug(nome))
	return _id_slot("camada_estado", parte, "skill", UtilPalco.slug(nome))


func _candidatos_camada(categoria: String, nome: String) -> Array:
	return [candidato_camada_png(categoria, nome)] + candidatos_peca_lutador(categoria, nome)


func tem_peca_lutador(categoria: String, nome: String) -> bool:
	return not _achar("lutadores", _candidatos_camada(categoria, nome)).is_empty()


func peca_lutador(categoria: String, nome: String) -> PackedScene:
	return _cena("lutadores", "peca/%s/%s" % [categoria, nome], _candidatos_camada(categoria, nome), {"modo": "camada"})


## Camadas persistentes gravadas em `trilhas.efeitos` (status e buff).
## Sem folha retorna null, pois elas nunca tiveram marcador proprio no palco.
func efeito_lutador(tipo: String, nome: String) -> PackedScene:
	var prefixo := "estado." if tipo == "status" else "buff." if tipo == "buff" else ""
	if prefixo == "":
		return null
	return cena_catalogada([prefixo + UtilPalco.slug(nome)])


func estado_lutador(nome: String) -> PackedScene:
	return cena_catalogada(["estado_lutador." + UtilPalco.slug(nome)])


func arena(nome: String, tema: String) -> PackedScene:
	return _cena("arenas", "%s/%s" % [nome, tema], [
		UtilPalco.slug(nome) if nome != "" else "",
		"temas/" + UtilPalco.slug(tema) if tema != "" else "",
		"_padrao",
	])


func hud() -> PackedScene:
	return _cena("hud", "hud", ["_padrao"])


## Som da biblioteca do PALCO (sobrepoe o do jogo so para o video). Vazio =
## nao ha; quem chama cai no arquivo resolvido pela cadeia do jogo.
func som(id_som: String) -> String:
	for ext in EXT_SOM:
		var caminho: String = raiz + "sons/" + id_som + str(ext)
		if ResourceLoader.exists(caminho):
			return caminho
	return ""


## Pasta de uma animacao do Atelie. A primeira peca com folha vence (heranca
## vem do catalogo, do mais especifico ao generico); nunca depende de .import.
func pasta_animacao(peca: String, estado: String, animacao: String, heranca: Array = []) -> String:
	for id in [peca] + heranca:
		var pasta := raiz + "animacoes/" + str(id) + "/" + estado + "/" + animacao
		if FileAccess.file_exists(pasta.path_join("folha.png")) and FileAccess.file_exists(pasta.path_join("animacao.json")):
			return pasta
	return ""


func _cena_folha(pasta: String) -> PackedScene:
	var no := Node2D.new()
	no.name = "TocadorFolha"
	no.set_script(load(TOCADOR_FOLHA))
	# Compatibilidade com chamadas antigas: o caminho tambem precisa sobreviver
	# ao pack, logo vai como configuracao exportada e e carregado no _ready.
	no.set("catalogo_peca", {"estados": [{"id": "base", "animacoes": [{"id": "ociosa", "gatilho": "ocioso", "loop": true, "pasta": pasta}]}]})
	var cena := PackedScene.new()
	cena.pack(no)
	no.free()
	return cena
