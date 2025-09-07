# pidrive/exceptions.py

class StorageRootViolation(PermissionError):
    """Raised when a path is outside the configured storage root or deletes a protected path."""
