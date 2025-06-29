#!/bin/bash

# Zen MCP Server - Run Integration Tests
# This script runs integration tests that require API keys
# Run this locally on your Mac to ensure everything works end-to-end

set -e  # Exit on any error

echo "🧪 Running Integration Tests for Zen MCP Server"
echo "=============================================="
echo "These tests use real API calls with your configured keys"
echo ""

# Activate virtual environment
if [[ -f ".zen_venv/bin/activate" ]]; then
    source .zen_venv/bin/activate
    echo "✅ Using virtual environment"
else
    echo "❌ No virtual environment found!"
    echo "Please run: ./run-server.sh first"
    exit 1
fi

# Check for .env file
if [[ ! -f ".env" ]]; then
    echo "⚠️  Warning: No .env file found. Integration tests may fail without API keys."
    echo ""
fi

echo "🔑 Checking API key availability:"
echo "---------------------------------"

# Check OpenAI API configuration
if [[ -n "$OPENAI_API_KEY" ]] || grep -q "OPENAI_API_KEY=" .env 2>/dev/null; then
    echo "✅ OPENAI_API_KEY configured"

    # Check endpoint configuration
    if [[ -n "$OPENAI_BASE_URL" ]] || grep -q "OPENAI_BASE_URL=" .env 2>/dev/null; then
        base_url=$(grep "OPENAI_BASE_URL=" .env 2>/dev/null | cut -d'=' -f2 || echo "$OPENAI_BASE_URL")
        if [[ "$base_url" == *"openrouter.ai"* ]]; then
            echo "✅ OpenRouter endpoint configured"
        elif [[ "$base_url" == *"api.openai.com"* ]]; then
            echo "✅ Official OpenAI endpoint configured"
        else
            echo "✅ Custom OpenAI-compatible endpoint configured: $base_url"
        fi
    else
        echo "✅ Using default OpenAI endpoint"
    fi
else
    echo "❌ OPENAI_API_KEY not found"
    echo "   Please add OPENAI_API_KEY to your .env file"
fi

echo ""

# Run integration tests
echo "🏃 Running integration tests..."
echo "------------------------------"

# Run only integration tests (marked with @pytest.mark.integration)
python -m pytest tests/ -v -m "integration" --tb=short

echo ""
echo "✅ Integration tests completed!"
echo ""

# Also run simulator tests if requested
if [[ "$1" == "--with-simulator" ]]; then
    echo "🤖 Running simulator tests..."
    echo "----------------------------"
    python communication_simulator_test.py --verbose
    echo ""
    echo "✅ Simulator tests completed!"
fi

echo "💡 Tips:"
echo "- Run './run_integration_tests.sh' for integration tests only"
echo "- Run './run_integration_tests.sh --with-simulator' to also run simulator tests"
echo "- Run './code_quality_checks.sh' for unit tests and linting"
echo "- Check logs in logs/mcp_server.log if tests fail"