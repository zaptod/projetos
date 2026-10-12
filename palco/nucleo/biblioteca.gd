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
## A arte do Atelie entra apenas pelo catalogo de animacoes e pelas folhas
## correspondentes. PNG avulso de manifesto nao vira peca do palco.

const RAIZ := "res://biblioteca/"
const EXTENSOES := [".tscn", ".scn"]
const EXT_SOM := [".wav", ".ogg", ".mp3"]
const RESERVA := "res://nucleo/peca_reserva.gd"
const TOCADOR_FOLHA := "res://nucleo/tocador_folha.gd"
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


func tem_folha_evento(tipo: String, elemento := "", skill := "", tipo_skill := "", variante := "") -> bool:
	return tem_folha_catalogada(["movimento." + UtilPalco.slug(variante) if tipo == "movimento" else "", "skill." + UtilPalco.slug(skill), "skill.tipo." + UtilPalco.slug(tipo_skill),
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


func _achar(categoria: String, candidatos: Array) -> String:
	for rel in candidatos:
		if str(rel).is_empty():
			continue
		var so_arte := str(rel).begins_with(PREFIXO_ARTE)
		var nome := str(rel).trim_prefix(PREFIXO_ARTE)
		for ext in EXTENSOES:
			var caminho: String = raiz + categoria + "/" + nome + str(ext)
			if ResourceLoader.exists(caminho) and not (so_arte and eh_provisoria(caminho)):
				return caminho
	return ""


static func _id_slot(grupo: String, parte: String, nivel: String, chave: String, estado := "base") -> String:
	# A assinatura fica para os candidatos antigos, mas PNG avulso nao entra.
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


func _cena(categoria: String, pedido: String, candidatos: Array, ajustes_png := {}) -> PackedScene:
	var caminho := _achar(categoria, candidatos)
	var chave := categoria + ":" + pedido
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


func rostos() -> Array:
	var cenas := []
	for id in ["lutador.rosto.boca", "lutador.rosto.detalhe_rosto", "lutador.rosto.olhos", "lutador.rosto.sobrancelhas"]:
		var cena := cena_catalogada([id, id + ".generico"])
		if cena != null:
			cenas.append(cena)
	return cenas


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
		"movimento." + UtilPalco.slug(variante) if tipo == "movimento" else "", "skill." + UtilPalco.slug(skill), "skill.tipo." + UtilPalco.slug(tipo_skill),
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
