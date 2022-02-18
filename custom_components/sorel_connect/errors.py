"""Errors for the SOREL connect component."""
from homeassistant.exceptions import HomeAssistantError


class SorelConnectException(HomeAssistantError):
	"""Base class for SOREL connect exceptions."""


class ServiceUnavailable(SorelConnectException):
	"""Service is not available."""


class InvalidCredentials(SorelConnectException):
	"""Invalid credentials."""
