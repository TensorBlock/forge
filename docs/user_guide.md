# Forge User Guide

This guide provides detailed instructions for using Forge, the AI provider middleware service.

## Table of Contents

- [Forge User Guide](#forge-user-guide)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
    - [Creating Your Account](#creating-your-account)
    - [Obtaining Your Forge API Key](#obtaining-your-forge-api-key)
  - [Managing Provider Keys](#managing-provider-keys)
    - [Adding Provider Keys](#adding-provider-keys)
    - [Listing Provider Keys](#listing-provider-keys)
    - [Customizing Provider Settings](#customizing-provider-settings)
    - [Deleting Provider Keys](#deleting-provider-keys)
  - [Using the Forge CLI](#using-the-forge-cli)
    - [Interactive Mode](#interactive-mode)
    - [Command Line Arguments](#command-line-arguments)
    - [Common CLI Commands](#common-cli-commands)
  - [API Integration](#api-integration)
    - [OpenAI API Compatibility](#openai-api-compatibility)
    - [Chat Completions](#chat-completions)
    - [Model Support](#model-support)
  - [Advanced Features](#advanced-features)
    - [Custom Model Mapping](#custom-model-mapping)
    - [Provider Base URLs](#provider-base-urls)
    - [Regenerating API Keys](#regenerating-api-keys)
  - [Integrating with Applications](#integrating-with-applications)
    - [Frontend Applications](#frontend-applications)
    - [Development Tools](#development-tools)
    - [Integration Examples](#integration-examples)
  - [Security Best Practices](#security-best-practices)
    - [API Key Management](#api-key-management)
    - [User Account Security](#user-account-security)
  - [Troubleshooting](#troubleshooting)
    - [Common Issues](#common-issues)
    - [Error Messages](#error-messages)

## Getting Started

### Creating Your Account

To use Forge, you'll need to create an account:

1. Ensure the Forge server is running (see the [Installation Guide](./installation.md))
2. Use the Forge CLI to register:
   ```bash
   ./forge-cli.py register
   ```
   You'll be prompted to enter:
   - Username
   - Email address
   - Password

   Alternatively, you can provide these details directly:
   ```bash
   ./forge-cli.py register --username your_username --email your_email@example.com --password your_password
   ```

3. Upon successful registration, you'll receive a Forge API key.

### Obtaining Your Forge API Key

If you already have an account but need to retrieve your API key:

1. Login to your account:
   ```bash
   ./forge-cli.py login --username your_username --password your_password
   ```

2. Get your user information:
   ```bash
   ./forge-cli.py info
   ```
   This will display your Forge API key.

## Managing Provider Keys

### Adding Provider Keys

To use AI providers through Forge, you need to add their API keys:

1. Login to your account:
   ```bash
   ./forge-cli.py login --username your_username --password your_password
   ```

2. Add a provider key:
   ```bash
   ./forge-cli.py add-key
   ```

   Follow the interactive prompts to select a provider and enter your API key. You can also add a key directly:

   ```bash
   ./forge-cli.py add-key --provider openai --api-key sk_your_openai_key
   ```

   Supported providers include:
   - OpenAI
   - Anthropic
   - Other (custom providers)

### Listing Provider Keys

To see all your configured provider keys:

```bash
./forge-cli.py list-keys
```

This will display all providers you've configured, without showing the actual API keys.

### Customizing Provider Settings

When adding a provider key, you can customize additional settings:

1. **Custom Base URL**: Useful for self-hosted models or specific API endpoints
   ```bash
   ./forge-cli.py add-key --provider openai --api-key sk_your_key --base-url https://custom-api.example.com/v1
   ```

2. **Model Mapping**: Create aliases for provider models
   ```bash
   ./forge-cli.py add-key --provider openai --api-key sk_your_key --mapping '{"my-gpt4": "gpt-4", "my-gpt35": "gpt-3.5-turbo"}'
   ```

### Deleting Provider Keys

To remove a provider key:

```bash
./forge-cli.py delete-key openai
```

## Using the Forge CLI

### Interactive Mode

The interactive mode provides a menu-driven interface:

```bash
./forge-cli.py interactive
```

This will present a menu with options:
1. Register new user
2. Login
3. Get user info
4. Regenerate API key
5. Add provider key
6. List provider keys
7. Delete provider key
8. Test chat completion

Navigate by entering the number of your chosen option.

### Command Line Arguments

For scripting or quick operations, use command-line arguments:

```bash
./forge-cli.py --help
```

This shows all available commands and their parameters.

### Common CLI Commands

Here are frequently used commands:

```bash
# Register a new user
./forge-cli.py register --username user --email user@example.com

# Login
./forge-cli.py login --username user

# Add a provider key
./forge-cli.py add-key --provider openai --api-key sk_your_key

# Test a chat completion
./forge-cli.py test --model gpt-4 --message "Hello, AI!"

# Regenerate your Forge API key
./forge-cli.py regenerate
```

## API Integration

### OpenAI API Compatibility

Forge is designed to be compatible with the OpenAI API. Any tool or application that uses the OpenAI API can be configured to use Forge instead.

### Chat Completions

To use the chat completions API:

```bash
curl -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-KEY: your_forge_api_key" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {"role": "user", "content": "Hello, how are you?"}
    ]
  }'
```

For detailed API documentation, visit the Swagger UI at `http://localhost:8000/docs` when the server is running.

### Model Support

Forge supports models from various providers:

- **OpenAI**: GPT-3.5, GPT-4, etc.
- **Anthropic**: Claude, Claude Instant, etc.

When making API calls, you can use standard model names, and Forge will route to the appropriate provider.

## Advanced Features

### Custom Model Mapping

Model mapping allows you to create custom aliases for provider models:

1. When adding a provider key, specify a mapping:
   ```bash
   ./forge-cli.py add-key --provider openai --api-key sk_your_key --mapping '{"smart": "gpt-4", "fast": "gpt-3.5-turbo"}'
   ```

2. Then use your custom model names in API calls:
   ```json
   {
     "model": "smart",
     "messages": [
       {"role": "user", "content": "Write a complex algorithm"}
     ]
   }
   ```

This is useful for:
- Creating standardized model names across your organization
- Abstracting away provider-specific model names
- Creating easy-to-remember aliases

### Provider Base URLs

You can customize the base URL for a provider:

```bash
./forge-cli.py add-key --provider openai --api-key sk_your_key --base-url https://api.custom-openai-proxy.com/v1
```

This is useful for:
- Self-hosted models
- API proxies
- Regional API endpoints
- Internal model deployments

### Regenerating API Keys

If you need to invalidate your current Forge API key and generate a new one:

```bash
./forge-cli.py regenerate
```

This is important if your key is compromised or for regular security rotations.

## Integrating with Applications

### Frontend Applications

To integrate Forge with frontend applications like LobeChat, CherryStudio, or any OpenAI-compatible tool:

1. In the application's settings, find the API configuration section
2. Set the API endpoint to your Forge server (e.g., `http://localhost:8000`)
3. Enter your Forge API key (not your OpenAI key)
4. Use standard model names (e.g., `gpt-4`) or your custom mapped names

### Development Tools

For developers using AI tools:

1. **VS Code Extensions**: For extensions like GitHub Copilot or similar, set the API endpoint and key in the extension settings
2. **CLI Tools**: For tools like LLM from the command line, configure them to point to your Forge endpoint
3. **SDKs**: When using OpenAI SDK, configure the base URL:
   ```python
   import openai
   openai.api_key = "your_forge_api_key"
   openai.api_base = "http://localhost:8000/v1"
   ```

### Integration Examples

Example of using Forge with the OpenAI Python SDK:

```python
import openai

# Configure to use Forge
openai.api_key = "your_forge_api_key"
openai.api_base = "http://localhost:8000"

# Make a completion request
response = openai.ChatCompletion.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "Explain quantum computing in simple terms"}
    ]
)

print(response.choices[0].message.content)
```

## Security Best Practices

### API Key Management

- Store your Forge API key securely
- Don't hardcode keys in source code
- Use environment variables or secure key storage
- Regenerate keys periodically
- Give each application its own key when possible

### User Account Security

- Use strong, unique passwords for your Forge account
- Don't share login credentials between users
- Logout when using shared computers

## Troubleshooting

### Common Issues

**Issue**: API calls return authentication errors
**Solution**: Verify your Forge API key is correct and hasn't been regenerated

**Issue**: Specified model not found
**Solution**: Ensure you've added the appropriate provider key for that model

**Issue**: Provider service errors
**Solution**: Check that your provider API key is valid and has sufficient credits

### Error Messages

| Error Code | Description | Solution |
|------------|-------------|----------|
| 401 | Unauthorized | Check your Forge API key |
| 404 | Model not found | Verify the model name and provider configuration |
| 402 | Insufficient credits | Add credits to your provider account |
| 500 | Server error | Check the Forge server logs |

For additional help, consult the Forge repository issues or reach out to the community.
