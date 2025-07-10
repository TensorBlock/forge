class InvalidProviderException(Exception):
    """Exception raised when a provider is invalid."""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Provider {identifier} is invalid or failed to extract provider info from model_id {identifier}")


class ProviderAuthenticationException(Exception):
    """Exception raised when a provider authentication fails."""

    def __init__(self, provider_name: str, error: Exception):
        self.provider_name = provider_name
        self.error = error
        super().__init__(f"Provider {provider_name} authentication failed: {error}")


class BaseInvalidProviderSetupException(Exception):
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

class ProviderAPIException(Exception):
    """Exception raised when a provider API error occurs."""

    def __init__(self, provider_name: str, error_code: int, error_message: str):
        super().__init__(f"Provider {provider_name} API error: {error_code} {error_message}")
