# Forge Installation Guide

This guide provides detailed installation instructions for setting up Forge on various platforms.

## Table of Contents

- [Forge Installation Guide](#forge-installation-guide)
  - [Table of Contents](#table-of-contents)
  - [Prerequisites](#prerequisites)
  - [Installation Methods](#installation-methods)
    - [Quick Setup Script](#quick-setup-script)
    - [Manual Installation](#manual-installation)
    - [Docker Installation](#docker-installation)
  - [Platform-Specific Instructions](#platform-specific-instructions)
    - [Linux](#linux)
    - [macOS](#macos)
    - [Windows](#windows)
  - [Verifying Your Installation](#verifying-your-installation)
  - [Troubleshooting](#troubleshooting)
    - [Common Issues](#common-issues)
    - [Getting Help](#getting-help)
  - [Next Steps](#next-steps)

## Prerequisites

Before installing Forge, ensure you have the following:

- **Python 3.8+** installed
- **pip** (Python package manager)
- **git** for cloning the repository
- **Docker** (optional, for containerized installation)

## Installation Methods

### Quick Setup Script

The quickest way to get started with Forge is to use the provided setup script:

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/forge.git
   cd forge
   ```

2. Run the setup script:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. Start the server:
   ```bash
   python run.py
   ```

The setup script performs the following actions:
- Creates a Python virtual environment
- Installs all required dependencies
- Creates a `.env` file from `.env.example`
- Generates secure random keys for encryption and JWT
- Runs database migrations
- Sets up the initial database structure

### Manual Installation

If you prefer more control over the installation process, follow these steps:

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/forge.git
   cd forge
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

3. Activate the virtual environment:
   - On Linux/macOS:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Create a `.env` file:
   ```bash
   cp .env.example .env
   ```

6. Generate secure keys:
   ```bash
   python -c "import os; from base64 import b64encode; print(f'API_KEY_ENCRYPTION_KEY={b64encode(os.urandom(32)).decode()}')"
   python -c "import os; from base64 import b64encode; print(f'JWT_SECRET_KEY={b64encode(os.urandom(32)).decode()}')"
   ```

7. Add the generated keys to your `.env` file.

8. Run database migrations:
   ```bash
   alembic upgrade head
   ```

9. Start the server:
   ```bash
   python run.py
   ```
   or
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Docker Installation

For a containerized deployment:

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/forge.git
   cd forge
   ```

2. Build and start with Docker Compose:
   ```bash
   docker-compose up -d
   ```

3. To view logs:
   ```bash
   docker-compose logs -f
   ```

4. To stop the service:
   ```bash
   docker-compose down
   ```

## Platform-Specific Instructions

### Linux

For Debian/Ubuntu-based distributions:

1. Install system dependencies:
   ```bash
   sudo apt update
   sudo apt install -y python3 python3-pip python3-venv git
   ```

2. Follow the [Manual Installation](#manual-installation) or [Quick Setup Script](#quick-setup-script) instructions.

### macOS

1. Install Homebrew if not already installed:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. Install Python and Git:
   ```bash
   brew install python git
   ```

3. Follow the [Manual Installation](#manual-installation) or [Quick Setup Script](#quick-setup-script) instructions.

### Windows

1. Install Python from the [official website](https://www.python.org/downloads/windows/).

2. Install Git from the [official website](https://git-scm.com/download/win).

3. Open Command Prompt or PowerShell and follow the [Manual Installation](#manual-installation) steps, with these Windows-specific adjustments:

   - Clone the repository:
     ```
     git clone https://github.com/yourusername/forge.git
     cd forge
     ```

   - Create and activate a virtual environment:
     ```
     python -m venv venv
     venv\Scripts\activate
     ```

   - Continue with the rest of the manual installation steps.

## Verifying Your Installation

To verify that Forge is installed and running correctly:

1. Open a web browser and navigate to:
   ```
   http://localhost:8000/docs
   ```
   You should see the Swagger UI API documentation.

2. Test with the CLI tool:
   ```bash
   ./forge-cli.py interactive
   ```
   You should see the interactive menu prompting you for actions.

## Troubleshooting

### Common Issues

**Problem**: `ModuleNotFoundError` when running the application.

**Solution**: Ensure the virtual environment is activated and all dependencies are installed:
```bash
source venv/bin/activate  # On Linux/macOS
venv\Scripts\activate     # On Windows
pip install -r requirements.txt
```

**Problem**: Database migration errors.

**Solution**: Try resetting the migrations and starting from scratch:
```bash
rm -rf migrations  # Be cautious with this command!
alembic init migrations
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

**Problem**: Permission errors when running the setup script.

**Solution**: Ensure the script is executable:
```bash
chmod +x setup.sh
```

**Problem**: API key encryption errors.

**Solution**: Check that your `.env` file contains valid base64-encoded encryption keys:
```bash
python -c "import os; from base64 import b64encode; print(f'API_KEY_ENCRYPTION_KEY={b64encode(os.urandom(32)).decode()}')"
python -c "import os; from base64 import b64encode; print(f'JWT_SECRET_KEY={b64encode(os.urandom(32)).decode()}')"
```

### Getting Help

If you encounter issues not covered by this guide:

1. Check the [GitHub Issues](https://github.com/yourusername/forge/issues) to see if others have faced the same problem.
2. Search for similar problems in the project discussions.
3. Open a new issue if your problem hasn't been addressed yet.

## Next Steps

After installation, refer to:
- [User Guide](./user_guide.md) for instructions on using Forge
- [Contributing Guide](./contributing.md) if you want to contribute to the project
- [API Documentation](../README.md#api-documentation) for API details
