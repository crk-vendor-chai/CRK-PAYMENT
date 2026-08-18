"""
Application configuration with environment variable support.

This module provides centralized configuration management for the payment gateway
application. All configurable values use environment variables with sensible defaults
for production and development environments.

Environment Variables:
    COMM_TIMEOUT: Device communication timeout in seconds (default: 30)
    SHUTDOWN_TIMEOUT: Graceful shutdown timeout in seconds (default: 10)
    API_HOST: API server bind address (default: 127.0.0.1)
    API_PORT: API server port (default: 8001)
    CAT_HOST: CAT device server bind address (default: 0.0.0.0)
    CAT_PORT: CAT device server port (default: 5000)
    LOG_LEVEL: Logging level (default: INFO)
    LOG_FORMAT: Log output format - 'json' or 'text' (default: text)

Usage:
    from config import settings
    
    timeout = settings.comm_timeout
    print(f"Using timeout: {timeout} seconds")
"""

import logging
import os
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Settings:
    """
    Application settings loaded from environment variables.
    
    All fields are immutable (frozen dataclass) to prevent accidental modification.
    Settings should be loaded once at startup and passed to components.
    """
    
    # Communication timeouts
    comm_timeout: float
    shutdown_timeout: float
    
    # API server configuration
    api_host: str
    api_port: int
    
    # CAT device server configuration
    cat_host: str
    cat_port: int
    
    # Logging configuration
    log_level: str
    log_format: Literal["json", "text"]
    
    @classmethod
    def from_env(cls) -> "Settings":
        """
        Load settings from environment variables with defaults.
        
        Returns:
            Settings instance with values from environment or defaults
            
        Raises:
            ValueError: If environment variable has invalid value
        """
        try:
            comm_timeout = float(os.getenv("COMM_TIMEOUT", "30.0"))
            if comm_timeout <= 0:
                raise ValueError("COMM_TIMEOUT must be positive")
        except ValueError as e:
            raise ValueError(f"Invalid COMM_TIMEOUT: {e}") from e
        
        try:
            shutdown_timeout = float(os.getenv("SHUTDOWN_TIMEOUT", "10.0"))
            if shutdown_timeout <= 0:
                raise ValueError("SHUTDOWN_TIMEOUT must be positive")
        except ValueError as e:
            raise ValueError(f"Invalid SHUTDOWN_TIMEOUT: {e}") from e
        
        api_host = os.getenv("API_HOST", "127.0.0.1")
        
        try:
            api_port = int(os.getenv("API_PORT", "8001"))
            if not (1 <= api_port <= 65535):
                raise ValueError("API_PORT must be between 1 and 65535")
        except ValueError as e:
            raise ValueError(f"Invalid API_PORT: {e}") from e
        
        cat_host = os.getenv("CAT_HOST", "0.0.0.0")
        
        try:
            cat_port = int(os.getenv("CAT_PORT", "5000"))
            if not (1 <= cat_port <= 65535):
                raise ValueError("CAT_PORT must be between 1 and 65535")
        except ValueError as e:
            raise ValueError(f"Invalid CAT_PORT: {e}") from e
        
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if log_level not in valid_levels:
            raise ValueError(
                f"Invalid LOG_LEVEL: {log_level}. Must be one of {valid_levels}"
            )
        
        log_format = os.getenv("LOG_FORMAT", "text").lower()
        if log_format not in ("json", "text"):
            raise ValueError(
                f"Invalid LOG_FORMAT: {log_format}. Must be 'json' or 'text'"
            )
        
        return cls(
            comm_timeout=comm_timeout,
            shutdown_timeout=shutdown_timeout,
            api_host=api_host,
            api_port=api_port,
            cat_host=cat_host,
            cat_port=cat_port,
            log_level=log_level,
            log_format=log_format,  # type: ignore
        )
    
    def configure_logging(self) -> None:
        """
        Configure Python logging based on settings.
        
        Sets up logging format (text or JSON) and level from configuration.
        Call this once at application startup.
        """
        log_level = getattr(logging, self.log_level)
        
        if self.log_format == "json":
            # JSON structured logging for production
            logging.basicConfig(
                level=log_level,
                format='{"timestamp":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","message":"%(message)s"}',
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        else:
            # Human-readable text format for development
            logging.basicConfig(
                level=log_level,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        
        # Reduce verbosity of third-party libraries
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


# Global settings instance - load once at module import
# Components should import and use this singleton
try:
    settings = Settings.from_env()
except ValueError as e:
    # Re-raise configuration errors with clear message
    raise RuntimeError(f"Failed to load configuration: {e}") from e


__all__ = ["settings", "Settings"]
