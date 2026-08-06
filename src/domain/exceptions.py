class DomainValidationError(ValueError):
    """Los datos son legibles, pero incumplen una regla del negocio."""


class InputDataError(ValueError):
    """El archivo o JSON de entrada no puede interpretarse."""


class PersistenceError(RuntimeError):
    """La persistencia no pudo completarse de forma atómica."""
