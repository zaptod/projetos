@tool
class_name EstiloPalco
extends Resource
## O ESTILO GLOBAL do palco: um arquivo so (biblioteca/estilo.tres) com os
## botoes que valem para todas as pecas. Abra no editor e mexa no inspetor; o
## proximo render ja usa. Um trabalho (job) do Python pode sobrepor qualquer
## campo pelo nome (secao "estilo" do job), sem tocar neste arquivo.

@export_group("Contorno e sombra")
## Largura do contorno dos corpos e das armas, em px do MUNDO (100 px = 1 m;
## a camera amplia junto).
@export_range(0.0, 20.0, 0.5) var contorno_px: float = 3.5
## #14141A: o contorno escuro continuo combinado com a arte da 16F.
@export var cor_contorno: Color = Color8(20, 20, 26)
## Opacidade da sombra de contato sob cada lutador (0 = sem sombra).
@export_range(0.0, 1.0, 0.01) var sombra_alfa: float = 0.34
## Altura da sombra em relacao a largura (0,42 = achatada, como no jogo).
@export_range(0.1, 1.0, 0.01) var sombra_achatamento: float = 0.42

@export_group("Tremor e hitstop")
## Multiplicador do tremor de camera nos golpes fortes (0 = camera parada).
@export_range(0.0, 3.0, 0.05) var tremor: float = 1.0
## Tremor maximo, em px da TELA.
@export_range(0.0, 60.0, 0.5) var tremor_max_px: float = 14.0
## Hitstop EXTRA do render, em segundos, por tier do golpe. O hitstop do
## proprio jogo ja vem congelado na timeline; isto so acrescenta quadros
## parados no video (muda a duracao). 0 = o video dura o mesmo que a luta.
@export_range(0.0, 0.5, 0.01) var hitstop_leve: float = 0.0
@export_range(0.0, 0.5, 0.01) var hitstop_medio: float = 0.0
@export_range(0.0, 0.5, 0.01) var hitstop_pesado: float = 0.0
@export_range(0.0, 0.5, 0.01) var hitstop_colossal: float = 0.0

@export_group("Brilho e efeitos")
## Intensidade do halo dos projeteis, orbes, areas e faiscas.
@export_range(0.0, 1.5, 0.01) var brilho: float = 0.45
## Cel de 2 tons + 1 brilho no corpo, luz do alto a esquerda (0 = chapado,
## como o jogo desde a identidade v2; 1 = o estilo combinado da 16F).
@export_range(0.0, 1.0, 0.01) var brilho_corpo: float = 1.0
## Tamanho das faiscas de acerto.
@export_range(0.2, 3.0, 0.05) var faisca_escala: float = 1.0
## Rastro da ponta da arma durante o golpe.
@export var rastro_arma: bool = true
@export_range(2, 30, 1) var rastro_passos: int = 10

@export_group("Leitura")
@export var mostrar_nomes: bool = true
## Tamanho do nome sobre o lutador, em px da TELA (o jogo usava 13).
@export_range(10, 90, 1) var nome_px: int = 40
@export var mostrar_status: bool = true
## Barras de cinema do golpe letal (canal global `letterbox`).
@export var letterbox: bool = true
@export var cor_fundo: Color = Color(0.05, 0.05, 0.08, 1.0)

@export_group("Som")
## 0 = mono (como a mistura do video de hoje); 1 = pan inteiro da anotacao.
@export_range(0.0, 1.0, 0.05) var estereo: float = 0.0
@export_range(-24.0, 12.0, 0.5) var volume_db: float = 0.0
## Quantos sons tocam ao mesmo tempo (o mais velho e cortado).
@export_range(4, 64, 1) var vozes: int = 32


func hitstop_do_tier(tier: String) -> float:
	match tier:
		"light":
			return hitstop_leve
		"medium":
			return hitstop_medio
		"heavy":
			return hitstop_pesado
		"colossal":
			return hitstop_colossal
	return 0.0


## Aplica a secao "estilo" do job. Campo desconhecido volta na lista (o
## palco avisa no relatorio em vez de ignorar calado).
func sobrepor(campos: Dictionary) -> PackedStringArray:
	var desconhecidos := PackedStringArray()
	var nomes := {}
	for p in get_property_list():
		nomes[p["name"]] = p["type"]
	for chave in campos:
		if not nomes.has(chave):
			desconhecidos.append(str(chave))
			continue
		var valor = campos[chave]
		if nomes[chave] == TYPE_COLOR and typeof(valor) == TYPE_STRING:
			valor = Color(valor)
		elif nomes[chave] == TYPE_INT:
			valor = int(valor)
		elif nomes[chave] == TYPE_FLOAT:
			valor = float(valor)
		set(chave, valor)
	return desconhecidos
