"""Typed exception hierarchy for ask-cli."""


class AskCLIError(Exception):
    """Base exception for all ask-cli errors.

    `hint` is the actionable suggestion shown under the error (PRD §10: problem +
    cause + suggestion); set it where the error is raised, since that is where the
    right advice is known.
    """

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class ConfigError(AskCLIError):
    """Raised for configuration loading or validation failures."""


class ProviderError(AskCLIError):
    """Raised when a provider API call fails."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: int | None = None,
        *,
        hint: str | None = None,
    ) -> None:
        super().__init__(message, hint=hint)
        self.provider = provider
        self.status_code = status_code


class ModelNotFoundError(ProviderError):
    """Raised when the requested model is not available."""


class HistoryError(AskCLIError):
    """Raised for conversation history I/O or format failures."""


class TemplateError(AskCLIError):
    """Raised when a template cannot be found or parsed."""


class AttachmentError(AskCLIError):
    """Raised when a file attachment cannot be read or resolved."""


class SavedResponseError(AskCLIError):
    """Raised when a saved response cannot be read, written, or found."""


class AgentError(AskCLIError):
    """Raised when the agent loop encounters an unrecoverable error."""
