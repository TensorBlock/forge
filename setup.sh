#!/bin/bash
set -e

# Colors for terminal output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Forge Middleware Setup ===${NC}"

# Check if python3.12 is installed
if ! command -v python3.12 &> /dev/null; then
    echo -e "${RED}Error: Python 3.12 is not installed. Please install Python 3.12 or newer.${NC}"

    # Detect OS for Python installation instructions
    OS=$(uname -s)
    if [ "$OS" = "Darwin" ]; then
        # macOS
        echo -e "${YELLOW}macOS detected. Install Python 3.12 with:${NC}"
        echo -e "${GREEN}  brew install python@3.12${NC}"
        echo -e "${YELLOW}Or download from:${NC} https://www.python.org/downloads/"
    elif [ "$OS" = "Linux" ]; then
        # Check Linux distribution
        if [ -f "/etc/debian_version" ]; then
            # Debian/Ubuntu
            echo -e "${YELLOW}Debian/Ubuntu detected. Install Python 3.12 with:${NC}"
            echo -e "${GREEN}  sudo add-apt-repository ppa:deadsnakes/ppa${NC}"
            echo -e "${GREEN}  sudo apt update${NC}"
            echo -e "${GREEN}  sudo apt install python3.12 python3.12-venv python3.12-dev${NC}"
        elif [ -f "/etc/fedora-release" ]; then
            # Fedora
            echo -e "${YELLOW}Fedora detected. Install Python 3.12 with:${NC}"
            echo -e "${GREEN}  sudo dnf install python3.12${NC}"
        elif [ -f "/etc/arch-release" ]; then
            # Arch Linux
            echo -e "${YELLOW}Arch Linux detected. Install Python 3.12 with:${NC}"
            echo -e "${GREEN}  sudo pacman -S python${NC}"
        else
            # Generic Linux
            echo -e "${YELLOW}Please install Python 3.12 using your distribution's package manager${NC}"
            echo -e "${YELLOW}Or download from:${NC} https://www.python.org/downloads/"
        fi
    else
        # Other OS
        echo -e "${YELLOW}Please install Python 3.12 from:${NC} https://www.python.org/downloads/"
    fi
    exit 1
fi

# Check python version
python_version=$(python3.12 --version | cut -d ' ' -f 2)
echo -e "${GREEN}✓ Using Python version:${NC} $python_version"

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo -e "${RED}Error: PostgreSQL is not installed.${NC}"

    OS=$(uname -s)
    if [ "$OS" = "Darwin" ]; then
        echo -e "${YELLOW}macOS detected. Install PostgreSQL with:${NC}"
        echo -e "${GREEN}  brew install postgresql@14${NC}"
        echo -e "${YELLOW}Then start the service with:${NC}"
        echo -e "${GREEN}  brew services start postgresql@14${NC}"
    elif [ "$OS" = "Linux" ]; then
        if [ -f "/etc/debian_version" ]; then
            echo -e "${YELLOW}Debian/Ubuntu detected. Install PostgreSQL with:${NC}"
            echo -e "${GREEN}  sudo apt update${NC}"
            echo -e "${GREEN}  sudo apt install postgresql postgresql-contrib${NC}"
        elif [ -f "/etc/fedora-release" ]; then
            echo -e "${YELLOW}Fedora detected. Install PostgreSQL with:${NC}"
            echo -e "${GREEN}  sudo dnf install postgresql-server postgresql-contrib${NC}"
            echo -e "${GREEN}  sudo postgresql-setup --initdb${NC}"
            echo -e "${GREEN}  sudo systemctl enable postgresql${NC}"
            echo -e "${GREEN}  sudo systemctl start postgresql${NC}"
        fi
    fi
    exit 1
fi

# Check if PostgreSQL is running
if ! pg_isready &> /dev/null; then
    echo -e "${RED}Error: PostgreSQL is not running.${NC}"
    echo -e "${YELLOW}Please start PostgreSQL and try again.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ PostgreSQL is installed and running${NC}"

# Install UV if not installed
if ! command -v uv &> /dev/null; then
    echo -e "\n${YELLOW}UV package manager not found. Installing UV...${NC}"

    OS=$(uname -s)
    ARCH=$(uname -m)

    if [ "$OS" = "Darwin" ]; then
        # MacOS
        if [ "$ARCH" = "arm64" ]; then
            # M1/M2 Mac
            curl -LsSf https://astral.sh/uv/install.sh | sh
        else
            # Intel Mac
            curl -LsSf https://astral.sh/uv/install.sh | sh
        fi
    elif [ "$OS" = "Linux" ]; then
        # Linux
        curl -LsSf https://astral.sh/uv/install.sh | sh
    else
        echo -e "${RED}Unsupported operating system. Please install UV manually: https://github.com/astral-sh/uv${NC}"
        exit 1
    fi

    # Add UV to PATH for the current session
    export PATH="$HOME/.local/bin:$PATH"

    # Check if UV is now available
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}UV installation succeeded but command not found in PATH.${NC}"
        echo -e "${YELLOW}Please add the following to your shell profile (${HOME}/.bashrc or ${HOME}/.zshrc):${NC}"
        echo -e "${GREEN}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
        echo -e "${YELLOW}Then restart your terminal or run:${NC}"
        echo -e "${GREEN}source ~/.bashrc${NC} or ${GREEN}source ~/.zshrc${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ UV installed and available in PATH${NC}"
else
    echo -e "${GREEN}✓ UV package manager already installed${NC}"
fi

# Create virtual environment
echo -e "\n${GREEN}Creating virtual environment...${NC}"
if [ -d ".venv" ]; then
    echo -e "${YELLOW}Virtual environment already exists. Using existing .venv.${NC}"
else
    uv venv .venv --python=python3.12
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "\n${GREEN}Activating virtual environment...${NC}"
source .venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Install dependencies
echo -e "\n${GREEN}Installing dependencies...${NC}"

echo -e "${GREEN}Installing project dependencies from pyproject.toml...${NC}"
if ! uv pip install -e .; then
    echo -e "${RED}Error installing project dependencies.${NC}"
    echo -e "${YELLOW}If you see an error about 'Unable to determine which files to ship inside the wheel',${NC}"
    echo -e "${YELLOW}make sure your pyproject.toml file has the [tool.hatch.build.targets.wheel] section${NC}"
    echo -e "${YELLOW}with packages = [\"app\"] to specify where your package code is located.${NC}"
    exit 1
fi

echo -e "${GREEN}Installing development dependencies...${NC}"
if ! uv pip install -e ".[dev]"; then
    echo -e "${RED}Error installing development dependencies.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Dependencies installed${NC}"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "\n${GREEN}Creating .env file from example...${NC}"
    cp .env.example .env

    # Generate random secret key
    if command -v openssl &> /dev/null; then
        SECRET_KEY=$(openssl rand -hex 32)
        ENCRYPTION_KEY=$(openssl rand -base64 32)
        # Replace placeholders with generated keys
        sed -i.bak "s/your_secret_key_here/$SECRET_KEY/" .env
        sed -i.bak "s/your_encryption_key_here/$ENCRYPTION_KEY/" .env
        rm -f .env.bak
        echo -e "${GREEN}✓ Generated secure random keys${NC}"
    else
        echo -e "${YELLOW}⚠️ OpenSSL not found. Please manually set SECRET_KEY and ENCRYPTION_KEY in .env file${NC}"
    fi

    echo -e "${YELLOW}⚠️ Please edit .env file to add your API keys and other configuration${NC}"
else
    echo -e "\n${YELLOW}⚠️ .env file already exists. Keeping existing configuration.${NC}"
fi

# Database setup
echo -e "\n${GREEN}Setting up PostgreSQL database...${NC}"

# Check if database exists
if psql -lqt | cut -d \| -f 1 | grep -qw forge; then
    echo -e "${YELLOW}Database 'forge' already exists.${NC}"
    echo -e "Choose an option:"
    echo -e "  ${GREEN}1) Drop and recreate database (will delete all data)${NC}"
    echo -e "  ${GREEN}2) Keep existing database${NC}"
    read -p "Enter your choice (1-2) [2]: " db_choice

    case "$db_choice" in
        1)
            echo -e "${YELLOW}Dropping existing database...${NC}"
            dropdb forge
            echo -e "${GREEN}✓ Database dropped${NC}"
            ;;
        *)
            echo -e "${YELLOW}Keeping existing database${NC}"
            ;;
    esac
fi

# Create database if it doesn't exist
if ! psql -lqt | cut -d \| -f 1 | grep -qw forge; then
    echo -e "${YELLOW}Creating new database...${NC}"
    createdb forge
    echo -e "${GREEN}✓ Database created${NC}"
fi

# Run database migrations
echo -e "\n${GREEN}Running database migrations...${NC}"
alembic upgrade head
echo -e "${GREEN}✓ Database migrations complete${NC}"

echo -e "\n${GREEN}=== Setup Complete! ===${NC}"
echo -e "\n${BLUE}IMPORTANT: Virtual Environment${NC}"
echo -e "This script has activated the virtual environment for the current shell session only."
echo -e "If you open a new terminal window or tab, you must manually activate the virtual environment:"
echo -e "${YELLOW}source .venv/bin/activate${NC}"
echo -e "You can tell the virtual environment is active when you see ${YELLOW}(.venv)${NC} at the beginning of your prompt."
echo -e "\n${GREEN}Next Steps:${NC}"
echo -e "1. Ensure your virtual environment is active ${YELLOW}(.venv)${NC}"
echo -e "2. You can run the server with: ${YELLOW}python run.py${NC}"
echo -e "   Or with uvicorn directly: ${YELLOW}uvicorn app.main:app --reload${NC}"
echo -e "3. Run tests with: ${YELLOW}python tests/run_tests.py${NC}"
echo -e "\n${GREEN}Remember to edit your .env file to add your API keys!${NC}"
