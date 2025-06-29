"""
List Models Tool - Display all available models organized by provider

This tool provides a comprehensive view of all AI models available in the system,
organized by their provider (Gemini, OpenAI, X.AI, OpenRouter, Custom).
It shows which providers are configured and what models can be used.
"""

import logging
import os
from typing import Any, Optional

from mcp.types import TextContent

from tools.models import ToolModelCategory, ToolOutput
from tools.shared.base_models import ToolRequest
from tools.shared.base_tool import BaseTool

logger = logging.getLogger(__name__)


class ListModelsTool(BaseTool):
    """
    Tool for listing all available AI models organized by provider.

    This tool helps users understand:
    - Which providers are configured (have API keys)
    - What models are available from each provider
    - Model aliases and their full names
    - Context window sizes and capabilities
    """

    def get_name(self) -> str:
        return "listmodels"

    def get_description(self) -> str:
        return (
            "LIST AVAILABLE MODELS - Display all AI models organized by provider. "
            "Shows which providers are configured, available models, their aliases, "
            "context windows, and capabilities. Useful for understanding what models "
            "can be used and their characteristics. MANDATORY: Must display full output to the user."
        )

    def get_input_schema(self) -> dict[str, Any]:
        """Return the JSON schema for the tool's input"""
        return {"type": "object", "properties": {}, "required": []}

    def get_annotations(self) -> Optional[dict[str, Any]]:
        """Return tool annotations indicating this is a read-only tool"""
        return {"readOnlyHint": True}

    def get_system_prompt(self) -> str:
        """No AI model needed for this tool"""
        return ""

    def get_request_model(self):
        """Return the Pydantic model for request validation."""
        return ToolRequest

    def requires_model(self) -> bool:
        return False

    async def prepare_prompt(self, request: ToolRequest) -> str:
        """Not used for this utility tool"""
        return ""

    def format_response(self, response: str, request: ToolRequest, model_info: Optional[dict] = None) -> str:
        """Not used for this utility tool"""
        return response

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        """
        List all available models organized by provider.

        This overrides the base class execute to provide direct output without AI model calls.

        Args:
            arguments: Standard tool arguments (none required)

        Returns:
            Formatted list of models by provider
        """
        from providers.base import ProviderType
        from providers.registry import ModelProviderRegistry

        output_lines = ["# Available AI Models\n"]

        # Map provider types to friendly names and their models
        provider_info = {
            ProviderType.OPENAI: {"name": "OpenAI-compatible Models", "env_key": "OPENAI_API_KEY"},
        }

        # Check each native provider type
        for provider_type, info in provider_info.items():
            # Check if provider is enabled
            provider = ModelProviderRegistry.get_provider(provider_type)
            is_configured = provider is not None

            output_lines.append(f"## {info['name']} {'✅' if is_configured else '❌'}")

            if is_configured:
                output_lines.append("**Status**: Configured and available")
                output_lines.append("\n**Models**:")

                # Get models from the provider's model configurations
                for model_name, capabilities in provider.get_model_configurations().items():
                    # Get description and context from the ModelCapabilities object
                    description = capabilities.description or "No description available"
                    context_window = capabilities.context_window

                    # Format context window
                    if context_window >= 1_000_000:
                        context_str = f"{context_window // 1_000_000}M context"
                    elif context_window >= 1_000:
                        context_str = f"{context_window // 1_000}K context"
                    else:
                        context_str = f"{context_window} context" if context_window > 0 else "unknown context"

                    output_lines.append(f"- `{model_name}` - {context_str}")

                    # Extract key capability from description
                    if "Ultra-fast" in description:
                        output_lines.append("  - Fast processing, quick iterations")
                    elif "Deep reasoning" in description:
                        output_lines.append("  - Extended reasoning with thinking mode")
                    elif "Strong reasoning" in description:
                        output_lines.append("  - Logical problems, systematic analysis")
                    elif "EXTREMELY EXPENSIVE" in description:
                        output_lines.append("  - ⚠️ Professional grade (very expensive)")
                    elif "Advanced reasoning" in description:
                        output_lines.append("  - Advanced reasoning and complex analysis")

                # Show aliases for this provider
                aliases = []
                for model_name, capabilities in provider.get_model_configurations().items():
                    if capabilities.aliases:
                        for alias in capabilities.aliases:
                            aliases.append(f"- `{alias}` → `{model_name}`")

                if aliases:
                    output_lines.append("\n**Aliases**:")
                    output_lines.extend(sorted(aliases))  # Sort for consistent output
            else:
                output_lines.append(f"**Status**: Not configured (set {info['env_key']})")

            output_lines.append("")

        # Show endpoint configuration
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        if base_url != "https://api.openai.com/v1":
            output_lines.append(f"## Custom Endpoint Configuration")
            output_lines.append(f"**Base URL**: {base_url}")
            output_lines.append("**Description**: Using custom OpenAI-compatible endpoint")
            output_lines.append("")

        # Add summary
        output_lines.append("## Summary")

        # Count configured providers
        configured_count = sum(
            [
                1
                for provider_type, info in provider_info.items()
                if ModelProviderRegistry.get_provider(provider_type) is not None
            ]
        )

        # Check if using custom endpoint (OpenRouter, local models, etc.)
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        if base_url != "https://api.openai.com/v1":
            # Custom endpoint is already counted as part of OpenAI provider
            pass

        output_lines.append(f"**Configured Providers**: {configured_count}")

        # Get total available models
        try:
            from providers.registry import ModelProviderRegistry

            # Get all available models respecting restrictions
            available_models = ModelProviderRegistry.get_available_models(respect_restrictions=True)
            total_models = len(available_models)
            output_lines.append(f"**Total Available Models**: {total_models}")
        except Exception as e:
            logger.warning(f"Error getting total available models: {e}")

        # Add usage tips
        output_lines.append("\n**Usage Tips**:")
        output_lines.append("- Use model aliases (e.g., 'flash', 'pro', 'o3') for convenience")
        output_lines.append("- In auto mode, Claude will select the best model for each task")
        output_lines.append("- Set OPENAI_BASE_URL to use custom OpenAI-compatible endpoints")
        output_lines.append("- All models are accessed through the unified OpenAI-compatible interface")

        # Format output
        content = "\n".join(output_lines)

        tool_output = ToolOutput(
            status="success",
            content=content,
            content_type="text",
            metadata={
                "tool_name": self.name,
                "configured_providers": configured_count,
            },
        )

        return [TextContent(type="text", text=tool_output.model_dump_json())]

    def get_model_category(self) -> ToolModelCategory:
        """Return the model category for this tool."""
        return ToolModelCategory.FAST_RESPONSE  # Simple listing, no AI needed
