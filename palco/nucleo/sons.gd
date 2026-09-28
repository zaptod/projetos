class_name MesaDeSom
extends Node
## Toca os sons da luta num pool de AudioStreamPlayer.
##
## A lista vem da secao `sons` da timeline (contrato da 16A,
## docs/palco/sons.md): {t, id, volume, pitch, pan?, x?}. `id` e a CHAVE do
## som no jogo; o arquivo e resolvido na hora, nesta ordem:
##   1. biblioteca/sons/<id>.wav|.ogg|.mp3 do palco (troca so no video);
##   2. o arquivo da cadeia do jogo (sound_config.json do runtime ou do
##      pacote, %LOCALAPPDATA%\neural-fights\sounds\, fallbacks), que o
##      Python resolve e manda no job (`sons_arquivos`).
## Trocar um wav no jogo vale no proximo render, sem regravar a luta.
##
## pitch e tocar mais rapido (como fita), igual a mistura offline da 16A;
## volume e ganho linear. O Master tem um limitador a -1 dBFS: vinte golpes
## juntos nao estouram.

const PANS := [-1.0, -0.5, 0.0, 0.5, 1.0]
const OPCOES_WAV := {"compress/mode": 0, "edit/normalize": false, "edit/trim": false}

var arquivos := {}
var biblioteca: Biblioteca
var estilo: EstiloPalco
var _vozes: Array[AudioStreamPlayer] = []
var _inicio_voz := PackedInt32Array()
var _streams := {}
var origem := {}       # id -> de onde o som veio (relatorio)
var tocados := 0
var ids := {}          # id -> vezes tocado
var faltando := {}     # id -> vezes pedido sem arquivo
var cortados := 0      # sons interrompidos por falta de voz livre
var _pan_barramento := {}


func preparar(p_estilo: EstiloPalco, p_biblioteca: Biblioteca, p_arquivos: Dictionary) -> void:
	estilo = p_estilo
	biblioteca = p_biblioteca
	arquivos = p_arquivos
	var master := AudioServer.get_bus_index("Master")
	AudioServer.set_bus_volume_db(master, estilo.volume_db)
	var tem_limitador := false
	for k in AudioServer.get_bus_effect_count(master):
		if AudioServer.get_bus_effect(master, k) is AudioEffectHardLimiter:
			tem_limitador = true
	if not tem_limitador:
		var lim := AudioEffectHardLimiter.new()
		lim.ceiling_db = -1.0
		AudioServer.add_bus_effect(master, lim)
	if estilo.estereo > 0.0:
		for pan in PANS:
			var nome := "Pan%+.1f" % pan
			var idx := AudioServer.bus_count
			AudioServer.add_bus(idx)
			AudioServer.set_bus_name(idx, nome)
			AudioServer.set_bus_send(idx, "Master")
			var efeito := AudioEffectPanner.new()
			efeito.pan = pan * estilo.estereo
			AudioServer.add_bus_effect(idx, efeito)
			_pan_barramento[pan] = nome
	for i in estilo.vozes:
		var voz := AudioStreamPlayer.new()
		voz.name = "Voz%02d" % i
		add_child(voz)
		_vozes.append(voz)
		_inicio_voz.append(-1)


func carregar(id_som: String) -> AudioStream:
	if _streams.has(id_som):
		return _streams[id_som]
	var stream: AudioStream = null
	var da_biblioteca := biblioteca.som(id_som) if biblioteca != null else ""
	if da_biblioteca != "":
		stream = load(da_biblioteca) as AudioStream
		origem[id_som] = da_biblioteca
	elif arquivos.has(id_som):
		stream = carregar_arquivo(str(arquivos[id_som]))
		origem[id_som] = str(arquivos[id_som])
	if stream == null:
		origem[id_som] = "faltando"
	_streams[id_som] = stream
	return stream


static func carregar_arquivo(caminho: String) -> AudioStream:
	if not FileAccess.file_exists(caminho):
		return null
	match caminho.get_extension().to_lower():
		"wav":
			return AudioStreamWAV.load_from_file(caminho, OPCOES_WAV)
		"ogg":
			return AudioStreamOggVorbis.load_from_file(caminho)
		"mp3":
			return AudioStreamMP3.load_from_file(caminho)
	return null


func _voz_livre(quadro: int) -> AudioStreamPlayer:
	var mais_velha := 0
	for i in _vozes.size():
		if not _vozes[i].playing:
			_inicio_voz[i] = quadro
			return _vozes[i]
		if _inicio_voz[i] < _inicio_voz[mais_velha]:
			mais_velha = i
	cortados += 1
	_vozes[mais_velha].stop()
	_inicio_voz[mais_velha] = quadro
	return _vozes[mais_velha]


func _barramento(pan: float) -> String:
	if _pan_barramento.is_empty():
		return "Master"
	var melhor = PANS[0]
	for p in PANS:
		if absf(p - pan) < absf(melhor - pan):
			melhor = p
	return _pan_barramento[melhor]


## Toca um item da lista `sons`. Devolve false se nao ha arquivo para o id.
func tocar(item: Dictionary, quadro: int) -> bool:
	var id_som := str(item.get("id", ""))
	var stream := carregar(id_som)
	if stream == null:
		faltando[id_som] = int(faltando.get(id_som, 0)) + 1
		return false
	var voz := _voz_livre(quadro)
	voz.stream = stream
	voz.volume_db = linear_to_db(maxf(float(item.get("volume", 1.0)), 0.0001))
	voz.pitch_scale = clampf(float(item.get("pitch", 1.0)), 0.25, 4.0)
	voz.bus = _barramento(float(item.get("pan", 0.0)))
	voz.play()
	tocados += 1
	ids[id_som] = int(ids.get(id_som, 0)) + 1
	return true


## Corte seco (jump cut): o som que comecou antes do corte continua soando,
## como na mistura da 16A (ela soma o arquivo inteiro a partir do `t`).
## Nada a fazer aqui; o metodo existe para quem quiser outra regra.
func no_corte() -> void:
	pass


func relatorio() -> Dictionary:
	return {
		"tocados": tocados,
		"ids_distintos": ids.size(),
		"por_id": ids,
		"faltando": faltando,
		"cortados_por_falta_de_voz": cortados,
		"origem": origem,
	}
