"""Tests for OpenAI provider implementation."""

import os
from unittest.mock import MagicMock, patch

from providers.base import ProviderType
from providers.openai_provider import OpenAIModelProvider


class TestOpenAIProvider:
    """Test OpenAI provider functionality."""

    def setup_method(self):
        """Set up clean state before each test."""
        # Clear restriction service cache before each test
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    def teardown_method(self):
        """Clean up after each test to avoid singleton issues."""
        # Clear restriction service cache after each test
        import utils.model_restrictions

        utils.model_restrictions._restriction_service = None

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_initialization(self):
        """Test provider initialization."""
        provider = OpenAIModelProvider("test-key")
        assert provider.api_key == "test-key"
        assert provider.get_provider_type() == ProviderType.OPENAI
        assert provider.base_url == "https://api.openai.com/v1"

    def test_initialization_with_custom_url(self):
        """Test provider initialization with custom base URL."""
        provider = OpenAIModelProvider("test-key", base_url="https://custom.openai.com/v1")
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://custom.openai.com/v1"

    def test_model_validation(self):
        """Test model name validation."""
        provider = OpenAIModelProvider("test-key")

        # Test valid models
        assert provider.validate_model_name("o3") is True
        assert provider.validate_model_name("o3-pro") is True

        # Test valid aliases
        assert provider.validate_model_name("pro") is True
        assert provider.validate_model_name("flash") is True
        assert provider.validate_model_name("o4mini") is True

        # Test invalid model
        assert provider.validate_model_name("invalid-model") is False
        assert provider.validate_model_name("gpt-4") is False
        assert provider.validate_model_name("gemini-pro") is False

    def test_resolve_model_name(self):
        """Test model name resolution."""
        provider = OpenAIModelProvider("test-key")

        # Test shorthand resolution
        assert provider._resolve_model_name("pro") == "gemini-2.5-pro"
        assert provider._resolve_model_name("flash") == "gemini-2.5-flash"

        # Test full name passthrough
        assert provider._resolve_model_name("o3") == "o3"
        assert provider._resolve_model_name("o3-pro") == "o3-pro-2025-06-10"

    def test_get_capabilities_o3(self):
        """Test getting model capabilities for O3."""
        provider = OpenAIModelProvider("test-key")

        capabilities = provider.get_capabilities("o3")
        assert capabilities.model_name == "o3"  # Should NOT be resolved in capabilities
        assert capabilities.friendly_name == "OpenAI (O3)"
        assert capabilities.context_window == 200_000
        assert capabilities.provider == ProviderType.OPENAI
        assert not capabilities.supports_extended_thinking
        assert capabilities.supports_system_prompts is True
        assert capabilities.supports_streaming is True
        assert capabilities.supports_function_calling is True

        # Test temperature constraint (O3 has fixed temperature)
        assert capabilities.temperature_constraint.value == 1.0

    def test_get_capabilities_with_alias(self):
        """Test getting model capabilities with alias resolves correctly."""
        provider = OpenAIModelProvider("test-key")

        capabilities = provider.get_capabilities("pro")
        assert capabilities.model_name == "gemini-2.5-pro"  # Capabilities should show resolved model name
        assert capabilities.friendly_name == "Gemini (Pro 2.5)"
        assert capabilities.context_window == 1_048_576
        assert capabilities.provider == ProviderType.OPENAI

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_resolves_alias_before_api_call(self, mock_openai_class):
        """Test that generate_content resolves aliases before making API calls.

        This is the CRITICAL test that was missing - verifying that aliases
        like 'pro' get resolved to 'gemini-2.5-pro' before being sent to OpenAI API.
        """
        # Set up mock OpenAI client
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock the completion response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "gemini-2.5-pro"  # API returns the resolved model name
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIModelProvider("test-key")

        # Call generate_content with alias 'pro' (resolves to gemini-2.5-pro, supports temperature)
        result = provider.generate_content(
            prompt="Test prompt",
            model_name="pro",
            temperature=1.0,  # This should be resolved to "gemini-2.5-pro"
        )

        # Verify the API was called with the RESOLVED model name
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]

        # CRITICAL ASSERTION: The API should receive "gemini-2.5-pro", not "pro"
        assert (
            call_kwargs["model"] == "gemini-2.5-pro"
        ), f"Expected 'gemini-2.5-pro' but API received '{call_kwargs['model']}'"

        # Verify other parameters (gemini-2.5-pro supports temperature)
        assert call_kwargs["temperature"] == 1.0
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
        assert call_kwargs["messages"][0]["content"] == "Test prompt"

        # Verify response
        assert result.content == "Test response"
        assert result.model_name == "gemini-2.5-pro"  # Should be the resolved name

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_other_aliases(self, mock_openai_class):
        """Test other alias resolutions in generate_content."""
        # Set up mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIModelProvider("test-key")

        # Test flash -> gemini-2.5-flash
        mock_response.model = "gemini-2.5-flash"
        provider.generate_content(prompt="Test", model_name="flash", temperature=1.0)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gemini-2.5-flash"

    @patch("providers.openai_compatible.OpenAI")
    def test_generate_content_no_alias_passthrough(self, mock_openai_class):
        """Test that full model names pass through unchanged."""
        # Set up mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "o3"
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIModelProvider("test-key")

        # Test full model name passes through unchanged (use o3 since o3-pro has special handling)
        provider.generate_content(prompt="Test", model_name="o3", temperature=1.0)
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "o3"  # Should be unchanged

    def test_supports_thinking_mode(self):
        """Test thinking mode support (currently False for all OpenAI models)."""
        provider = OpenAIModelProvider("test-key")

        # All OpenAI models currently don't support thinking mode
        assert provider.supports_thinking_mode("o3") is False
        assert provider.supports_thinking_mode("o3-pro") is False
        assert provider.supports_thinking_mode("pro") is False  # Test with alias too

    @patch("providers.openai_compatible.OpenAI")
    def test_o3_pro_routes_to_responses_endpoint(self, mock_openai_class):
        """Test that o3-pro model routes to the /v1/responses endpoint (mock test)."""
        # Set up mock for OpenAI client responses endpoint
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.output = MagicMock()
        mock_response.output.content = [MagicMock()]
        mock_response.output.content[0].type = "output_text"
        mock_response.output.content[0].text = "4"
        mock_response.model = "o3-pro-2025-06-10"
        mock_response.id = "test-id"
        mock_response.created_at = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15

        mock_client.responses.create.return_value = mock_response

        provider = OpenAIModelProvider("test-key")

        # Generate content with o3-pro
        result = provider.generate_content(prompt="What is 2 + 2?", model_name="o3-pro", temperature=1.0)

        # Verify responses.create was called
        mock_client.responses.create.assert_called_once()
        call_args = mock_client.responses.create.call_args[1]
        assert call_args["model"] == "o3-pro-2025-06-10"
        assert call_args["input"][0]["role"] == "user"
        assert "What is 2 + 2?" in call_args["input"][0]["content"][0]["text"]

        # Verify the response
        assert result.content == "4"
        assert result.model_name == "o3-pro-2025-06-10"
        assert result.metadata["endpoint"] == "responses"

    @patch("providers.openai_compatible.OpenAI")
    def test_non_o3_pro_uses_chat_completions(self, mock_openai_class):
        """Test that non-o3-pro models use the standard chat completions endpoint."""
        # Set up mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.model = "o3"
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIModelProvider("test-key")

        # Generate content with o3 (not o3-pro)
        result = provider.generate_content(prompt="Test prompt", model_name="o3", temperature=1.0)

        # Verify chat.completions.create was called
        mock_client.chat.completions.create.assert_called_once()

        # Verify the response
        assert result.content == "Test response"
        assert result.model_name == "o3"
