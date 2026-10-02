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

const RAIZ := "res://biblioteca/"
const EXTENSOES := [".tscn", ".scn"]
const EXT_SOM := [".wav", ".ogg", ".mp3"]
const RESERVA := "res://nucleo/peca_reserva.gd"

var raiz := RAIZ          # os testes apontam para uma biblioteca de mentira
var _cache := {}          # caminho -> PackedScene
var escolhas := {}        # "categoria:pedido" -> caminho escolhido (relatorio)
var reservas := {}        # pedidos que cairam no _padrao ou na reserva embutida


func _achar(categoria: String, candidatos: Array) -> String:
	for rel in candidatos:
		if str(rel).is_empty():
			continue
		for ext in EXTENSOES:
			var caminho: String = raiz + categoria + "/" + str(rel) + str(ext)
			if ResourceLoader.exists(caminho):
				return caminho
	return ""


func _cena(categoria: String, pedido: String, candidatos: Array) -> PackedScene:
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
	return _cena("armas", "%s/%s" % [tipo, estilo], [
		"estilos/" + UtilPalco.slug(estilo) if estilo != "" else "",
		"tipos/" + UtilPalco.slug(tipo) if tipo != "" else "",
		"_padrao",
	])


func lutador(nome: String, classe: String) -> PackedScene:
	return _cena("lutadores", "%s/%s" % [nome, classe], [
		"nomes/" + UtilPalco.slug(nome) if nome != "" else "",
		"classes/" + UtilPalco.slug(classe) if classe != "" else "",
		"classes/" + UtilPalco.slug(_sem_parenteses(classe)) if classe != "" else "",
		"_padrao",
	])


func objeto(tipo: String, elemento: String, nome: String) -> PackedScene:
	return _cena("efeitos", "%s/%s/%s" % [tipo, elemento, nome], [
		"skills/" + UtilPalco.slug(nome) if nome != "" else "",
		"objetos/%s/%s" % [tipo, UtilPalco.slug(elemento)] if elemento != "" else "",
		"objetos/%s/_padrao" % tipo,
		"objetos/_padrao",
	])


static func candidatos_evento(tipo: String, tier := "", elemento := "", variante := "") -> Array:
	var nome := UtilPalco.slug(tipo)
	return [
		"eventos/%s_%s" % [nome, UtilPalco.slug(variante)] if variante != "" else "",
		"eventos/%s_%s" % [nome, UtilPalco.slug(elemento)] if elemento != "" else "",
		"eventos/%s_%s" % [nome, UtilPalco.slug(tier)] if tier != "" else "",
		"eventos/" + nome,
		"eventos/_padrao",
	]


func evento(tipo: String, tier := "", elemento := "", variante := "") -> PackedScene:
	return _cena("efeitos", "evento/%s/%s/%s/%s" % [tipo, tier, elemento, variante],
		candidatos_evento(tipo, tier, elemento, variante))


static func candidatos_peca_lutador(categoria: String, nome: String) -> Array:
	var pasta := UtilPalco.slug(categoria)
	return [
		"%s/%s" % [pasta, UtilPalco.slug(nome)] if nome != "" else "",
		"%s/_padrao" % pasta,
	]


func tem_peca_lutador(categoria: String, nome: String) -> bool:
	return not _achar("lutadores", candidatos_peca_lutador(categoria, nome)).is_empty()


func peca_lutador(categoria: String, nome: String) -> PackedScene:
	return _cena("lutadores", "peca/%s/%s" % [categoria, nome], candidatos_peca_lutador(categoria, nome))


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
