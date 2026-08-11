"""Contratos leves compartilhados pelos subsistemas de inteligência artificial."""


def obter_brain(entidade):
    """Retorna o controlador atual de IA ou o alias legado, quando presente."""
    if entidade is None:
        return None
    return getattr(entidade, "brain", None) or getattr(entidade, "ai", None)
