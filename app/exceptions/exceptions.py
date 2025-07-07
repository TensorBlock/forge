class InvalidProviderException(Exception):
    """Exception raised when a provider is invalid."""

    def __init__(self, identifier: str):
        self.identifier = identifier
        super().__init__(f"Provider {identifier} is invalid or failed to extract provider info from model_id {identifier}")