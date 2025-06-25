"""OpenAI model provider implementation."""

import base64
import ipaddress
import json
import logging
import os
import time
from typing import Optional
from urllib.parse import urlparse

from openai import OpenAI

from .base import (
    ModelCapabilities,
    ModelProvider,
    ModelResponse,
    ProviderType,
    create_temperature_constraint,
)

logger = logging.getLogger(__name__)





class OpenAIModelProvider(ModelProvider):
    """OpenAI-compatible API provider supporting both official OpenAI models and custom models.

    This provider supports:
    - Direct OpenAI API
    - OpenRouter
    - Any other OpenAI-compatible endpoint
    """

    DEFAULT_HEADERS = {}
    FRIENDLY_NAME = "OpenAI Compatible"

    # Base OpenAI model configurations
    _BASE_MODELS = {
        "o3": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3",
            friendly_name="OpenAI (O3)",
            context_window=200_000,  # 200K tokens
            max_output_tokens=65536,  # 64K max output tokens
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # O3 models support vision
            max_image_size_mb=20.0,  # 20MB per OpenAI docs
            supports_temperature=False,  # O3 models don't accept temperature parameter
            temperature_constraint=create_temperature_constraint("fixed"),
            description="Strong reasoning (200K context) - Logical problems, code generation, systematic analysis",
            aliases=[],
        ),
        "o3-mini": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3-mini",
            friendly_name="OpenAI (O3-mini)",
            context_window=200_000,  # 200K tokens
            max_output_tokens=65536,  # 64K max output tokens
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # O3 models support vision
            max_image_size_mb=20.0,  # 20MB per OpenAI docs
            supports_temperature=False,  # O3 models don't accept temperature parameter
            temperature_constraint=create_temperature_constraint("fixed"),
            description="Fast O3 variant (200K context) - Balanced performance/speed, moderate complexity",
            aliases=["o3mini", "o3-mini"],
        ),
        "o3-pro": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o3-pro",
            friendly_name="OpenAI (O3-Pro)",
            context_window=200_000,  # 200K tokens
            max_output_tokens=65536,  # 64K max output tokens
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # O3 models support vision
            max_image_size_mb=20.0,  # 20MB per OpenAI docs
            supports_temperature=False,  # O3 models don't accept temperature parameter
            temperature_constraint=create_temperature_constraint("fixed"),
            description="Professional-grade reasoning (200K context) - EXTREMELY EXPENSIVE: Only for the most complex problems requiring universe-scale complexity analysis OR when the user explicitly asks for this model. Use sparingly for critical architectural decisions or exceptionally complex debugging that other models cannot handle.",
            aliases=["o3-pro"],
        ),
        "o4-mini": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="o4-mini",
            friendly_name="OpenAI (O4-mini)",
            context_window=200_000,  # 200K tokens
            max_output_tokens=65536,  # 64K max output tokens
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # O4 models support vision
            max_image_size_mb=20.0,  # 20MB per OpenAI docs
            supports_temperature=False,  # O4 models don't accept temperature parameter
            temperature_constraint=create_temperature_constraint("fixed"),
            description="Latest reasoning model (200K context) - Optimized for shorter contexts, rapid reasoning",
            aliases=["mini", "o4mini", "o4-mini"],
        ),
        "gpt-4.1": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="gpt-4.1",
            friendly_name="OpenAI (GPT 4.1)",
            context_window=1_000_000,  # 1M tokens
            max_output_tokens=32_768,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # GPT-4.1 supports vision
            max_image_size_mb=20.0,  # 20MB per OpenAI docs
            supports_temperature=True,  # Regular models accept temperature parameter
            temperature_constraint=create_temperature_constraint("range"),
            description="GPT-4.1 (1M context) - Advanced reasoning model with large context window",
            aliases=["gpt4.1"],
        ),
        "gemini-2.5-pro": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="gemini-2.5-pro",
            friendly_name="Gemini (Pro 2.5)",
            context_window=1_048_576,  # 1M tokens
            max_output_tokens=65_536,
            supports_extended_thinking=True,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # Vision capability
            max_image_size_mb=32.0,  # Higher limit for Pro model
            supports_temperature=True,
            temperature_constraint=create_temperature_constraint("range"),
            max_thinking_tokens=32768,  # Max thinking tokens for Pro model
            description="Deep reasoning + thinking mode (1M context) - Complex problems, architecture, deep analysis",
            aliases=["pro", "gemini pro", "gemini-pro"],
        ),
        "gemini-2.5-flash": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="gemini-2.5-flash",
            friendly_name="Gemini (Flash 2.5)",
            context_window=1_048_576,  # 1M tokens
            max_output_tokens=65_536,
            supports_extended_thinking=True,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=True,
            supports_images=True,  # Vision capability
            max_image_size_mb=20.0,  # Conservative 20MB limit for reliability
            supports_temperature=True,
            temperature_constraint=create_temperature_constraint("range"),
            max_thinking_tokens=24576,  # Flash 2.5 thinking budget limit
            description="Ultra-fast (1M context) - Quick analysis, simple queries, rapid iterations",
            aliases=["flash", "flash2.5"],
        ),
        "grok-3": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="grok-3",
            friendly_name="X.AI (Grok 3)",
            context_window=131_072,  # 131K tokens
            max_output_tokens=131072,
            supports_extended_thinking=False,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=False,  # Assuming GROK doesn't have JSON mode yet
            supports_images=False,  # Assuming GROK is text-only for now
            max_image_size_mb=0.0,
            supports_temperature=True,
            temperature_constraint=create_temperature_constraint("range"),
            description="GROK-3 (131K context) - Advanced reasoning model from X.AI, excellent for complex analysis",
            aliases=["grok", "grok3"],
        ),
        "grok-3-deepsearch": ModelCapabilities(
            provider=ProviderType.OPENAI,
            model_name="grok-3-deepsearch",
            friendly_name="X.AI (Grok 3 deepsearch)",
            context_window=1_048_576, 
            max_output_tokens=1_048_576,
            supports_extended_thinking=True,
            supports_system_prompts=True,
            supports_streaming=True,
            supports_function_calling=True,
            supports_json_mode=False,  # Assuming GROK doesn't have JSON mode yet
            supports_images=False,  # Assuming GROK is text-only for now
            max_image_size_mb=0.0,
            supports_temperature=True,
            temperature_constraint=create_temperature_constraint("range"),
            description="grok-3-deepsearch (1M context) - Higher performance variant, faster processing but more expensive",
            aliases=["grok3r"],
        ),
    }

    # All supported models (no longer needs dynamic loading)
    SUPPORTED_MODELS = _BASE_MODELS



    def __init__(self, api_key: str, base_url: str = None, **kwargs):
        """Initialize OpenAI provider with API key and optional base URL.

        Args:
            api_key: API key for authentication
            base_url: Base URL for the API endpoint
            **kwargs: Additional configuration options including timeout
        """

        # Set base URL from environment variable or parameter
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

        # Initialize parent class
        super().__init__(api_key, **kwargs)

        # Initialize OpenAI-compatible provider attributes
        self._client = None
        self.organization = kwargs.get("organization")
        self.allowed_models = self._parse_allowed_models()

        # Configure timeouts - especially important for custom/local endpoints
        self.timeout_config = self._configure_timeouts(**kwargs)

        # Validate base URL for security
        if self.base_url:
            self._validate_base_url()

        # Warn if using external URL without authentication
        if self.base_url and not self._is_localhost_url() and not api_key:
            logging.warning(
                f"Using external URL '{self.base_url}' without API key. "
                "This may be insecure. Consider setting an API key for authentication."
            )

    def _parse_allowed_models(self) -> Optional[set[str]]:
        """Parse allowed models from environment variable.

        Returns:
            Set of allowed model names (lowercase) or None if not configured
        """
        # Get provider-specific allowed models
        provider_type = self.get_provider_type().value.upper()
        env_var = f"{provider_type}_ALLOWED_MODELS"
        models_str = os.getenv(env_var, "")

        if models_str:
            # Parse and normalize to lowercase for case-insensitive comparison
            models = {m.strip().lower() for m in models_str.split(",") if m.strip()}
            if models:
                logging.info(f"Configured allowed models for {self.FRIENDLY_NAME}: {sorted(models)}")
                return models

        # Log info if no allow-list configured for proxy providers
        if self.get_provider_type() != ProviderType.OPENAI:
            logging.info(
                f"Model allow-list not configured for {self.FRIENDLY_NAME} - all models permitted. "
                f"To restrict access, set {env_var} with comma-separated model names."
            )

        return None

    def _configure_timeouts(self, **kwargs):
        """Configure timeout settings based on provider type and custom settings.

        Custom URLs and local models often need longer timeouts due to:
        - Network latency on local networks
        - Extended thinking models taking longer to respond
        - Local inference being slower than cloud APIs

        Returns:
            httpx.Timeout object with appropriate timeout settings
        """
        import httpx

        # Default timeouts - more generous for custom/local endpoints
        default_connect = 30.0  # 30 seconds for connection (vs OpenAI's 5s)
        default_read = 600.0  # 10 minutes for reading (same as OpenAI default)
        default_write = 600.0  # 10 minutes for writing
        default_pool = 600.0  # 10 minutes for pool

        # For custom/local URLs, use even longer timeouts
        if self.base_url and self._is_localhost_url():
            default_connect = 60.0  # 1 minute for local connections
            default_read = 1800.0  # 30 minutes for local models (extended thinking)
            default_write = 1800.0  # 30 minutes for local models
            default_pool = 1800.0  # 30 minutes for local models
            logging.info(f"Using extended timeouts for local endpoint: {self.base_url}")
        elif self.base_url:
            default_connect = 45.0  # 45 seconds for custom remote endpoints
            default_read = 900.0  # 15 minutes for custom remote endpoints
            default_write = 900.0  # 15 minutes for custom remote endpoints
            default_pool = 900.0  # 15 minutes for custom remote endpoints
            logging.info(f"Using extended timeouts for custom endpoint: {self.base_url}")

        # Allow override via kwargs or environment variables in future, for now...
        connect_timeout = kwargs.get("connect_timeout", float(os.getenv("CUSTOM_CONNECT_TIMEOUT", default_connect)))
        read_timeout = kwargs.get("read_timeout", float(os.getenv("CUSTOM_READ_TIMEOUT", default_read)))
        write_timeout = kwargs.get("write_timeout", float(os.getenv("CUSTOM_WRITE_TIMEOUT", default_write)))
        pool_timeout = kwargs.get("pool_timeout", float(os.getenv("CUSTOM_POOL_TIMEOUT", default_pool)))

        timeout = httpx.Timeout(connect=connect_timeout, read=read_timeout, write=write_timeout, pool=pool_timeout)

        logging.debug(
            f"Configured timeouts - Connect: {connect_timeout}s, Read: {read_timeout}s, "
            f"Write: {write_timeout}s, Pool: {pool_timeout}s"
        )

        return timeout

    def _is_localhost_url(self) -> bool:
        """Check if the base URL points to localhost or local network.

        Returns:
            True if URL is localhost or local network, False otherwise
        """
        if not self.base_url:
            return False

        try:
            parsed = urlparse(self.base_url)
            hostname = parsed.hostname

            # Check for common localhost patterns
            if hostname in ["localhost", "127.0.0.1", "::1"]:
                return True

            # Check for private network ranges (local network)
            if hostname:
                try:
                    ip = ipaddress.ip_address(hostname)
                    return ip.is_private or ip.is_loopback
                except ValueError:
                    # Not an IP address, might be a hostname
                    pass

            return False
        except Exception:
            return False

    def _validate_base_url(self) -> None:
        """Validate base URL for security (SSRF protection).

        Raises:
            ValueError: If URL is invalid or potentially unsafe
        """
        if not self.base_url:
            return

        try:
            parsed = urlparse(self.base_url)

            # Check URL scheme - only allow http/https
            if parsed.scheme not in ("http", "https"):
                raise ValueError(f"Invalid URL scheme: {parsed.scheme}. Only http/https allowed.")

            # Check hostname exists
            if not parsed.hostname:
                raise ValueError("URL must include a hostname")

            # Check port is valid (if specified)
            port = parsed.port
            if port is not None and (port < 1 or port > 65535):
                raise ValueError(f"Invalid port number: {port}. Must be between 1 and 65535.")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            raise ValueError(f"Invalid base URL '{self.base_url}': {str(e)}")

    @property
    def client(self):
        """Lazy initialization of OpenAI client with security checks and timeout configuration."""
        if self._client is None:
            import httpx

            # Temporarily disable proxy environment variables to prevent httpx from detecting them
            original_env = {}
            proxy_env_vars = ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]

            for var in proxy_env_vars:
                if var in os.environ:
                    original_env[var] = os.environ[var]
                    del os.environ[var]

            try:
                # Create a custom httpx client that explicitly avoids proxy parameters
                timeout_config = (
                    self.timeout_config
                    if hasattr(self, "timeout_config") and self.timeout_config
                    else httpx.Timeout(30.0)
                )

                # Create httpx client with minimal config to avoid proxy conflicts
                # Note: proxies parameter was removed in httpx 0.28.0
                http_client = httpx.Client(
                    timeout=timeout_config,
                    follow_redirects=True,
                )

                # Keep client initialization minimal to avoid proxy parameter conflicts
                client_kwargs = {
                    "api_key": self.api_key,
                    "http_client": http_client,
                }

                if self.base_url:
                    client_kwargs["base_url"] = self.base_url

                if self.organization:
                    client_kwargs["organization"] = self.organization

                # Add default headers if any
                if self.DEFAULT_HEADERS:
                    client_kwargs["default_headers"] = self.DEFAULT_HEADERS.copy()

                logging.debug(f"OpenAI client initialized with custom httpx client and timeout: {timeout_config}")

                # Create OpenAI client with custom httpx client
                self._client = OpenAI(**client_kwargs)

            except Exception as e:
                # If all else fails, try absolute minimal client without custom httpx
                logging.warning(f"Failed to create client with custom httpx, falling back to minimal config: {e}")
                try:
                    minimal_kwargs = {"api_key": self.api_key}
                    if self.base_url:
                        minimal_kwargs["base_url"] = self.base_url
                    self._client = OpenAI(**minimal_kwargs)
                except Exception as fallback_error:
                    logging.error(f"Even minimal OpenAI client creation failed: {fallback_error}")
                    raise
            finally:
                # Restore original proxy environment variables
                for var, value in original_env.items():
                    os.environ[var] = value

        return self._client

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.OPENAI

    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is supported."""
        # Check against allowed models if configured
        if self.allowed_models:
            return model_name.lower() in self.allowed_models

        # Check against supported models
        resolved_name = self._resolve_model_name(model_name)
        return resolved_name in self.SUPPORTED_MODELS

    def generate_content(
        self,
        prompt: str,
        model_name: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_output_tokens: Optional[int] = None,
        images: Optional[list[str]] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using the OpenAI-compatible API.

        Args:
            prompt: User prompt to send to the model
            model_name: Name of the model to use
            system_prompt: Optional system prompt for model behavior
            temperature: Sampling temperature
            max_output_tokens: Maximum tokens to generate
            **kwargs: Additional provider-specific parameters

        Returns:
            ModelResponse with generated content and metadata
        """
        # Resolve model alias before processing
        resolved_model_name = self._resolve_model_name(model_name)

        # Validate model name against allow-list
        if not self.validate_model_name(model_name):
            raise ValueError(f"Model '{model_name}' not in allowed models list. Allowed models: {self.allowed_models}")

        # Get effective temperature for this model
        effective_temperature = self.get_effective_temperature(resolved_model_name, temperature)

        # Only validate if temperature is not None (meaning the model supports it)
        if effective_temperature is not None:
            # Validate parameters with the effective temperature
            self.validate_parameters(resolved_model_name, effective_temperature)

        # Prepare messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Prepare user message with text and potentially images
        user_content = []
        user_content.append({"type": "text", "text": prompt})

        # Add images if provided and model supports vision
        if images and self._supports_vision(resolved_model_name):
            for image_path in images:
                try:
                    image_content = self._process_image(image_path)
                    if image_content:
                        user_content.append(image_content)
                except Exception as e:
                    logging.warning(f"Failed to process image {image_path}: {e}")
                    # Continue with other images and text
                    continue
        elif images and not self._supports_vision(resolved_model_name):
            logging.warning(f"Model {resolved_model_name} does not support images, ignoring {len(images)} image(s)")

        # Add user message
        if len(user_content) == 1:
            # Only text content, use simple string format for compatibility
            messages.append({"role": "user", "content": prompt})
        else:
            # Text + images, use content array format
            messages.append({"role": "user", "content": user_content})

        # Prepare completion parameters
        completion_params = {
            "model": resolved_model_name,
            "messages": messages,
        }

        # Check model capabilities once to determine parameter support
        resolved_model = resolved_model_name

        # Use the effective temperature we calculated earlier
        if effective_temperature is not None:
            completion_params["temperature"] = effective_temperature
            supports_temperature = True
        else:
            # Model doesn't support temperature
            supports_temperature = False

        # Add max tokens if specified and model supports it
        # O3/O4 models that don't support temperature also don't support max_tokens
        if max_output_tokens and supports_temperature:
            completion_params["max_tokens"] = max_output_tokens

        # Add any additional OpenAI-specific parameters
        # Use capabilities to filter parameters for reasoning models
        for key, value in kwargs.items():
            if key in ["top_p", "frequency_penalty", "presence_penalty", "seed", "stop", "stream"]:
                # Reasoning models (those that don't support temperature) also don't support these parameters
                if not supports_temperature and key in ["top_p", "frequency_penalty", "presence_penalty"]:
                    continue  # Skip unsupported parameters for reasoning models
                completion_params[key] = value

        # Check if this is o3-pro and needs the responses endpoint
        if resolved_model == "o3-pro":
            # This model requires the /v1/responses endpoint
            # If it fails, we should not fall back to chat/completions
            return self._generate_with_responses_endpoint(
                model_name=resolved_model,
                messages=messages,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                **kwargs,
            )

        # Retry logic with progressive delays
        max_retries = 4  # Total of 4 attempts
        retry_delays = [1, 3, 5, 8]  # Progressive delays: 1s, 3s, 5s, 8s

        last_exception = None

        for attempt in range(max_retries):
            try:
                # Generate completion
                response = self.client.chat.completions.create(**completion_params)

                # Extract content and usage with proper null checks
                if not response.choices or len(response.choices) == 0:
                    raise RuntimeError("No choices returned in API response")

                choice = response.choices[0]
                if not choice.message:
                    raise RuntimeError("No message in API response choice")

                content = choice.message.content or ""
                usage = self._extract_usage(response)

                return ModelResponse(
                    content=content,
                    usage=usage,
                    model_name=model_name,
                    friendly_name=self.FRIENDLY_NAME,
                    provider=self.get_provider_type(),
                    metadata={
                        "finish_reason": choice.finish_reason,
                        "model": getattr(response, "model", model_name),  # Actual model used
                        "id": getattr(response, "id", ""),
                        "created": getattr(response, "created", 0),
                    },
                )

            except Exception as e:
                last_exception = e

                # Check if this is a retryable error using structured error codes
                is_retryable = self._is_error_retryable(e)

                # If this is the last attempt or not retryable, give up
                if attempt == max_retries - 1 or not is_retryable:
                    break

                # Get progressive delay
                delay = retry_delays[attempt]

                # Log retry attempt
                logging.warning(
                    f"{self.FRIENDLY_NAME} error for model {model_name}, attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {delay}s..."
                )
                time.sleep(delay)

        # If we get here, all retries failed
        actual_attempts = attempt + 1  # Convert from 0-based index to human-readable count
        error_msg = f"{self.FRIENDLY_NAME} API error for model {model_name} after {actual_attempts} attempt{'s' if actual_attempts > 1 else ''}: {str(last_exception)}"
        logging.error(error_msg)
        raise RuntimeError(error_msg) from last_exception

    def count_tokens(self, text: str, model_name: str) -> int:
        """Count tokens for the given text.

        Uses a layered approach:
        1. Try provider-specific token counting endpoint
        2. Try tiktoken for known model families
        3. Fall back to character-based estimation

        Args:
            text: Text to count tokens for
            model_name: Model name for tokenizer selection

        Returns:
            Estimated token count
        """
        # 1. Check if provider has a remote token counting endpoint
        if hasattr(self, "count_tokens_remote"):
            try:
                return self.count_tokens_remote(text, model_name)
            except Exception as e:
                logging.debug(f"Remote token counting failed: {e}")

        # 2. Try tiktoken for known models
        try:
            import tiktoken

            # Try to get encoding for the specific model
            try:
                encoding = tiktoken.encoding_for_model(model_name)
            except KeyError:
                # Try common encodings based on model patterns
                if "gpt-4" in model_name or "gpt-3.5" in model_name:
                    encoding = tiktoken.get_encoding("cl100k_base")
                else:
                    encoding = tiktoken.get_encoding("cl100k_base")  # Default

            return len(encoding.encode(text))

        except (ImportError, Exception) as e:
            logging.debug(f"Tiktoken not available or failed: {e}")

        # 3. Fall back to character-based estimation
        logging.warning(
            f"No specific tokenizer available for '{model_name}'. "
            "Using character-based estimation (~4 chars per token)."
        )
        return len(text) // 4

    def validate_parameters(self, model_name: str, temperature: float, **kwargs) -> None:
        """Validate model parameters.

        For proxy providers, this may use generic capabilities.

        Args:
            model_name: Model to validate for
            temperature: Temperature to validate
            **kwargs: Additional parameters to validate
        """
        try:
            capabilities = self.get_capabilities(model_name)

            # Check if we're using generic capabilities
            if hasattr(capabilities, "_is_generic"):
                logging.debug(
                    f"Using generic parameter validation for {model_name}. Actual model constraints may differ."
                )

            # Validate temperature using parent class method
            super().validate_parameters(model_name, temperature, **kwargs)

        except Exception as e:
            # For proxy providers, we might not have accurate capabilities
            # Log warning but don't fail
            logging.warning(f"Parameter validation limited for {model_name}: {e}")

    def _extract_usage(self, response) -> dict[str, int]:
        """Extract token usage from OpenAI response.

        Args:
            response: OpenAI API response object

        Returns:
            Dictionary with usage statistics
        """
        usage = {}

        if hasattr(response, "usage") and response.usage:
            # Safely extract token counts with None handling
            usage["input_tokens"] = getattr(response.usage, "prompt_tokens", 0) or 0
            usage["output_tokens"] = getattr(response.usage, "completion_tokens", 0) or 0
            usage["total_tokens"] = getattr(response.usage, "total_tokens", 0) or 0

        return usage

    def supports_thinking_mode(self, model_name: str) -> bool:
        """Check if the model supports extended thinking mode.

        Default is False for OpenAI-compatible providers.
        """
        return False

    def _supports_vision(self, model_name: str) -> bool:
        """Check if the model supports vision (image processing).

        Default implementation for OpenAI-compatible providers.
        Subclasses should override with specific model support.
        """
        # Common vision-capable models - only include models that actually support images
        vision_models = {
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4-vision-preview",
            "gpt-4.1",  # GPT-4.1 supports vision
            "o3",
            "o3-mini",
            "o3-pro",
            "o4-mini",
            # Note: Claude models would be handled by a separate provider
        }
        supports = model_name.lower() in vision_models
        logging.debug(f"Model '{model_name}' vision support: {supports}")
        return supports

    def _is_error_retryable(self, error: Exception) -> bool:
        """Determine if an error should be retried based on structured error codes.

        Uses OpenAI API error structure instead of text pattern matching for reliability.

        Args:
            error: Exception from OpenAI API call

        Returns:
            True if error should be retried, False otherwise
        """
        error_str = str(error).lower()

        # Check for 429 errors first - these need special handling
        if "429" in error_str:
            # Try to extract structured error information
            error_type = None
            error_code = None

            # Parse structured error from OpenAI API response
            # Format: "Error code: 429 - {'error': {'type': 'tokens', 'code': 'rate_limit_exceeded', ...}}"
            try:
                import ast
                import json
                import re

                # Extract JSON part from error string using regex
                # Look for pattern: {...} (from first { to last })
                json_match = re.search(r"\{.*\}", str(error))
                if json_match:
                    json_like_str = json_match.group(0)

                    # First try: parse as Python literal (handles single quotes safely)
                    try:
                        error_data = ast.literal_eval(json_like_str)
                    except (ValueError, SyntaxError):
                        # Fallback: try JSON parsing with simple quote replacement
                        # (for cases where it's already valid JSON or simple replacements work)
                        json_str = json_like_str.replace("'", '"')
                        error_data = json.loads(json_str)

                    if "error" in error_data:
                        error_info = error_data["error"]
                        error_type = error_info.get("type")
                        error_code = error_info.get("code")

            except (json.JSONDecodeError, ValueError, SyntaxError, AttributeError):
                # Fall back to checking hasattr for OpenAI SDK exception objects
                if hasattr(error, "response") and hasattr(error.response, "json"):
                    try:
                        response_data = error.response.json()
                        if "error" in response_data:
                            error_info = response_data["error"]
                            error_type = error_info.get("type")
                            error_code = error_info.get("code")
                    except Exception:
                        pass

            # Determine if 429 is retryable based on structured error codes
            if error_type == "tokens":
                # Token-related 429s are typically non-retryable (request too large)
                logging.debug(f"Non-retryable 429: token-related error (type={error_type}, code={error_code})")
                return False
            elif error_code in ["invalid_request_error", "context_length_exceeded"]:
                # These are permanent failures
                logging.debug(f"Non-retryable 429: permanent failure (type={error_type}, code={error_code})")
                return False
            else:
                # Other 429s (like requests per minute) are retryable
                logging.debug(f"Retryable 429: rate limiting (type={error_type}, code={error_code})")
                return True

        # For non-429 errors, check if they're retryable
        retryable_indicators = [
            "timeout",
            "connection",
            "network",
            "temporary",
            "unavailable",
            "retry",
            "408",  # Request timeout
            "500",  # Internal server error
            "502",  # Bad gateway
            "503",  # Service unavailable
            "504",  # Gateway timeout
            "ssl",  # SSL errors
            "handshake",  # Handshake failures
        ]

        return any(indicator in error_str for indicator in retryable_indicators)

    def _process_image(self, image_path: str) -> Optional[dict]:
        """Process an image for OpenAI-compatible API."""
        try:
            if image_path.startswith("data:image/"):
                # Handle data URL: data:image/png;base64,iVBORw0...
                return {"type": "image_url", "image_url": {"url": image_path}}
            else:
                # Handle file path
                if not os.path.exists(image_path):
                    logging.warning(f"Image file not found: {image_path}")
                    return None

                # Detect MIME type from file extension using centralized mappings
                from utils.file_types import get_image_mime_type

                ext = os.path.splitext(image_path)[1].lower()
                mime_type = get_image_mime_type(ext)
                logging.debug(f"Processing image '{image_path}' with extension '{ext}' as MIME type '{mime_type}'")

                # Read and encode the image
                with open(image_path, "rb") as f:
                    image_data = base64.b64encode(f.read()).decode()

                # Create data URL for OpenAI API
                data_url = f"data:{mime_type};base64,{image_data}"

                return {"type": "image_url", "image_url": {"url": data_url}}
        except Exception as e:
            logging.error(f"Error processing image {image_path}: {e}")
            return None

    def _generate_with_responses_endpoint(
        self,
        model_name: str,
        messages: list,
        temperature: float,
        max_output_tokens: Optional[int] = None,
        **kwargs,
    ) -> ModelResponse:
        """Generate content using the /v1/responses endpoint for o3-pro via OpenAI library."""
        # Convert messages to the correct format for responses endpoint
        input_messages = []

        for message in messages:
            role = message.get("role", "")
            content = message.get("content", "")

            if role == "system":
                # For o3-pro, system messages should be handled carefully to avoid policy violations
                # Instead of prefixing with "System:", we'll include the system content naturally
                input_messages.append({"role": "user", "content": [{"type": "input_text", "text": content}]})
            elif role == "user":
                input_messages.append({"role": "user", "content": [{"type": "input_text", "text": content}]})
            elif role == "assistant":
                input_messages.append({"role": "assistant", "content": [{"type": "output_text", "text": content}]})

        # Prepare completion parameters for responses endpoint
        # Based on OpenAI documentation, use nested reasoning object for responses endpoint
        completion_params = {
            "model": model_name,
            "input": input_messages,
            "reasoning": {"effort": "medium"},  # Use nested object for responses endpoint
            "store": True,
        }

        # Add max tokens if specified (using max_completion_tokens for responses endpoint)
        if max_output_tokens:
            completion_params["max_completion_tokens"] = max_output_tokens

        # For responses endpoint, we only add parameters that are explicitly supported
        # Remove unsupported chat completion parameters that may cause API errors

        # Retry logic with progressive delays
        max_retries = 4
        retry_delays = [1, 3, 5, 8]
        last_exception = None

        for attempt in range(max_retries):
            try:
                # Log the exact payload being sent for debugging
                logging.info(f"o3-pro API request payload: {json.dumps(completion_params, indent=2)}")

                # Use OpenAI client's responses endpoint
                response = self.client.responses.create(**completion_params)

                # Extract content and usage from responses endpoint format
                # The response format is different for responses endpoint
                content = ""
                if hasattr(response, "output") and response.output:
                    if hasattr(response.output, "content") and response.output.content:
                        # Look for output_text in content
                        for content_item in response.output.content:
                            if hasattr(content_item, "type") and content_item.type == "output_text":
                                content = content_item.text
                                break
                    elif hasattr(response.output, "text"):
                        content = response.output.text

                # Try to extract usage information
                usage = None
                if hasattr(response, "usage"):
                    usage = self._extract_usage(response)
                elif hasattr(response, "input_tokens") and hasattr(response, "output_tokens"):
                    # Safely extract token counts with None handling
                    input_tokens = getattr(response, "input_tokens", 0) or 0
                    output_tokens = getattr(response, "output_tokens", 0) or 0
                    usage = {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    }

                return ModelResponse(
                    content=content,
                    usage=usage,
                    model_name=model_name,
                    friendly_name=self.FRIENDLY_NAME,
                    provider=self.get_provider_type(),
                    metadata={
                        "model": getattr(response, "model", model_name),
                        "id": getattr(response, "id", ""),
                        "created": getattr(response, "created_at", 0),
                        "endpoint": "responses",
                    },
                )

            except Exception as e:
                last_exception = e

                # Check if this is a retryable error using structured error codes
                is_retryable = self._is_error_retryable(e)

                if is_retryable and attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logging.warning(
                        f"Retryable error for o3-pro responses endpoint, attempt {attempt + 1}/{max_retries}: {str(e)}. Retrying in {delay}s..."
                    )
                    time.sleep(delay)
                else:
                    break

        # If we get here, all retries failed
        actual_attempts = attempt + 1  # Convert from 0-based index to human-readable count
        error_msg = f"o3-pro responses endpoint error after {actual_attempts} attempt{'s' if actual_attempts > 1 else ''}: {str(last_exception)}"
        logging.error(error_msg)
        raise RuntimeError(error_msg) from last_exception

    def get_capabilities(self, model_name: str) -> ModelCapabilities:
        """Get capabilities for a specific OpenAI model."""
        # Resolve shorthand
        resolved_name = self._resolve_model_name(model_name)

        if resolved_name not in self.SUPPORTED_MODELS:
            raise ValueError(f"Unsupported OpenAI model: {model_name}")

        # Check if model is allowed by restrictions
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.OPENAI, resolved_name, model_name):
            raise ValueError(f"OpenAI model '{model_name}' is not allowed by restriction policy.")

        # Return the ModelCapabilities object directly from SUPPORTED_MODELS
        return self.SUPPORTED_MODELS[resolved_name]

    def get_provider_type(self) -> ProviderType:
        """Get the provider type."""
        return ProviderType.OPENAI

    def validate_model_name(self, model_name: str) -> bool:
        """Validate if the model name is supported and allowed."""
        resolved_name = self._resolve_model_name(model_name)

        # First check if model is supported
        if resolved_name not in self.SUPPORTED_MODELS:
            return False

        # Then check if model is allowed by restrictions
        from utils.model_restrictions import get_restriction_service

        restriction_service = get_restriction_service()
        if not restriction_service.is_allowed(ProviderType.OPENAI, resolved_name, model_name):
            logger.debug(f"OpenAI model '{model_name}' -> '{resolved_name}' blocked by restrictions")
            return False

        return True



    def supports_thinking_mode(self, model_name: str) -> bool:
        """Check if the model supports extended thinking mode."""
        # Currently no OpenAI models support extended thinking
        # This may change with future O3 models
        return False
