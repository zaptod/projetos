extends SceneTree
## Guarda headless: uma folha temporaria por grupo deve chegar ao TocadorFolha.

const PECAS := {
	"skill": ["skill.teste", "skill"], "efeito": ["evento.acerto", "acerto"],
	"elemento": ["elemento.fogo", "skill"], "estado_personagem": ["estado.atordoado", "status"],
	"buff": ["buff.furia", "buff"],
}

func _init() -> void:
	call_deferred("_testar")


func _testar() -> void:
	var raiz := "user://consumo_atelie/"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(raiz))
	var pecas := []
	for grupo in PECAS:
		var id: String = PECAS[grupo][0]
		var gatilho: String = PECAS[grupo][1]
		var pasta := raiz + "animacoes/" + id + "/base/ativa"
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(pasta))
		var imagem := Image.create(2, 2, false, Image.FORMAT_RGBA8)
		imagem.fill(Color.WHITE)
		assert(imagem.save_png(ProjectSettings.globalize_path(pasta + "/folha.png")) == OK)
		var animacao := {"fps": 12, "loop": true, "escala": 1.0,
			"quadros": [{"x": 0, "y": 0, "w": 2, "h": 2}], "ancora": {"x": 0, "y": 0}}
		FileAccess.open(ProjectSettings.globalize_path(pasta + "/animacao.json"), FileAccess.WRITE).store_string(JSON.stringify(animacao))
		pecas.append({"id": id, "grupo": grupo, "heranca": [], "estados": [{"id": "base",
			"animacoes": [{"id": "ativa", "gatilho": gatilho, "loop": true, "camada": 42,
			"segue": "lutador", "tamanho_padrao": "1,0 do corpo"}]}]})
	FileAccess.open(ProjectSettings.globalize_path(raiz + "catalogo_animacoes.json"), FileAccess.WRITE).store_string(JSON.stringify({"pecas": pecas}))
	var biblioteca := Biblioteca.new()
	biblioteca.raiz = raiz
	var falhas := 0
	for grupo in PECAS:
		var cena := biblioteca.cena_catalogada([PECAS[grupo][0]])
		if cena == null:
			print("FALHA ", grupo, ": folha nao resolvida")
			falhas += 1
			continue
		var no := cena.instantiate()
		root.add_child(no)
		if no is TocadorFolha and no.textura != null:
			print("OK ", grupo, " -> ", PECAS[grupo][0])
		else:
			print("FALHA ", grupo, ": tocador ausente")
			falhas += 1
		no.queue_free()
	print("consumo_atelie: %d falha(s)" % falhas)
	quit(1 if falhas else 0)
