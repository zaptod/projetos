class_name PartesLutador
extends RefCounted
## Resolve os PNGs modulares do lutador. A regra fica aqui para o palco e os
## testes usarem exatamente a mesma heranca.

const RAIZ := "res://biblioteca/partes/lutador"
static var _biblioteca_externa := ""
static var _caminhos := {}
static var _rotulos := {}
static var _rotulos_palco := {}
static var _manifesto_lido := false
static var _guarda_roupa := {}
const PARTES := {
	"sombra": {"z": 0, "quadro": "mundo"},
	"acessorio_costas": {"z": 10, "quadro": "olhar"},
	"pele": {"z": 20, "quadro": "tela"},
	"marcas": {"z": 25, "quadro": "olhar"},
	"olhos": {"z": 40, "quadro": "olhar"},
	"sobrancelhas": {"z": 45, "quadro": "olhar"},
	"boca": {"z": 50, "quadro": "olhar"},
	"detalhe_rosto": {"z": 55, "quadro": "olhar"},
	"acessorio_cabeca": {"z": 60, "quadro": "olhar"},
}
const EXPRESSOES := [
	"neutro", "focado", "glacial", "determinado", "furia", "berserk", "confiante", "animado",
	"euforico", "extase", "panico", "nervoso", "desespero", "tedio", "tristeza", "morto",
	"tonto", "dor", "esforco", "firmeza", "alerta", "confuso", "limite", "concentrado",
]
const FAMILIA := {
	"neutro": "neutro", "focado": "neutro", "glacial": "neutro", "concentrado": "neutro",
	"firmeza": "neutro", "tedio": "neutro", "determinado": "furia", "furia": "furia",
	"berserk": "furia", "esforco": "furia", "limite": "furia", "confiante": "animado",
	"animado": "animado", "euforico": "animado", "extase": "animado", "panico": "panico",
	"nervoso": "panico", "desespero": "panico", "alerta": "panico", "confuso": "panico",
	"tonto": "dor", "tristeza": "dor", "dor": "dor", "morto": "morto",
}
const PARTES_DE_EXPRESSAO := {"olhos": true, "sobrancelhas": true, "boca": true, "detalhe_rosto": true}
const NIVEIS := {
	"sombra": ["comum"], "acessorio_costas": ["personagem", "classe"],
	"pele": ["personagem", "classe", "comum"], "marcas": ["personagem", "classe"],
	"olhos": ["personagem", "classe", "comum"], "sobrancelhas": ["personagem", "classe", "comum"],
	"boca": ["personagem", "classe", "comum"], "detalhe_rosto": ["comum"],
	"acessorio_cabeca": ["personagem", "classe"],
}


static func caminho(parte: String, nivel: String, alvo: String, estado: String, variante: String = "v01") -> String:
	_carregar_manifesto()
	var chave := "%s/%s/%s/%s/%s" % [parte, nivel, alvo, variante, estado]
	if _caminhos.has(chave):
		return str(_caminhos[chave])
	# Com biblioteca externa (previa do painel, testes), nada cai na
	# biblioteca real do palco: o que nao esta no manifesto e procurado la.
	var raiz := (_biblioteca_externa + "/partes/lutador") if _biblioteca_externa else RAIZ
	return "%s/%s/%s/%s/%s/%s.png" % [raiz, parte, nivel, alvo, variante, estado]


## O nome humano do alvo ("Berserker (Furia)", com acento), tirado do
## `alvo.rotulo` do manifesto; aceita o id (berserker_furia) ou o nome.
## Devolve "" quando o manifesto nao conhece o alvo.
static func rotulo(nivel: String, alvo: String) -> String:
	_carregar_manifesto()
	var chave := nivel + "/" + UtilPalco.slug(alvo)
	if _rotulos.has(chave) or _biblioteca_externa == "":
		return str(_rotulos.get(chave, ""))
	# biblioteca externa sem o alvo no manifesto dela: o nome continua sendo
	# o da engine, que o manifesto do palco conhece
	if _rotulos_palco.is_empty():
		for slot in _slots_do_manifesto("res://biblioteca/manifesto_slots.json"):
			var a: Dictionary = slot.get("alvo", {})
			if str(a.get("rotulo", "")) != "":
				_rotulos_palco["%s/%s" % [a.get("nivel", ""), a.get("chave", "")]] = str(a.get("rotulo"))
	return str(_rotulos_palco.get(chave, ""))


static func _slots_do_manifesto(manifesto: String) -> Array:
	if not FileAccess.file_exists(manifesto):
		return []
	var json := JSON.new()
	if json.parse(FileAccess.get_file_as_string(manifesto)) != OK or typeof(json.data) != TYPE_DICTIONARY:
		return []
	var saida := []
	for slot in json.data.get("slots", []):
		if typeof(slot) == TYPE_DICTIONARY and str(slot.get("grupo", "")) == "lutador":
			saida.append(slot)
	return saida


static func configurar_biblioteca(caminho_biblioteca: String) -> void:
	_biblioteca_externa = caminho_biblioteca.replace("\\", "/").rstrip("/")
	_caminhos.clear()
	_rotulos.clear()
	_guarda_roupa.clear()
	_manifesto_lido = false


## Le o manifesto uma vez por processo (por biblioteca): o resolvedor pergunta
## o caminho dezenas de vezes por parte e o manifesto tem ~1.900 slots.
static func _carregar_manifesto() -> void:
	if _manifesto_lido:
		return
	_manifesto_lido = true
	var manifesto := (_biblioteca_externa + "/manifesto_slots.json") if _biblioteca_externa else "res://biblioteca/manifesto_slots.json"
	for slot in _slots_do_manifesto(manifesto):
		var alvo: Dictionary = slot.get("alvo", {})
		var destino := str(slot.get("destino", "")).replace("\\", "/")
		var pedacos: PackedStringArray = destino.split("/")
		var variante := "v01"
		if pedacos.size() >= 2 and pedacos[-2].begins_with("v"):
			variante = pedacos[-2]
		var chave := "%s/%s/%s/%s/%s" % [slot.get("parte", ""), alvo.get("nivel", ""), alvo.get("chave", ""), variante, slot.get("estado", "base")]
		if str(alvo.get("rotulo", "")) != "":
			_rotulos["%s/%s" % [alvo.get("nivel", ""), alvo.get("chave", "")]] = str(alvo.get("rotulo"))
		var relativo := destino.trim_prefix("palco/biblioteca/")
		_caminhos[chave] = (_biblioteca_externa + "/" + relativo) if _biblioteca_externa else "res://biblioteca/" + relativo
	var guarda := (_biblioteca_externa + "/partes/guarda_roupa.json") if _biblioteca_externa else "res://biblioteca/partes/guarda_roupa.json"
	if FileAccess.file_exists(guarda):
		var json_guarda := JSON.new()
		if json_guarda.parse(FileAccess.get_file_as_string(guarda)) == OK and typeof(json_guarda.data) == TYPE_DICTIONARY:
			_guarda_roupa = json_guarda.data


static func estados(parte: String, expressao: String) -> Array:
	if not PARTES_DE_EXPRESSAO.has(parte):
		return ["base"]
	var familia := str(FAMILIA.get(expressao, "neutro"))
	var saida := [expressao]
	if familia != expressao:
		saida.append(familia)
	if not saida.has("neutro"):
		saida.append("neutro")
	return saida


static func resolver(parte: String, personagem: String, classe: String, expressao: String) -> Dictionary:
	return resolver_com(parte, personagem, classe, expressao,
		func(caminho_png: String): return FileAccess.file_exists(caminho_png))


## O painel grava a escolha ao lado do PNG. Sem .json, a pele comum segue a
## regra segura do contrato: mascara tingida pela cor do personagem.
static func tingir(parte: Dictionary) -> String:
	if parte.is_empty():
		return "nenhum"
	var dados := opcoes(parte)
	if not dados.is_empty():
		return str(dados.get("tingir", "nenhum"))
	return "cor_personagem" if str(parte.get("nivel", "")) == "comum" else "nenhum"


## O .json que o painel grava ao lado do PNG (tingir, contorno_proprio,
## brilho_proprio...); {} quando nao existe ou nao abre.
static func opcoes(parte: Dictionary) -> Dictionary:
	if parte.is_empty():
		return {}
	var caminho_json := str(parte.get("caminho", "")).get_basename() + ".json"
	if FileAccess.file_exists(caminho_json):
		var json := JSON.new()
		if json.parse(FileAccess.get_file_as_string(caminho_json)) == OK and typeof(json.data) == TYPE_DICTIONARY:
			return json.data
	return {}


## `existe` deixa a regra verificavel sem criar ou importar PNGs no teste.
static func resolver_com(parte: String, personagem: String, classe: String, expressao: String, existe: Callable) -> Dictionary:
	if not PARTES.has(parte):
		return {}
	var niveis := [["personagem", UtilPalco.slug(personagem)], ["classe", UtilPalco.slug(classe)], ["comum", "_"]]
	for nivel in niveis:
		var nivel_nome := str(nivel[0])
		if not NIVEIS[parte].has(nivel_nome):
			continue
		var alvo := str(nivel[1])
		if alvo == "" and nivel_nome != "comum":
			continue
		var colecao := _variantes(parte, nivel_nome, alvo, existe)
		if colecao.is_empty():
			continue
		var fixadas: Dictionary = _guarda_roupa.get(UtilPalco.slug(personagem), {})
		var variante := str(fixadas.get(parte, ""))
		if not colecao.has(variante):
			variante = _sorteio_variante(personagem if personagem != "" else classe, parte, colecao.keys())
		for estado in estados(parte, expressao):
			var png := caminho(parte, nivel_nome, alvo, str(estado), variante)
			if existe.call(png):
				return {"caminho": png, "nivel": nivel_nome, "estado": estado,
					"variante": variante, "z": int(PARTES[parte]["z"]), "quadro": str(PARTES[parte]["quadro"])}
		# Um dono sem o estado pedido cai no neutro dele; se ele so tiver uma
		# expressao avulsa, nao mistura a identidade com o nivel de baixo.
		return {}
	return {}


static func _variantes(parte: String, nivel: String, alvo: String, existe: Callable) -> Dictionary:
	var raiz := (_biblioteca_externa + "/partes/lutador") if _biblioteca_externa else RAIZ
	var pasta := "%s/%s/%s/%s" % [raiz, parte, nivel, alvo]
	var saida := {}
	# A v01 e sempre consultada pelo `existe`, mesmo sem a pasta no disco: e o
	# contrato antigo (uma arte por slot) e e o que deixa a regra verificavel
	# sem PNG (testes.gd), igual ao fallback de manifesto_sprites.resolver_parte.
	var candidatas: Array = ["v01"]
	if DirAccess.dir_exists_absolute(pasta):
		for nome in DirAccess.get_directories_at(pasta):
			if not candidatas.has(nome):
				candidatas.append(nome)
	for variante in candidatas:
		if not str(variante).begins_with("v"):
			continue
		for estado in (EXPRESSOES if PARTES_DE_EXPRESSAO.has(parte) else ["base"]):
			if existe.call(caminho(parte, nivel, alvo, estado, variante)):
				saida[variante] = true
				break
	return saida


static func _sorteio_variante(personagem: String, parte: String, opcoes: Array) -> String:
	var numero := 0
	var texto := personagem + ":" + parte
	for i in texto.length():
		numero = (numero * 31 + texto.unicode_at(i)) % 2147483647
	var ordenadas := opcoes.duplicate()
	ordenadas.sort()
	return str(ordenadas[numero % ordenadas.size()])
