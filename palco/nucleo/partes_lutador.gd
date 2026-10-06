class_name PartesLutador
extends RefCounted
## Resolve os PNGs modulares do lutador. A regra fica aqui para o palco e os
## testes usarem exatamente a mesma heranca.

const RAIZ := "res://biblioteca/partes/lutador"
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


static func caminho(parte: String, nivel: String, alvo: String, estado: String) -> String:
	return "%s/%s/%s/%s/%s.png" % [RAIZ, parte, nivel, alvo, estado]


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
	var caminho_json := str(parte.get("caminho", "")).get_basename() + ".json"
	if FileAccess.file_exists(caminho_json):
		var json := JSON.new()
		if json.parse(FileAccess.get_file_as_string(caminho_json)) == OK and typeof(json.data) == TYPE_DICTIONARY:
			return str(json.data.get("tingir", "nenhum"))
	return "cor_personagem" if str(parte.get("nivel", "")) == "comum" else "nenhum"


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
		# O primeiro nivel que possui QUALQUER estado e o dono da parte.
		var dono := false
		var possiveis: Array = EXPRESSOES if PARTES_DE_EXPRESSAO.has(parte) else ["base"]
		for estado in possiveis:
			if existe.call(caminho(parte, nivel_nome, alvo, str(estado))):
				dono = true
				break
		if not dono:
			continue
		for estado in estados(parte, expressao):
			var png := caminho(parte, nivel_nome, alvo, str(estado))
			if existe.call(png):
				return {"caminho": png, "nivel": nivel_nome, "estado": estado,
					"z": int(PARTES[parte]["z"]), "quadro": str(PARTES[parte]["quadro"])}
		# Um dono sem o estado pedido cai no neutro dele; se ele so tiver uma
		# expressao avulsa, nao mistura a identidade com o nivel de baixo.
		return {}
	return {}
