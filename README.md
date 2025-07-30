<div style="width: auto; margin-left: auto; margin-right: auto">
<img src="https://i.imgur.com/jC7kdl8.jpeg" alt="TensorBlock" style="width: 100%; min-width: 400px; display: block; margin: auto;">
</div>

# Forge
[![Website](https://img.shields.io/badge/Website-tensorblock.co-blue?logo=google-chrome&logoColor=white)](https://tensorblock.co)
[![Twitter](https://img.shields.io/twitter/follow/tensorblock_aoi?style=social)](https://twitter.com/tensorblock_aoi)
[![Discord](https://img.shields.io/badge/Discord-Join%20Us-5865F2?logo=discord&logoColor=white)](https://discord.gg/yefvtqDd2w)
[![🤗 Hugging Face](https://img.shields.io/badge/HuggingFace-TensorBlock-yellow?logo=huggingface&logoColor=white)](https://huggingface.co/tensorblock)
[![Telegram](https://img.shields.io/badge/Telegram-Group-blue?logo=telegram)](https://t.me/TensorBlock)

<div align="center">
  <h3>One API for all AI models</h3>
  <p>
    <a href="https://www.producthunt.com/products/tensorblock-forge?embed=true&utm_source=badge-top-post-badge&utm_medium=badge&utm_source=badge-tensorblock&#0045;forge" target="_blank"><img src="https://api.producthunt.com/widgets/embed-image/v1/top-post-badge.svg?post_id=985244&theme=light&period=daily&t=1752002891028" alt="TensorBlock&#0032;Forge - One&#0032;API&#0032;for&#0032;all&#0032;AI&#0032;models | Product Hunt" style="width: 250px; height: 54px;" width="250" height="54" /></a>
  </p>

  <p>
    <a href="#key-features">Features</a> •
    <a href="#installation">Installation</a> •
    <a href="#usage">Usage</a> •
    <a href="#configuration">Configuration</a> •
    <a href="#security-and-privacy">Security</a> •
    <a href="#contributing">Contributing</a> •
    <a href="#license">License</a>
  </p>
</div>



## Introduction

Forge is an open-source middleware service that simplifies AI model provider management. It allows you to use multiple AI providers (OpenAI, Anthropic, etc.) through a single, unified API. By storing your provider API keys securely, Forge generates a unified key that works across all your AI applications.

![Product Poster](assets/service.jpg)

**News**
- We have deployed Forge as an online service, feel free to [✨ learn the service](https://tensorblock.co/forge) and [🚀 try it now](https://forge.tensorblock.co)
- Forge now enables [Claude Code to work with any LLM](https://github.com/TensorBlock/claude-code-forge)

**Why Forge?**
- **Unified Experience**: Use multiple AI models through a single, consistent API
- **Simplified Key Management**: Store provider keys once, use everywhere
- **Seamless Integration**: Compatible with OpenAI API standard for easy integration with existing tools
- **Enhanced Security**: Keys are encrypted and never exposed to end applications

## Key Features

- **Unified API Key**: Store multiple provider API keys and access all with a single Forge API key
- **OpenAI API Compatible**: Drop-in replacement for any application that uses OpenAI's API
- **Model Mapping**: Create custom model names mapped to provider-specific models
- **Advanced Security**: Strong encryption for API keys with JWT-based authentication
- **High Performance**: Built for scalability and concurrent usage
- **CLI Management**: Easy key and user management via included command-line interface
- **Extensible Architecture**: Provider adapter pattern makes it easy to add new AI providers

## Installation

### Prerequisites

- Python 3.12 or newer
- UV package manager (installed automatically by the setup scripts)

The project uses UV as the preferred package manager for faster and more reliable dependency installation.

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/forge.git
cd forge

# Make sure you have a running PostgreSQL instance.
# You can start one locally using Docker:
# docker compose up -d db
#
# Your DATABASE_URL for the local Docker setup will be:
# DATABASE_URL="postgresql://forge:forge@localhost:5432/forge"

# Create and configure your environment file
cp .env.example .env
# Now, edit the .env file with your specific settings.
# If you used the docker compose command above, you can use the DATABASE_URL provided.
# The `DATABASE_URL` should point to your running PostgreSQL instance.
# Example: DATABASE_URL="postgresql://user:password@localhost/mydatabase"

# Run the setup script
# For Linux/macOS:
chmod +x setup.sh
./setup.sh

# For Windows:
setup.bat

# Start the server
python run.py
```

### Using Docker

```bash
# First, create your environment file from the example.
# The Docker container will automatically use this .env file for configuration.
cp .env.example .env
# Now, edit the .env file with your specific settings.

# Build and run with Docker Compose
docker compose up -d
```

### Manual Setup

If you prefer to set up manually:

```bash
# After cloning the repo, create your environment file
cp .env.example .env
# Now, edit the .env file with your specific settings.

# Install UV package manager
curl -LsSf https://astral.sh/uv/install.sh | sh  # Linux/macOS
# or
pip install uv  # Windows

# Create a virtual environment
uv venv venv --python=python3.12
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate  # Windows

# Install dependencies
uv pip install -e .
uv pip install --dev -e .

# Run migrations
alembic upgrade head

# Start the server
python run.py
```

See the [detailed installation guide](docs/installation.md) for step-by-step instructions.

## Usage

### Managing Forge with CLI

Forge comes with a command-line interface for easy management:

```bash
# Run in interactive mode
./forge-cli.py

# Or use specific commands
./forge-cli.py register --username myuser --email user@example.com
./forge-cli.py login --username myuser
./forge-cli.py add-key --provider openai --api-key sk-...
./forge-cli.py test --model gpt-4o --message "Hello, AI!"
```

See all available commands:
```bash
./forge-cli.py --help
```

### API Documentation

API documentation is available at `/docs` when the server is running.

## Integration

### Connecting Frontends

To use Forge with frontends like CherryStudio, LobeChat, or any OpenAI-compatible application:

1. Register and add your provider API keys in Forge
2. Configure your frontend to use Forge's URL and your Forge API key
3. Use standard model names (e.g., `gpt-4o`, `claude-sonnet-4`) or custom mappings

```
Frontend ➡️ Forge ➡️ AI Provider API
```

### Supported Providers

Forge supports an extensive range of AI providers through both custom adapters and OpenAI-compatible interfaces:

- **OpenAI**
- **Anthropic**
- **Google Gemini**
- **xAI**
- **DeepSeek**
- **Cohere**
- **Mistral**
- **Nvidia**
- **Alibaba**
- **Fireworks AI**
- **Azure OpenAI**
- **AWS Bedrock**
- **Together AI**
- **OpenRouter**
- **Cerebras**
- **Groq**
- **SambaNova**
- **Moonshot**
- **Hunyuan**
- **Baichuan**
- **Stepfun**
- **01.ai**
- **Nebius**
- **Novita**
- **NScale**
- **DeepInfra**
- **Maritaca**
- **Featherless.ai**
- **Enfer**
- **Inference.net**
- **Kluster.ai**
- **Lambda**
- **Mancer**
- **Redpill.ai**
- **Parasail**
- **Nineteen.ai**
- **Targon**
- **Hyperbolic**
- **SiliconFlow**
- **TensorBlock**
- **Perplexity**
- **Zhipu**

The Anthropic integration includes:
- Support for Claude 3 models with streaming responses
- Automatic model name mapping (e.g., "claude" → "claude-3-opus-20240229")
- Message API format support
- Token usage reporting

## Configuration

### Environment Variables

Key environment variables in your `.env` file, please check `.env.example`:

```
# Server settings
HOST=127.0.0.1
PORT=8000

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/forge

# Security
API_KEY_ENCRYPTION_KEY=your_generated_key
JWT_SECRET_KEY=your_generated_key
# Secret key for signing JWTs. Generate a strong, random key.
# Use `openssl rand -hex 32` to generate a key.
SECRET_KEY=
# Secret key for encrypting sensitive data like provider API keys.
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=
```

### Model Mapping

Create custom aliases for provider models:

```json
{
  "my-smart-model": "gpt-4o",
  "my-fast-model": "claude-instant"
}
```

## Security and Privacy

At Forge, we take the security and privacy of your API keys very seriously. Since our service requires storing provider API keys (like OpenAI, Anthropic, etc.), we've implemented multiple layers of protection:

### API Key Encryption

- **Strong Encryption**: All provider API keys are encrypted using [Fernet symmetric encryption](https://cryptography.io/en/latest/fernet/), which utilizes AES-128 in CBC mode with PKCS7 padding
- **Secure Key Storage**: The encryption key itself is never stored in the database and is only held in environment variables
- **No Plaintext Storage**: API keys are never stored in plaintext at any point in the database
- **Encryption at Rest**: Keys remain encrypted in the database, only being decrypted temporarily in memory when needed for API calls

### Data Transmission

- **HTTPS Only**: When deployed in production, all communication should be over HTTPS to prevent man-in-the-middle attacks
- **JWT Authentication**: All API interactions are authenticated using JWT tokens with configurable expiration
- **Header-Based API Keys**: The Forge API key is transmitted via HTTP headers, not in URLs or query parameters
- **No Key Logging**: API keys are masked in logs to prevent accidental exposure

### Key Management

- **Key Regeneration**: Users can instantly regenerate their Forge API key if it's compromised
- **Isolated Storage**: Each user's provider keys are isolated and can only be accessed with proper authentication
- **Minimal Persistence**: Keys are only held in memory during the processing of a request
- **No Third-Party Sharing**: Your API keys are never shared with third parties or used for any purpose other than routing your requests

### Self-Hosted Security

Since Forge is designed to be self-hosted, you maintain complete control over:
- **Who has access** to your Forge instance
- **Where your data** is stored and processed
- **How the system** is deployed and secured
- **What security measures** (firewalls, access controls, etc.) are in place

### Security Implementation Details

1. **Key Encryption Process**:
   - New API keys are immediately encrypted before storing
   - The encryption uses a randomly generated nonce to ensure that identical keys don't produce the same ciphertext
   - Encryption key is derived from the environment variable `API_KEY_ENCRYPTION_KEY`

2. **Request Processing**:
   - When a request comes in with your Forge API key, we:
     1. Authenticate the request
     2. Identify the appropriate provider
     3. Decrypt the provider's API key temporarily in memory
     4. Use the decrypted key to make the provider API call
     5. Return the response to you
     6. Discard the decrypted key from memory

3. **Server Security Recommendations**:
   - Run Forge behind a secure reverse proxy like Nginx with HTTPS
   - Implement IP restrictions where possible
   - Use strong, unique values for all security-related environment variables
   - Regularly update the server and dependencies
   - Consider using key rotation policies for sensitive credentials

## Testing

Run the comprehensive test suite:

```bash
python tests/run_tests.py  # Unit and integration tests
```

## Contributing

We welcome contributions from the community!

### Getting Started

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests to ensure everything works
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to your branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Guidelines

- Follow the [code style guide](docs/code-style.md)
- Write tests for new features
- Update documentation for any changes
- See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for detailed guidelines

### Continuous Integration

We use GitHub Actions for continuous integration:

- All pull requests trigger automated tests
- Code must pass all tests before merging
- Test coverage is tracked to maintain quality
- Database migrations are validated automatically

The CI pipeline checks:
- Unit and integration tests
- Code formatting and linting
- Database migrations

You can run these checks locally before submitting your PR:
```bash
# Run tests
python tests/run_tests.py

# Check code formatting (if installed)
black --check app tests
flake8 app tests
```

### Project Structure

```
forge/
├── app/              # Main application code
│   ├── api/          # API endpoints
│   ├── core/         # Core functionality
│   ├── models/       # Database models
│   └── services/     # Business logic
├── docs/             # Documentation
├── tests/            # Test suite
└── forge-cli.py      # Command-line interface
```

## Roadmap

Our future plans include:

- Additional AI provider integrations
- Advanced request routing and load balancing
- Usage analytics and monitoring
- User and team management features

## License

Please check [License](LICENSE)
