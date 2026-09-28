class_name UtilPalco
extends RefCounted
## Pequenas funcoes usadas pelo palco inteiro (sem estado).
##
## Unidades: a timeline fala em METROS e GRAUS; o mundo do Godot fala em px.
## PX_POR_M e so a escala do mundo antes da camera (a camera decide quanto
## disso cabe na tela). 100 px por metro deixa as pecas da biblioteca com um
## tamanho confortavel de desenhar no editor: um lutador de 1,7 m tem raio de
## 85 px na cena.

const PX_POR_M := 100.0

# Paletas por elemento (neural_fights/utils/palette.py: ELEMENT_PALETTES).
# core = centro quente, mid/outer = aneis, spark = faisca, glow = halo.
const PALETAS := {
	"FOGO": {"core": 0xFFFFC8, "mid": [0xFFB432, 0xFF7800, 0xFF5000], "outer": [0xFF3200, 0xC81E00, 0x961400], "spark": 0xFFFF64, "glow": 0xFF6400},
	"GELO": {"core": 0xFFFFFF, "mid": [0xC8F0FF, 0x96DCFF, 0x64C8FF], "outer": [0x50B4FF, 0x3296DC, 0x1E78C8], "spark": 0xDCFAFF, "glow": 0x64C8FF},
	"RAIO": {"core": 0xFFFFFF, "mid": [0xFFFF96, 0xFFFF64, 0xC8C8FF], "outer": [0x9696FF, 0x6464FF, 0x5050C8], "spark": 0xFFFFFF, "glow": 0x9696FF},
	"TREVAS": {"core": 0x9664C8, "mid": [0x640096, 0x500078, 0x3C0064], "outer": [0x280050, 0x1E003C, 0x140028], "spark": 0xC896FF, "glow": 0x640096},
	"LUZ": {"core": 0xFFFFFF, "mid": [0xFFFFDC, 0xFFFFB4, 0xFFF096], "outer": [0xFFDC64, 0xFFC832, 0xFFB400], "spark": 0xFFFFFF, "glow": 0xFFFFC8},
	"NATUREZA": {"core": 0xC8FFC8, "mid": [0x64FF64, 0x50DC50, 0x3CC83C], "outer": [0x32B432, 0x289628, 0x1E781E], "spark": 0xB4FFB4, "glow": 0x64FF64},
	"ARCANO": {"core": 0xFFC8FF, "mid": [0xDC96FF, 0xC864FF, 0xB450FF], "outer": [0x9632C8, 0x781EB4, 0x641496], "spark": 0xFFC8FF, "glow": 0xC864FF},
	"CAOS": {"core": 0xFFFFFF, "mid": [0xFF6464, 0x64FF64, 0x6464FF], "outer": [0xFF32C8, 0xC832FF, 0x32C8FF], "spark": 0xFFFFFF, "glow": 0xFF64FF},
	"SANGUE": {"core": 0xFFC8C8, "mid": [0xDC3232, 0xC81E1E, 0xB41414], "outer": [0x960000, 0x780000, 0x640000], "spark": 0xFF9696, "glow": 0xC80000},
	"VOID": {"core": 0x643296, "mid": [0x320064, 0x1E0050, 0x14003C], "outer": [0x0A0028, 0x05001E, 0x000014], "spark": 0x9664C8, "glow": 0x320064},
	"TEMPO": {"core": 0xF0EBFF, "mid": [0xD2C3FF, 0xB4A5F0, 0x968CDC], "outer": [0x786EBE, 0x5F55A0, 0x463C82], "spark": 0xE6DCFF, "glow": 0xB4A0FF},
	"GRAVITACAO": {"core": 0xC8BEFF, "mid": [0x8C6EFF, 0x6E50E6, 0x5A3CC8], "outer": [0x3C2896, 0x2D1E78, 0x1E145A], "spark": 0xAA96FF, "glow": 0x6E50E6},
	"DEFAULT": {"core": 0xFFFFFF, "mid": [0xC8C8C8, 0xB4B4B4, 0x969696], "outer": [0x787878, 0x646464, 0x505050], "spark": 0xFFFFFF, "glow": 0xC8C8C8},
}

# Cor por tier de impacto (a faisca do acerto cresce e esquenta com o tier).
const COR_TIER := {"light": 0xFFF6C8, "medium": 0xFFD25A, "heavy": 0xFF8A2A, "colossal": 0xFF3C3C}


## 0xRRGGBB (int ou float do JSON) -> Color. O JSON do Godot le numero como
## float; int() antes de mexer nos bits.
static func cor(valor, alfa: float = 1.0) -> Color:
	var v := int(valor) if valor != null else 0xFFFFFF
	return Color8((v >> 16) & 255, (v >> 8) & 255, v & 255, int(clampf(alfa, 0.0, 1.0) * 255.0))


## "Mágica" -> "magica"; "Machado-Martelo" -> "machado_martelo";
## "Piromante (Fogo)" -> "piromante_fogo". E o nome de ARQUIVO que a
## biblioteca procura: sem acento, sem espaco, minusculo.
static func slug(texto: String) -> String:
	var de := "áàâãäåéèêëíìîïóòôõöúùûüçñý"
	var para := "aaaaaaeeeeiiiiooooouuuucny"
	var saida := ""
	for ch in texto.strip_edges().to_lower():
		var c: String = ch
		var i := de.find(c)
		if i >= 0:
			c = para[i]
		if (c >= "a" and c <= "z") or (c >= "0" and c <= "9"):
			saida += c
		elif saida != "" and not saida.ends_with("_"):
			saida += "_"
	return saida.trim_suffix("_")


static func paleta(elemento: String) -> Dictionary:
	var chave := elemento.to_upper()
	if PALETAS.has(chave):
		return PALETAS[chave]
	return PALETAS["DEFAULT"]


## Um numero pseudo-aleatorio ESTAVEL em [0, 1) a partir de uma semente e de
## um indice. Os efeitos do palco usam isto no lugar de randf(): o mesmo
## quadro sai igual em qualquer render (o palco e deterministico bit a bit).
static func ruido(semente: int, indice: int) -> float:
	var h := hash(str(semente) + ":" + str(indice))
	return float(h & 0xFFFFFF) / float(0x1000000)


static func m(valor: float) -> float:
	return valor * PX_POR_M


static func mv(x: float, y: float) -> Vector2:
	return Vector2(x, y) * PX_POR_M
