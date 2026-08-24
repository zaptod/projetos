"""SynergyEngine (modo neural_fights): personagem + arma nunca avaliados
isolados. Avalia sobre os REGISTROS canonicos do NF (arma com geometria,
skill com custo de mana) mais os atributos rolados.
"""
from __future__ import annotations

from .roll_evaluator import RollEvaluator
from ..nf_bridge import loader as nf

# rotulo da classe (parenteses) -> elemento de encantamento equivalente
CLASSE_ELEMENTO_MAP = {
    "Fogo": "Fogo", "Gelo": "Gelo", "Trevas": "Trevas", "Sagrado": "Luz",
    "Arcano": "Arcano", "Natureza": "Natureza", "Caos": "Arcano",
}
ELEMENTOS_OPOSTOS = {("Fogo", "Gelo"), ("Gelo", "Fogo"),
                     ("Luz", "Trevas"), ("Trevas", "Luz")}


class SynergyEngine:
    def __init__(self, synergies: dict, evaluator: RollEvaluator):
        self.config = synergies
        self.evaluator = evaluator
        self.syn_by_id = {s["id"]: s for s in synergies.get("special_synergies", [])}
        self.con_by_id = {c["id"]: c for c in synergies.get("special_conflicts", [])}

    def evaluate(self, character: dict, arma: dict) -> dict:
        parts: dict[str, int] = {}
        synergies: list[dict] = []
        conflicts: list[dict] = []

        parts["peso_forca"] = self.evaluator.peso_vs_forca(arma["peso"], character)
        parts["classe_arma"] = self._classe_arma(character, arma, synergies)
        parts["elemento_classe"] = self._elemento_classe(character, arma,
                                                         synergies, conflicts)
        parts["mana_habilidade"] = self._mana_habilidade(character, arma, conflicts)
        parts["alcance_tamanho"] = self._alcance_tamanho(character, arma, conflicts)

        if parts["peso_forca"] <= 20:
            conflicts.append(self.con_by_id["nao_levanta"])

        weights = self.config["compatibility"]["weights"]
        score = sum(parts[k] * weights[k] for k in weights)
        score += sum(s["bonus"] for s in synergies)
        score -= sum(c["penalty"] for c in conflicts)
        score = max(0, min(100, round(score)))

        result = {
            "compatibility_score": score,
            "parts": parts,
            "synergies": synergies,
            "conflicts": conflicts,
        }
        tier = self.evaluator.tier_for(score)
        result.update({"tier": tier["name"], "tier_label": tier["label"],
                       "tier_color": tier["color"], "sentiment": tier["sentiment"],
                       "intensity": tier["intensity"]})
        return result

    # ------------------------------------------------------------------- parts
    def _classe_arma(self, character: dict, arma: dict, synergies: list) -> int:
        preferidos = nf.tipos_preferidos_da_classe(character["classe"])
        if arma["tipo"] in preferidos and len(preferidos) < len(nf.LISTA_TIPOS_ARMA):
            synergies.append(self.syn_by_id["arma_da_classe"])
            return 90
        if len(preferidos) >= len(nf.LISTA_TIPOS_ARMA):
            return 60  # classe sem preferencia registrada no NF
        return 42

    def _elemento_classe(self, character: dict, arma: dict,
                         synergies: list, conflicts: list) -> int:
        rotulo = nf.classe_elemento(character["classe"])
        elemento_classe = CLASSE_ELEMENTO_MAP.get(rotulo)
        encantamento = arma.get("afinidade_elemento") or (arma.get("encantamentos") or [None])[0]
        elemento_arma = nf.ENCANTAMENTOS.get(encantamento, {}).get("elemento")
        if not elemento_classe or not elemento_arma:
            return 55
        if elemento_classe == elemento_arma:
            synergies.append(self.syn_by_id["elemento_da_classe"])
            return 94
        if (elemento_classe, elemento_arma) in ELEMENTOS_OPOSTOS:
            conflicts.append(self.con_by_id["elemento_oposto"])
            return 20
        return 55

    def _mana_habilidade(self, character: dict, arma: dict, conflicts: list) -> int:
        skill = arma.get("habilidade", "Nenhuma")
        if not skill or skill == "Nenhuma":
            return 60
        custo = nf.SKILL_DB.get(skill, {}).get("custo", 20)
        reserva = character["mana"] * 12  # mana 3-9 -> reserva ~36-108
        ratio = reserva / max(1.0, custo)
        if ratio < 1.2:
            conflicts.append(self.con_by_id["mana_insuficiente"])
            return max(5, round(ratio * 35))
        return min(96, round(45 + ratio * 12))

    def _alcance_tamanho(self, character: dict, arma: dict, conflicts: list) -> int:
        alcance = arma.get("comp_cabo", 0) + arma.get("comp_lamina", 0)
        if arma["tipo"] in ("Arco", "Arremesso", "Orbital", "Mágica"):
            return 65  # armas de distancia nao dependem do porte fisico
        score = self.evaluator.alcance_vs_tamanho(alcance, character["tamanho"])
        if alcance > character["tamanho"] * 100:
            conflicts.append(self.con_by_id["arma_gigante"])
        return score
