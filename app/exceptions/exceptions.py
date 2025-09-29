class BaseForgeException(Exception):
    pass

class InvalidProviderException(BaseForgeException):
    """Exception raised when a provider is invalid."""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Provider {identifier} is invalid or failed to extract provider info from model_id {identifier}")


class ProviderAuthenticationException(BaseForgeException):
    """Exception raised when a provider authentication fails."""

    def __init__(self, provider_name: str, error: Exception):
        self.provider_name = provider_name
        self.error = error
        super().__init__(f"Provider {provider_name} authentication failed: {error}")


class BaseInvalidProviderSetupException(BaseForgeException):
    """Exception raised when a provider setup is invalid."""

    def __init__(self, provider_name: str, error: Exception):
        self.provider_name = provider_name
        self.error = error
        super().__init__(f"Provider {provider_name} setup is invalid: {error}")

class InvalidProviderConfigException(BaseInvalidProviderSetupException):
    """Exception raised when a provider config is invalid."""

    def __init__(self, provider_name: str, error: Exception):
        super().__init__(provider_name, error)

class InvalidProviderAPIKeyException(BaseInvalidProviderSetupException):
    """Exception raised when a provider API key is invalid."""

    def __init__(self, provider_name: str, error: Exception):
        super().__init__(provider_name, error)

class ProviderAPIException(BaseForgeException):
    """Exception raised when a provider API error occurs."""

    def __init__(self, provider_name: str, error_code: int, error_message: str):
        """Initialize the exception and persist error details for downstream handling.

        Many parts of the codebase (e.g. the Claude Code routes) rely on the
        presence of the ``error_code`` and ``error_message`` attributes to
        construct a well-formed error response.  Without setting these instance
        attributes an ``AttributeError`` is raised when the exception is caught
        and introspected, masking the original provider failure.  Persisting the
        values here guarantees that the original error information is available
        to any error-handling middleware.
        """
        self.provider_name = provider_name
        self.error_code = error_code
        self.error_message = error_message

        # Compose the base exception message for logging / debugging purposes.
        super().__init__(
            f"Provider {provider_name} API error: {error_code} {error_message}"
        )


class BaseInvalidRequestException(BaseForgeException):
    """Exception raised when a request is invalid."""

    def __init__(self, provider_name: str, error: Exception):
        self.provider_name = provider_name
        self.error = error
        super().__init__(f"Provider {provider_name} request is invalid: {error}")

class InvalidCompletionRequestException(BaseInvalidRequestException):
    """Exception raised when a completion request is invalid."""

    def __init__(self, provider_name: str, error: Exception):
        self.provider_name = provider_name
        self.error = error
        super().__init__(self.provider_name, self.error)

class InvalidEmbeddingsRequestException(BaseInvalidRequestException):
    """Exception raised when a embeddings request is invalid."""

    def __init__(self, provider_name: str, error: Exception):
        self.provider_name = provider_name
        self.error = error
        super().__init__(self.provider_name, self.error)

class BaseInvalidForgeKeyException(BaseForgeException):
    """Exception raised when a Forge key is invalid."""

    def __init__(self, error: Exception):
        self.error = error
        super().__init__(f"Forge key is invalid: {error}")


class InvalidForgeKeyException(BaseInvalidForgeKeyException):
    """Exception raised when a Forge key is invalid."""
    def __init__(self, error: Exception):
        super().__init__(error)