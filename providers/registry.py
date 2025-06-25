"""Model provider registry for managing available providers."""

import logging
import os
from typing import TYPE_CHECKING, Optional

from .base import ModelProvider, ProviderType

if TYPE_CHECKING:
    from tools.models import ToolModelCategory


class ModelProviderRegistry:
    """Registry for managing model providers."""

    _instance = None

    def __new__(cls):
        """Singleton pattern for registry."""
        if cls._instance is None:
            logging.debug("REGISTRY: Creating new registry instance")
            cls._instance = super().__new__(cls)
            # Initialize instance dictionaries on first creation
            cls._instance._providers = {}
            cls._instance._initialized_providers = {}
            logging.debug(f"REGISTRY: Created instance {cls._instance}")
        return cls._instance

    @classmethod
    def register_provider(cls, provider_type: ProviderType, provider_class: type[ModelProvider]) -> None:
        """Register a new provider class.

        Args:
            provider_type: Type of the provider (e.g., ProviderType.OPENAI)
            provider_class: Class that implements ModelProvider interface
        """
        instance = cls()
        instance._providers[provider_type] = provider_class

    @classmethod
    def get_provider(cls, provider_type: ProviderType, force_new: bool = False) -> Optional[ModelProvider]:
        """Get an initialized provider instance.

        Args:
            provider_type: Type of provider to get
            force_new: Force creation of new instance instead of using cached

        Returns:
            Initialized ModelProvider instance or None if not available
        """
        instance = cls()

        # Return cached instance if available and not forcing new
        if not force_new and provider_type in instance._initialized_providers:
            return instance._initialized_providers[provider_type]

        # Check if provider class is registered
        if provider_type not in instance._providers:
            return None

        # Get API key from environment
        api_key = cls._get_api_key_for_provider(provider_type)

        # Get provider class or factory function
        provider_class = instance._providers[provider_type]

        # Initialize provider with API key
        if not api_key:
            return None
        provider = provider_class(api_key=api_key)

        # Cache the instance
        instance._initialized_providers[provider_type] = provider

        return provider

    @classmethod
    def get_provider_for_model(cls, model_name: str) -> Optional[ModelProvider]:
        """Get provider instance for a specific model name.

        Provider priority order:
        1. OPENAI - OpenAI-compatible APIs (most direct and efficient)
        2. CUSTOM - For local/private models with specific endpoints

        Args:
            model_name: Name of the model (e.g., "gpt-4o", "o3-mini")

        Returns:
            ModelProvider instance that supports this model
        """
        logging.debug(f"get_provider_for_model called with model_name='{model_name}'")

        # Define explicit provider priority order
        # Only OpenAI-compatible APIs
        PROVIDER_PRIORITY_ORDER = [
            ProviderType.OPENAI,  # OpenAI compatible API access (includes custom endpoints)
        ]

        # Check providers in priority order
        instance = cls()
        logging.debug(f"Registry instance: {instance}")
        logging.debug(f"Available providers in registry: {list(instance._providers.keys())}")

        for provider_type in PROVIDER_PRIORITY_ORDER:
            if provider_type in instance._providers:
                logging.debug(f"Found {provider_type} in registry")
                # Get or create provider instance
                provider = cls.get_provider(provider_type)
                if provider and provider.validate_model_name(model_name):
                    logging.debug(f"{provider_type} validates model {model_name}")
                    return provider
                else:
                    logging.debug(f"{provider_type} does not validate model {model_name}")
            else:
                logging.debug(f"{provider_type} not found in registry")

        logging.debug(f"No provider found for model {model_name}")
        return None

    @classmethod
    def get_available_providers(cls) -> list[ProviderType]:
        """Get list of registered provider types."""
        instance = cls()
        return list(instance._providers.keys())

    @classmethod
    def get_available_models(cls, respect_restrictions: bool = True) -> dict[str, ProviderType]:
        """Get mapping of all available models to their providers.

        Args:
            respect_restrictions: If True, filter out models not allowed by restrictions

        Returns:
            Dict mapping model names to provider types
        """
        # Import here to avoid circular imports
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service() if respect_restrictions else None
        models: dict[str, ProviderType] = {}
        instance = cls()

        for provider_type in instance._providers:
            provider = cls.get_provider(provider_type)
            if not provider:
                continue

            try:
                available = provider.list_models(respect_restrictions=respect_restrictions)
            except NotImplementedError:
                logging.warning("Provider %s does not implement list_models", provider_type)
                continue

            for model_name in available:
                # =====================================================================================
                # CRITICAL: Prevent double restriction filtering (Fixed Issue #98)
                # =====================================================================================
                # Previously, both the provider AND registry applied restrictions, causing
                # double-filtering that resulted in "no models available" errors.
                #
                # Logic: If respect_restrictions=True, provider already filtered models,
                # so registry should NOT filter them again.
                # TEST COVERAGE: tests/test_provider_routing_bugs.py::TestOpenRouterAliasRestrictions
                # =====================================================================================
                if (
                    restriction_service
                    and not respect_restrictions  # Only filter if provider didn't already filter
                    and not restriction_service.is_allowed(provider_type, model_name)
                ):
                    logging.debug("Model %s filtered by restrictions", model_name)
                    continue
                models[model_name] = provider_type

        return models

    @classmethod
    def get_available_model_names(cls, provider_type: Optional[ProviderType] = None) -> list[str]:
        """Get list of available model names, optionally filtered by provider.

        This respects model restrictions automatically.

        Args:
            provider_type: Optional provider to filter by

        Returns:
            List of available model names
        """
        available_models = cls.get_available_models(respect_restrictions=True)

        if provider_type:
            # Filter by specific provider
            return [name for name, ptype in available_models.items() if ptype == provider_type]
        else:
            # Return all available models
            return list(available_models.keys())

    @classmethod
    def _get_api_key_for_provider(cls, provider_type: ProviderType) -> Optional[str]:
        """Get API key for a provider from environment variables.

        Args:
            provider_type: Provider type to get API key for

        Returns:
            API key string or None if not found
        """
        key_mapping = {
            ProviderType.OPENAI: "OPENAI_API_KEY",
        }

        env_var = key_mapping.get(provider_type)
        if not env_var:
            return None

        return os.getenv(env_var)

    @classmethod
    def get_preferred_fallback_model(cls, tool_category: Optional["ToolModelCategory"] = None) -> str:
        """Get the preferred fallback model based on available API keys and tool category.

        This method checks which providers have valid API keys and returns
        a sensible default model for auto mode fallback situations.

        Takes into account model restrictions when selecting fallback models.

        Args:
            tool_category: Optional category to influence model selection

        Returns:
            Model name string for fallback use
        """
        # Import here to avoid circular import
        from tools.models import ToolModelCategory

        # Get available models respecting restrictions
        available_models = cls.get_available_models(respect_restrictions=True)

        # Group by provider
        openai_models = [m for m, p in available_models.items() if p == ProviderType.OPENAI]

        openai_available = bool(openai_models)

        if tool_category == ToolModelCategory.EXTENDED_REASONING:
            # Prefer thinking-capable models for deep reasoning tools
            if openai_available and "o3" in openai_models:
                return "o3"  # O3 for deep reasoning
            elif openai_available and "o3-pro" in openai_models:
                return "o3-pro"  # O3-Pro for complex reasoning
            elif openai_available and "deepseek-r1" in openai_models:
                return "deepseek-r1"  # DeepSeek R1 with thinking mode
            elif openai_available and openai_models:
                # Fall back to any available OpenAI model
                return openai_models[0]
            else:
                # Fallback to a default OpenAI-compatible model
                return "gpt-4"

        elif tool_category == ToolModelCategory.FAST_RESPONSE:
            # Prefer fast, cost-efficient models
            if openai_available and "o4-mini" in openai_models:
                return "o4-mini"  # Latest, fast and efficient
            elif openai_available and "o3-mini" in openai_models:
                return "o3-mini"  # Second choice
            elif openai_available and "flash" in openai_models:
                return "flash"  # Gemini Flash for speed
            elif openai_available and "gpt-4o-mini" in openai_models:
                return "gpt-4o-mini"  # Fast GPT-4 variant
            elif openai_available and openai_models:
                # Fall back to any available OpenAI model
                return openai_models[0]
            else:
                # Default to a fast OpenAI-compatible model
                return "gpt-4o-mini"

        # BALANCED or no category specified - use existing balanced logic
        if openai_available and "o4-mini" in openai_models:
            return "o4-mini"  # Latest balanced performance/cost
        elif openai_available and "o3-mini" in openai_models:
            return "o3-mini"  # Second choice
        elif openai_available and "pro" in openai_models:
            return "pro"  # Gemini Pro for balanced performance
        elif openai_available and "gpt-4o" in openai_models:
            return "gpt-4o"  # Balanced GPT-4 variant
        elif openai_available and openai_models:
            return openai_models[0]
        else:
            # No models available due to restrictions - check if any providers exist
            if not available_models:
                # This might happen if all models are restricted
                logging.warning("No models available due to restrictions")
            # Return a reasonable default for backward compatibility
            return "gpt-4o"

    @classmethod
    def _find_extended_thinking_model(cls) -> Optional[str]:
        """Find a model suitable for extended reasoning from custom/openrouter providers.

        Returns:
            Model name if found, None otherwise
        """
        # Check OpenAI provider for thinking models
        openai_provider = cls.get_provider(ProviderType.OPENAI)
        if openai_provider:
            try:
                # For OpenAI-compatible providers, look for models that support extended thinking
                models = openai_provider.list_models(respect_restrictions=True)
                # Prefer models known for deep reasoning
                preferred_models = [
                    "deepseek-r1", "o3", "o3-pro", "gpt-4o", "claude-3-opus", "claude-3-sonnet",
                    "gemini-2.5-pro", "llama-3.1-70b", "mixtral-8x7b"
                ]
                for model in preferred_models:
                    if model in models:
                        return model
                # Fallback to first available model
                if models:
                    return models[0]
            except Exception:
                pass

        return None

    @classmethod
    def get_available_providers_with_keys(cls) -> list[ProviderType]:
        """Get list of provider types that have valid API keys.

        Returns:
            List of ProviderType values for providers with valid API keys
        """
        available = []
        instance = cls()
        for provider_type in instance._providers:
            if cls.get_provider(provider_type) is not None:
                available.append(provider_type)
        return available

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached provider instances."""
        instance = cls()
        instance._initialized_providers.clear()

    @classmethod
    def unregister_provider(cls, provider_type: ProviderType) -> None:
        """Unregister a provider (mainly for testing)."""
        instance = cls()
        instance._providers.pop(provider_type, None)
        instance._initialized_providers.pop(provider_type, None)
