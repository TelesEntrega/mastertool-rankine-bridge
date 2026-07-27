"""Exceções da camada externa."""


class BridgeError(Exception):
    """Erro base do mastertool-bridge."""


class ExportNotFoundError(BridgeError):
    """Diretório de export inexistente ou sem manifesto."""


class ValidationError(BridgeError):
    """Export ou change set inválido."""

    def __init__(self, message: str, issues: list[str] | None = None):
        super().__init__(message)
        self.issues = issues or []


class SafetyPolicyViolation(BridgeError):
    """Operação bloqueada pela política de segurança (fail closed)."""


class NotImplementedPhaseError(BridgeError):
    """Funcionalidade pertence a uma fase ainda não liberada."""


class ProjectIndexError(BridgeError):
    """Erro base da API pública ProjectIndex."""


class InvalidIndexError(ProjectIndexError):
    """Diretório de índice ausente, incompleto, ou com JSON corrompido."""


class UnsupportedSchemaError(ProjectIndexError):
    """Reservada para quando o índice carregar um marcador de versão de
    schema incompatível. NENHUM artefato JSON gerado hoje por
    build_static_index carrega um campo de versão de schema explícito --
    esta exceção existe como ponto de extensão futuro (documente isso
    honestamente no docstring), não é levantada por nenhum código atual."""
