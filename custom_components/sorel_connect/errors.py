"""Errors for the SOREL Connect component."""
from homeassistant.exceptions import HomeAssistantError


class SorelConnectException(HomeAssistantError):
	"""Base class for SOREL Connect exceptions."""


class ServiceUnavailable(SorelConnectException):
	"""Service is not available."""


class InvalidCredentials(SorelConnectException):
	"""Invalid credentials."""
