#!/usr/bin/env python3
"""
Forge TUI - A modern Terminal User Interface for Forge middleware service
Built with Textual for a beautiful and intuitive CLI experience
"""
import json
import asyncio
import configparser
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path

import requests
from http import HTTPStatus

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Button, Input, TextArea, Static, DataTable, 
    Label, Tabs, TabPane, TabbedContent, Select, Switch, Log, 
    Tree, Placeholder, LoadingIndicator, Markdown, ProgressBar
)
from textual.screen import Screen, ModalScreen
from textual.message import Message
from textual.reactive import reactive
from textual.binding import Binding
from textual.timer import Timer


class Config:
    """Configuration manager for Forge TUI"""
    
    def __init__(self, config_path: Path = None):
        self.config_path = config_path or Path(__file__).parent / "config.ini"
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self):
        """Load configuration from file"""
        if self.config_path.exists():
            self.config.read(self.config_path)
        else:
            self.create_default_config()
    
    def create_default_config(self):
        """Create default configuration"""
        self.config['api'] = {
            'base_url': 'http://localhost:8000/v1',
            'timeout': '30',
            'retry_attempts': '3'
        }
        self.config['ui'] = {
            'default_theme': 'dark',
            'show_clock': 'true',
            'show_notifications': 'true',
            'auto_refresh_interval': '30'
        }
        self.config['display'] = {
            'table_page_size': '15',
            'max_log_lines': '100',
            'truncate_long_text': 'true',
            'max_text_length': '50'
        }
        self.save_config()
    
    def save_config(self):
        """Save configuration to file"""
        with open(self.config_path, 'w') as f:
            self.config.write(f)
    
    def get(self, section: str, key: str, fallback: str = None):
        """Get configuration value"""
        return self.config.get(section, key, fallback=fallback)
    
    def getboolean(self, section: str, key: str, fallback: bool = False):
        """Get boolean configuration value"""
        return self.config.getboolean(section, key, fallback=fallback)
    
    def getint(self, section: str, key: str, fallback: int = 0):
        """Get integer configuration value"""
        return self.config.getint(section, key, fallback=fallback)


class ForgeAPI:
    """Enhanced API client for Forge service with configuration support"""

    def __init__(self, config: Config):
        self.config = config
        self.api_url = config.get('api', 'base_url', 'http://localhost:8000/v1')
        self.timeout = config.getint('api', 'timeout', 30)
        self.retry_attempts = config.getint('api', 'retry_attempts', 3)
        self.token = None
        self.forge_api_key = None

    async def _make_request(self, method: str, endpoint: str, **kwargs) -> tuple[bool, dict | str]:
        """Make HTTP request with error handling and retries"""
        url = f"{self.api_url}{endpoint}"
        kwargs.setdefault('timeout', self.timeout)
        
        for attempt in range(self.retry_attempts):
            try:
                response = requests.request(method, url, **kwargs)
                if response.status_code in [HTTPStatus.OK, HTTPStatus.CREATED]:
                    try:
                        return True, response.json()
                    except json.JSONDecodeError:
                        return True, {"message": "Success"}
                else:
                    error_msg = f"HTTP {response.status_code}"
                    try:
                        error_data = response.json()
                        if 'detail' in error_data:
                            error_msg += f": {error_data['detail']}"
                        elif 'message' in error_data:
                            error_msg += f": {error_data['message']}"
                        else:
                            error_msg += f": {response.text}"
                    except:
                        error_msg += f": {response.text}"
                    return False, error_msg
            except requests.exceptions.RequestException as e:
                if attempt == self.retry_attempts - 1:  # Last attempt
                    return False, f"Request failed: {str(e)}"
                await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
        
        return False, "Max retries exceeded"

    async def health_check(self) -> tuple[bool, str]:
        """Check if Forge server is healthy"""
        success, result = await self._make_request("GET", "/health")
        if success:
            return True, "Server is healthy"
        return success, result if isinstance(result, str) else "Health check failed"

    async def register(self, username: str, email: str, password: str) -> tuple[bool, str]:
        """Register a new user"""
        success, result = await self._make_request(
            "POST", "/auth/register",
            json={"username": username, "email": email, "password": password}
        )
        if success and isinstance(result, dict) and result.get("forge_api_keys"):
            # Handle API keys like in original CLI - they are strings directly
            api_keys = result["forge_api_keys"]
            if api_keys:
                first_key = api_keys[0]
                if isinstance(first_key, dict):
                    self.forge_api_key = first_key.get('key')
                else:
                    self.forge_api_key = str(first_key)
            return True, f"User {username} registered successfully!"
        return success, result if isinstance(result, str) else "Registration failed"

    async def login(self, username: str, password: str) -> tuple[bool, str]:
        """Login and get JWT token"""
        success, result = await self._make_request(
            "POST", "/auth/token",
            data={"username": username, "password": password}
        )
        if success and isinstance(result, dict):
            self.token = result.get("access_token")
            return True, "Login successful!"
        return success, result if isinstance(result, str) else "Login failed"

    async def get_user_info(self) -> tuple[bool, dict | str]:
        """Get current user information"""
        if not self.token:
            return False, "Not authenticated. Please login first."
        
        success, result = await self._make_request(
            "GET", "/users/me",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        return success, result

    async def create_forge_api_key(self, name: str = None, allowed_provider_key_ids: List[int] = None) -> tuple[bool, dict | str]:
        """Create a new Forge API key"""
        if not self.token:
            return False, "Not authenticated. Please login first."

        payload = {}
        if name:
            payload["name"] = name
        if allowed_provider_key_ids is not None:
            payload["allowed_provider_key_ids"] = allowed_provider_key_ids

        success, result = await self._make_request(
            "POST", "/api-keys/",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        
        if success and isinstance(result, dict) and not self.forge_api_key:
            self.forge_api_key = result.get("key")
        
        return success, result

    async def list_forge_api_keys(self) -> tuple[bool, List[dict] | str]:
        """List all Forge API keys"""
        if not self.token:
            return False, "Not authenticated. Please login first."

        success, result = await self._make_request(
            "GET", "/api-keys/",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        return success, result

    async def update_forge_api_key(self, key_id: int, name: str = None, 
                                 is_active: bool = None, 
                                 allowed_provider_key_ids: List[int] = None) -> tuple[bool, dict | str]:
        """Update an existing Forge API key"""
        if not self.token:
            return False, "Not authenticated. Please login first."

        payload = {}
        if name is not None:
            payload["name"] = name
        if is_active is not None:
            payload["is_active"] = is_active
        if allowed_provider_key_ids is not None:
            payload["allowed_provider_key_ids"] = allowed_provider_key_ids

        if not payload:
            return False, "No update parameters provided"

        success, result = await self._make_request(
            "PUT", f"/api-keys/{key_id}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            },
            json=payload
        )
        return success, result

    async def delete_forge_api_key(self, key_id: int) -> tuple[bool, str]:
        """Delete a Forge API key"""
        if not self.token:
            return False, "Not authenticated. Please login first."

        success, result = await self._make_request(
            "DELETE", f"/api-keys/{key_id}",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        if success:
            if isinstance(result, dict) and self.forge_api_key == result.get("key"):
                self.forge_api_key = None
            return True, f"API key {key_id} deleted successfully"
        
        return success, result if isinstance(result, str) else "Delete failed"

    async def add_provider_key(self, provider_name: str, api_key: str, 
                             base_url: str = None, model_mapping: dict = None, 
                             config: dict = None) -> tuple[bool, str]:
        """Add a provider key"""
        if not self.token:
            return False, "Not authenticated. Please login first."

        data = {
            "provider_name": provider_name,
            "api_key": api_key
        }
        
        if base_url:
            data["base_url"] = base_url
        if model_mapping:
            data["model_mapping"] = model_mapping
        if config:
            data["config"] = config

        success, result = await self._make_request(
            "POST", "/provider-keys/",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            },
            json=data
        )
        
        message = f"Successfully added {provider_name} API key!" if success else result
        return success, message if isinstance(message, str) else "Operation failed"

    async def list_provider_keys(self) -> tuple[bool, List[dict] | str]:
        """List all provider keys"""
        if not self.token:
            return False, "Not authenticated. Please login first."

        success, result = await self._make_request(
            "GET", "/provider-keys/",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        return success, result

    async def update_provider_key(self, provider_name: str, api_key: str = None,
                                base_url: str = None, model_mapping: dict = None,
                                config: dict = None) -> tuple[bool, str]:
        """Update a provider key"""
        if not self.token:
            return False, "Not authenticated. Please login first."

        data = {}
        if api_key:
            data["api_key"] = api_key
        if base_url:
            data["base_url"] = base_url
        if model_mapping:
            data["model_mapping"] = model_mapping
        if config:
            data["config"] = config

        success, result = await self._make_request(
            "PUT", f"/provider-keys/{provider_name}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"
            },
            json=data
        )
        
        message = f"Successfully updated {provider_name} API key!" if success else result
        return success, message if isinstance(message, str) else "Update failed"

    async def delete_provider_key(self, provider_name: str) -> tuple[bool, str]:
        """Delete a provider key"""
        if not self.token:
            return False, "Not authenticated. Please login first."

        success, result = await self._make_request(
            "DELETE", f"/provider-keys/{provider_name}",
            headers={"Authorization": f"Bearer {self.token}"}
        )
        
        message = f"Successfully deleted provider key {provider_name}!" if success else result
        return success, message if isinstance(message, str) else "Delete failed"

    async def test_chat_completion(self, model: str, message: str, api_key: str = None) -> tuple[bool, dict | str]:
        """Test chat completion"""
        key = api_key or self.forge_api_key
        if not key:
            return False, "No API key provided"

        data = {
            "model": model,
            "messages": [{"role": "user", "content": message}]
        }

        success, result = await self._make_request(
            "POST", "/chat/completions",
            headers={
                "Content-Type": "application/json",
                "X-API-KEY": key
            },
            json=data
        )
        return success, result

    async def list_models(self, api_key: str = None) -> tuple[bool, List[str] | str]:
        """List available models"""
        key = api_key or self.forge_api_key
        if not key:
            return False, "No API key provided"

        success, result = await self._make_request(
            "GET", "/models",
            headers={
                "Content-Type": "application/json",
                "X-API-KEY": key
            }
        )
        
        if success and isinstance(result, dict):
            return True, result.get("data", [])
        return success, result


class LoginScreen(ModalScreen[bool]):
    """Login modal screen"""

    def compose(self) -> ComposeResult:
        with Container(id="login-dialog"):
            yield Static("🔐 Login to Forge", id="login-title")
            yield Input(placeholder="Username", id="username")
            yield Input(placeholder="Password", password=True, id="password")
            with Horizontal():
                yield Button("Login", variant="primary", id="login-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    @on(Button.Pressed, "#login-btn")
    async def handle_login(self):
        username = self.query_one("#username", Input).value
        password = self.query_one("#password", Input).value
        
        if not username or not password:
            self.app.notify("Please enter both username and password", severity="error")
            return

        forge_api = self.app.forge_api
        success, message = await forge_api.login(username, password)
        
        if success:
            self.app.notify(message, severity="information")
            self.dismiss(True)
        else:
            self.app.notify(f"Login failed: {message}", severity="error")

    @on(Button.Pressed, "#cancel-btn")
    def handle_cancel(self):
        self.dismiss(False)


class RegisterScreen(ModalScreen[bool]):
    """Registration modal screen"""

    def compose(self) -> ComposeResult:
        with Container(id="register-dialog"):
            yield Static("📝 Register for Forge", id="register-title")
            yield Input(placeholder="Username", id="username")
            yield Input(placeholder="Email", id="email")
            yield Input(placeholder="Password", password=True, id="password")
            with Horizontal():
                yield Button("Register", variant="primary", id="register-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    @on(Button.Pressed, "#register-btn")
    async def handle_register(self):
        username = self.query_one("#username", Input).value
        email = self.query_one("#email", Input).value
        password = self.query_one("#password", Input).value
        
        if not all([username, email, password]):
            self.app.notify("Please fill in all fields", severity="error")
            return

        forge_api = self.app.forge_api
        success, message = await forge_api.register(username, email, password)
        
        if success:
            self.app.notify(message, severity="information")
            self.dismiss(True)
        else:
            self.app.notify(f"Registration failed: {message}", severity="error")

    @on(Button.Pressed, "#cancel-btn")
    def handle_cancel(self):
        self.dismiss(False)


class CreateAPIKeyScreen(ModalScreen[bool]):
    """Create API Key modal screen"""

    def compose(self) -> ComposeResult:
        with Container(id="api-key-dialog"):
            yield Static("🔑 Create Forge API Key", id="api-key-title")
            yield Input(placeholder="Key Name (optional)", id="key-name")
            yield Input(placeholder="Provider Key IDs (comma-separated, optional)", id="provider-ids")
            with Horizontal():
                yield Button("Create", variant="primary", id="create-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    @on(Button.Pressed, "#create-btn")
    async def handle_create(self):
        key_name = self.query_one("#key-name", Input).value or None
        provider_ids_str = self.query_one("#provider-ids", Input).value
        
        allowed_provider_key_ids = None
        if provider_ids_str:
            try:
                allowed_provider_key_ids = [int(id.strip()) for id in provider_ids_str.split(",")]
            except ValueError:
                self.app.notify("Invalid provider IDs format", severity="error")
                return

        forge_api = self.app.forge_api
        success, result = await forge_api.create_forge_api_key(key_name, allowed_provider_key_ids)
        
        if success:
            if isinstance(result, dict) and result.get("key"):
                # Show the created API key
                api_key = result["key"]
                await self.app.push_screen(ShowAPIKeyScreen(api_key))
            self.app.notify("API key created successfully!", severity="information")
            self.dismiss(True)
        else:
            self.app.notify(f"Failed to create API key: {result}", severity="error")

    @on(Button.Pressed, "#cancel-btn")
    def handle_cancel(self):
        self.dismiss(False)


class ShowAPIKeyScreen(ModalScreen[bool]):
    """Show created API Key modal screen"""

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    def compose(self) -> ComposeResult:
        with Container(id="show-key-dialog"):
            yield Static("🔑 Your New API Key", id="show-key-title")
            yield Static("⚠️ Please copy and save this key now. You won't be able to see it again!", classes="warning")
            yield Input(value=self.api_key, id="api-key-display", disabled=True)
            with Horizontal():
                yield Button("Copy to Clipboard", variant="primary", id="copy-btn")
                yield Button("Close", variant="default", id="close-btn")

    @on(Button.Pressed, "#copy-btn")
    def handle_copy(self):
        # Note: Actual clipboard functionality would require additional libraries
        self.app.notify("API key copied to selection (use Ctrl+C to copy)", severity="information")

    @on(Button.Pressed, "#close-btn")
    def handle_close(self):
        self.dismiss(True)


class AddProviderScreen(ModalScreen[bool]):
    """Add Provider Key modal screen"""

    def compose(self) -> ComposeResult:
        with Container(id="provider-dialog"):
            yield Static("🔌 Add Provider Key", id="provider-title")
            yield Input(placeholder="Provider Name", id="provider-name")
            yield Input(placeholder="API Key", password=True, id="api-key")
            yield Input(placeholder="Base URL (optional)", id="base-url")
            yield Static("Model Mapping JSON (optional):")
            yield TextArea(text="", id="model-mapping")
            yield Static("Config JSON (optional):")
            yield TextArea(text="", id="config")
            with Horizontal():
                yield Button("Add", variant="primary", id="add-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    @on(Button.Pressed, "#add-btn")
    async def handle_add(self):
        provider_name = self.query_one("#provider-name", Input).value
        api_key = self.query_one("#api-key", Input).value
        base_url = self.query_one("#base-url", Input).value or None
        model_mapping_str = self.query_one("#model-mapping", TextArea).text
        config_str = self.query_one("#config", TextArea).text
        
        if not provider_name or not api_key:
            self.app.notify("Provider name and API key are required", severity="error")
            return

        model_mapping = None
        config = None
        
        try:
            if model_mapping_str:
                model_mapping = json.loads(model_mapping_str)
            if config_str:
                config = json.loads(config_str)
        except json.JSONDecodeError as e:
            self.app.notify(f"Invalid JSON format: {e}", severity="error")
            return

        forge_api = self.app.forge_api
        success, message = await forge_api.add_provider_key(
            provider_name, api_key, base_url, model_mapping, config
        )
        
        if success:
            self.app.notify(message, severity="information")
            self.dismiss(True)
        else:
            self.app.notify(f"Failed to add provider: {message}", severity="error")

    @on(Button.Pressed, "#cancel-btn")
    def handle_cancel(self):
        self.dismiss(False)


class UpdateProviderScreen(ModalScreen[bool]):
    """Update Provider Key modal screen"""

    def __init__(self, provider_data: dict):
        super().__init__()
        self.provider_data = provider_data
        self.provider_name = provider_data.get('provider_name', '')

    def compose(self) -> ComposeResult:
        with Container(id="provider-dialog"):
            yield Static(f"🔌 Update Provider: {self.provider_name}", id="provider-title")
            yield Label("Provider Name (read-only):")
            yield Input(value=self.provider_name, disabled=True, id="provider-name")
            yield Label("API Key (leave empty to keep current):")
            yield Input(placeholder="Enter new API key or leave empty", password=True, id="api-key")
            yield Label("Base URL:")
            yield Input(
                placeholder="Base URL (optional)", 
                id="base-url",
                value=self.provider_data.get('base_url', '') or ''
            )
            yield Static("Model Mapping JSON (leave empty to keep current):")
            yield TextArea(
                text=json.dumps(self.provider_data.get('model_mapping'), indent=2) 
                     if self.provider_data.get('model_mapping') else "", 
                id="model-mapping"
            )
            yield Static("Config JSON (leave empty to keep current):")
            yield TextArea(
                text=json.dumps(self.provider_data.get('config'), indent=2) 
                     if self.provider_data.get('config') else "", 
                id="config"
            )
            with Horizontal():
                yield Button("Update", variant="primary", id="update-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    @on(Button.Pressed, "#update-btn")
    async def handle_update(self):
        api_key = self.query_one("#api-key", Input).value.strip()
        base_url = self.query_one("#base-url", Input).value.strip()
        model_mapping_str = self.query_one("#model-mapping", TextArea).text.strip()
        config_str = self.query_one("#config", TextArea).text.strip()
        
        # Prepare update data - only include fields that have values
        update_data = {}
        
        if api_key:
            update_data['api_key'] = api_key
            
        if base_url:
            update_data['base_url'] = base_url
            
        if model_mapping_str:
            try:
                update_data['model_mapping'] = json.loads(model_mapping_str)
            except json.JSONDecodeError as e:
                self.app.notify(f"Invalid Model Mapping JSON: {e}", severity="error")
                return
                
        if config_str:
            try:
                update_data['config'] = json.loads(config_str)
            except json.JSONDecodeError as e:
                self.app.notify(f"Invalid Config JSON: {e}", severity="error")
                return
        
        if not update_data:
            self.app.notify("No changes to update", severity="warning")
            return

        forge_api = self.app.forge_api
        success, message = await forge_api.update_provider_key(
            self.provider_name, 
            **update_data
        )
        
        if success:
            self.app.notify(f"Provider {self.provider_name} updated successfully!", severity="information")
            self.dismiss(True)
        else:
            self.app.notify(f"Failed to update provider: {message}", severity="error")

    @on(Button.Pressed, "#cancel-btn")
    def handle_cancel(self):
        self.dismiss(False)


class UpdateAPIKeyScreen(ModalScreen[bool]):
    """Update API Key modal screen"""

    def __init__(self, key_id: str, key_name: str):
        super().__init__()
        self.key_id = key_id
        self.current_name = key_name

    def compose(self) -> ComposeResult:
        with Container(id="api-key-dialog"):
            yield Static("🔑 Update API Key", id="api-key-title")
            yield Label("New Name:")
            yield Input(
                placeholder="Enter new API key name",
                id="api-key-name",
                value=self.current_name
            )
            with Horizontal():
                yield Button("Update", variant="primary", id="update-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    @on(Button.Pressed, "#update-btn")
    async def handle_update(self):
        name_input = self.query_one("#api-key-name", Input)
        new_name = name_input.value.strip()
        
        if not new_name:
            self.app.notify("API key name cannot be empty", severity="error")
            return
            
        if new_name == self.current_name:
            self.app.notify("No changes made", severity="warning")
            self.dismiss(False)
            return

        forge_api = self.app.forge_api
        success, result = await forge_api.update_forge_api_key(int(self.key_id), name=new_name)
        
        if success:
            self.app.notify("API key updated successfully!", severity="information")
            self.dismiss(True)
        else:
            self.app.notify(f"Failed to update API key: {result}", severity="error")

    @on(Button.Pressed, "#cancel-btn")
    def handle_cancel(self):
        self.dismiss(False)


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Confirmation dialog for delete operations"""

    def __init__(self, item_type: str, item_name: str):
        super().__init__()
        self.item_type = item_type
        self.item_name = item_name

    def compose(self) -> ComposeResult:
        with Container(id="action-dialog"):
            yield Static(f"⚠️ Confirm Delete {self.item_type}", id="action-title")
            yield Static(f"Are you sure you want to delete {self.item_type}: {self.item_name}?", classes="warning")
            yield Static("This action cannot be undone!", classes="warning")
            with Horizontal():
                yield Button("Delete", variant="error", id="confirm-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    @on(Button.Pressed, "#confirm-btn")
    def handle_confirm(self):
        self.dismiss(True)
    @on(Button.Pressed, "#cancel-btn")
    def handle_cancel(self):
        self.dismiss(False)


class APIKeyActionScreen(ModalScreen[bool]):
    """API Key action modal screen"""

    def __init__(self, key_id: str, key_name: str):
        super().__init__()
        self.key_id = key_id
        self.key_name = key_name

    def compose(self) -> ComposeResult:
        with Container(id="action-dialog"):
            yield Static(f"🔑 Manage API Key: {self.key_name}", id="action-title")
            with Horizontal():
                yield Button("Update", variant="primary", id="update-btn")
                yield Button("Delete", variant="error", id="delete-btn")
                yield Button("Toggle Active", variant="warning", id="toggle-active-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    @on(Button.Pressed, "#update-btn")
    async def handle_update(self):
        # Launch update screen
        result = await self.app.push_screen(UpdateAPIKeyScreen(self.key_id, self.key_name))
        if result:
            self.dismiss(True)

    @on(Button.Pressed, "#delete-btn")
    async def handle_delete(self):
        # Show confirmation first
        confirm = await self.app.push_screen(ConfirmDeleteScreen("API Key", self.key_name))
        self.app.notify(f"Confirm: {confirm}")
        if not confirm:
            self.dismiss(False)
            return
            
        forge_api = self.app.forge_api
        success, message = await forge_api.delete_forge_api_key(int(self.key_id))
        
        if success:
            self.app.notify("API key deleted successfully!", severity="information")
            self.dismiss(True)
        else:
            self.app.notify(f"Failed to delete API key: {message}", severity="error")

    @on(Button.Pressed, "#toggle-active-btn")
    async def handle_toggle_active(self):
        forge_api = self.app.forge_api
        # First get current status
        success, keys = await forge_api.list_forge_api_keys()
        if not success:
            self.app.notify("Failed to get current key status", severity="error")
            return
            
        current_key = None
        for key in keys:
            if str(key.get('id')) == self.key_id:
                current_key = key
                break
                
        if not current_key:
            self.app.notify("Key not found", severity="error")
            return
            
        new_status = not current_key.get('is_active', True)
        success, result = await forge_api.update_forge_api_key(int(self.key_id), is_active=new_status)
        
        if success:
            status_text = "activated" if new_status else "deactivated"
            self.app.notify(f"API key {status_text} successfully!", severity="information")
            self.dismiss(True)
        else:
            self.app.notify(f"Failed to update API key: {result}", severity="error")

    @on(Button.Pressed, "#cancel-btn")
    def handle_cancel(self):
        self.dismiss(False)


class ProviderActionScreen(ModalScreen[bool]):
    """Provider action modal screen"""

    def __init__(self, provider_name: str):
        super().__init__()
        self.provider_name = provider_name

    def compose(self) -> ComposeResult:
        with Container(id="action-dialog"):
            yield Static(f"🔌 Manage Provider: {self.provider_name}", id="action-title")
            with Horizontal():
                yield Button("Update", variant="primary", id="update-btn")
                yield Button("Delete", variant="error", id="delete-btn")
                yield Button("Cancel", variant="default", id="cancel-btn")

    @on(Button.Pressed, "#update-btn")
    async def handle_update(self):
        # Get current provider data first
        forge_api = self.app.forge_api
        success, providers = await forge_api.list_provider_keys()
        if not success:
            self.app.notify("Failed to get provider data", severity="error")
            return
            
        current_provider = None
        for provider in providers:
            if provider.get('provider_name') == self.provider_name:
                current_provider = provider
                break
                
        if not current_provider:
            self.app.notify("Provider not found", severity="error")
            return
            
        # Launch update screen with current data
        result = await self.app.push_screen(UpdateProviderScreen(current_provider))
        if result:
            self.dismiss(True)

    @on(Button.Pressed, "#delete-btn")
    async def handle_delete(self):
        # Show confirmation first
        confirm = await self.app.push_screen(ConfirmDeleteScreen("Provider", self.provider_name))
        if not confirm:
            return
            
        forge_api = self.app.forge_api
        success, message = await forge_api.delete_provider_key(self.provider_name)
        
        if success:
            self.app.notify("Provider deleted successfully!", severity="information")
            self.dismiss(True)
        else:
            self.app.notify(f"Failed to delete provider: {message}", severity="error")

    @on(Button.Pressed, "#cancel-btn")
    def handle_cancel(self):
        self.dismiss(False)


class AuthTab(Static):
    """Authentication tab content"""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("🔐 Authentication", classes="tab-title")
            with Horizontal(classes="auth-buttons"):
                yield Button("Login", id="login-button", variant="primary")
                yield Button("Register", id="register-button", variant="default")
                yield Button("Get User Info", id="user-info-button", variant="default")
            yield Static("", id="auth-status")

    @on(Button.Pressed, "#login-button")
    async def handle_login(self):
        result = await self.app.push_screen(LoginScreen())
        if result:
            await self.update_auth_status()
            await self.handle_user_info()  # 自动显示用户信息

    @on(Button.Pressed, "#register-button")
    async def handle_register(self):
        result = await self.app.push_screen(RegisterScreen())
        if result:
            await self.update_auth_status()
            await self.handle_user_info()  # 自动显示用户信息

    @on(Button.Pressed, "#user-info-button")
    async def handle_user_info(self):
        forge_api = self.app.forge_api
        success, result = await forge_api.get_user_info()
        
        if success:
            user_info = f"User: {result.get('username', 'N/A')}\n"
            user_info += f"Email: {result.get('email', 'N/A')}\n"
            
            # Get API keys and set the first one as default (like original CLI)
            api_keys = result.get('forge_api_keys', [])
            if api_keys:
                user_info += f"API Keys: {len(api_keys)}\n"
                # Display all API keys like in original CLI
                for i, key in enumerate(api_keys, 1):
                    if isinstance(key, dict):
                        key_display = key.get('key', str(key))
                    else:
                        key_display = str(key)
                    user_info += f"  {i}. {key_display}\n"
                
                # Set the first API key as the default if we don't have one
                if not forge_api.forge_api_key and api_keys:
                    first_key = api_keys[0]
                    if isinstance(first_key, dict):
                        forge_api.forge_api_key = first_key.get('key')
                    else:
                        forge_api.forge_api_key = str(first_key)
                    
                    if forge_api.forge_api_key:
                        user_info += f"Default API Key: {forge_api.forge_api_key[:8]}..."
            else:
                user_info += "⚠️ No API keys found"
                
            self.query_one("#auth-status").update(user_info)
        else:
            self.app.notify(f"Failed to get user info: {result}", severity="error")

    async def update_auth_status(self):
        forge_api = self.app.forge_api
        if forge_api.token:
            self.query_one("#auth-status").update("✅ Authenticated")
        else:
            self.query_one("#auth-status").update("❌ Not authenticated")


class APIKeysTab(Static):
    """API Keys management tab"""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("🔑 Forge API Keys", classes="tab-title")
            with Horizontal(classes="key-buttons"):
                yield Button("Create API Key", id="create-key-button", variant="primary")
                yield Button("Refresh List", id="refresh-keys-button", variant="default")
            yield DataTable(id="api-keys-table")

    async def on_mount(self):
        table = self.query_one("#api-keys-table", DataTable)
        table.cursor_type = "row"  # Enable row selection
        table.zebra_stripes = True  # Better visual feedback
        table.add_columns("ID", "Name", "Active", "Created", "Last Used", "Actions")
        await self.refresh_api_keys()

    @on(DataTable.RowSelected)
    async def handle_row_selected(self, event: DataTable.RowSelected):
        """Handle row selection for actions"""
        # Add debug info
        self.app.notify("API Key row clicked!", severity="information")
        
        table = event.data_table
        row_key = event.row_key
        row_data = table.get_row(row_key)
        key_id = row_data[0]  # ID is first column
        
        self.app.notify(f"Selected key ID: {key_id}, Name: {row_data[1]}", severity="information")
        
        # Show action menu
        result = await self.app.push_screen(APIKeyActionScreen(key_id, row_data[1]))
        if result:
            await self.refresh_api_keys()

    @on(Button.Pressed, "#create-key-button")
    async def handle_create_key(self):
        result = await self.app.push_screen(CreateAPIKeyScreen())
        if result:
            await self.refresh_api_keys()

    @on(Button.Pressed, "#refresh-keys-button")
    async def refresh_api_keys(self):
        forge_api = self.app.forge_api
        success, result = await forge_api.list_forge_api_keys()
        
        table = self.query_one("#api-keys-table", DataTable)
        table.clear()
        
        if success and isinstance(result, list):
            for key_data in result:
                table.add_row(
                    str(key_data.get('id', 'N/A')),
                    key_data.get('name', 'N/A'),
                    "✅" if key_data.get('is_active') else "❌",
                    key_data.get('created_at', 'N/A')[:10] if key_data.get('created_at') else 'N/A',
                    key_data.get('last_used_at', 'Never')[:10] if key_data.get('last_used_at') else 'Never',
                    "Click to manage"
                )
        else:
            self.app.notify(f"Failed to load API keys: {result}", severity="error")


class ProvidersTab(Static):
    """Provider keys management tab"""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("🔌 Provider Keys", classes="tab-title")
            with Horizontal(classes="provider-buttons"):
                yield Button("Add Provider", id="add-provider-button", variant="primary")
                yield Button("Refresh List", id="refresh-providers-button", variant="default")
            yield DataTable(id="providers-table")

    async def on_mount(self):
        table = self.query_one("#providers-table", DataTable)
        table.cursor_type = "row"  # Enable row selection
        table.zebra_stripes = True  # Better visual feedback
        table.add_columns("ID", "Provider", "Base URL", "Created", "Actions")
        await self.refresh_providers()

    @on(DataTable.RowSelected)
    async def handle_row_selected(self, event: DataTable.RowSelected):
        """Handle row selection for actions"""
        # Add debug info
        self.app.notify("Provider row clicked!", severity="information")
        
        table = event.data_table
        row_key = event.row_key
        row_data = table.get_row(row_key)
        provider_name = row_data[1]  # Provider name is second column
        
        self.app.notify(f"Selected provider: {provider_name}", severity="information")
        
        # Show action menu
        result = await self.app.push_screen(ProviderActionScreen(provider_name))
        if result:
            await self.refresh_providers()

    @on(Button.Pressed, "#add-provider-button")
    async def handle_add_provider(self):
        result = await self.app.push_screen(AddProviderScreen())
        if result:
            await self.refresh_providers()

    @on(Button.Pressed, "#refresh-providers-button")
    async def refresh_providers(self):
        forge_api = self.app.forge_api
        success, result = await forge_api.list_provider_keys()
        
        table = self.query_one("#providers-table", DataTable)
        table.clear()
        
        if success and isinstance(result, list):
            for provider_data in result:
                table.add_row(
                    str(provider_data.get('id', 'N/A')),
                    provider_data.get('provider_name', 'N/A'),
                    provider_data.get('base_url', 'N/A'),
                    provider_data.get('created_at', 'N/A')[:10] if provider_data.get('created_at') else 'N/A',
                    "Click to manage"
                )
        else:
            self.app.notify(f"Failed to load providers: {result}", severity="error")


class TestingTab(Static):
    """Testing and models tab"""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("🧪 Testing & Models", classes="tab-title")
            
            # Control buttons
            with Horizontal(classes="test-buttons"):
                yield Button("List Models", id="list-models-button", variant="primary")
                yield Button("Test Chat", id="test-chat-button", variant="default")
            
            # Main content area with proper scrolling
            with Horizontal(classes="testing-main"):
                # Left panel - inputs with scroll
                with Vertical(classes="testing-inputs"):
                    yield Static("🔧 Input Parameters", classes="section-title")
                    with ScrollableContainer(classes="inputs-scroll"):
                        with Vertical():
                            yield Static("🔑 API Key:", classes="input-label")
                            yield Input(placeholder="Enter Forge API Key", id="api-key-input")
                            
                            yield Static("🤖 Model:", classes="input-label")
                            yield Input(placeholder="e.g., openai/gpt-4", id="model-input")
                            
                            yield Static("💬 Message:", classes="input-label")
                            yield Input(placeholder="Enter test message", id="message-input")
                            
                            yield Button("🚀 Send Test", id="send-test-button", variant="success")
                
                # Right panel - models list with scroll
                with Vertical(classes="testing-models"):
                    yield Static("📋 Available Models", classes="section-title")
                    with ScrollableContainer(classes="models-scroll"):
                        yield Static("Click 'List Models' to load available models", id="models-list")
            
            # Bottom panel - results with scroll
            with Vertical(classes="testing-results"):
                yield Static("📊 Test Results", classes="section-title")
                with ScrollableContainer(classes="results-scroll"):
                    yield Static("No test results yet. Use the form above to test a model.", id="test-results")

    @on(Button.Pressed, "#list-models-button")
    async def handle_list_models(self):
        forge_api = self.app.forge_api
        
        # Get API key from input field or use stored key (like original CLI)
        api_key_input = self.query_one("#api-key-input", Input).value.strip()
        
        if api_key_input:
            # User provided an API key
            api_key = api_key_input
            self.app.notify(f"Using provided API key: {api_key[:8]}...", severity="information")
        elif forge_api.forge_api_key:
            # Use stored API key
            api_key = forge_api.forge_api_key
            self.app.notify(f"Using stored API key: {api_key[:8]}...", severity="information")
        else:
            # No API key available, try to get one from user info
            success, result = await forge_api.get_user_info()
            if success and result.get('forge_api_keys'):
                api_keys = result['forge_api_keys']
                if api_keys:
                    # Handle both string format and dict format like original CLI
                    first_key = api_keys[0]
                    if isinstance(first_key, dict):
                        api_key = first_key.get('key')
                    else:
                        api_key = str(first_key)
                    
                    if api_key:
                        forge_api.forge_api_key = api_key  # Store for future use
                        self.app.notify(f"Using API key from user info: {api_key[:8]}...", severity="information")
                    else:
                        api_key = None
                else:
                    api_key = None
            else:
                api_key = None
        
        # Check if we have an API key
        if not api_key:
            self.app.notify("❌ No API key available. Please enter an API key or create one first.", severity="error")
            models_widget = self.query_one("#models-list", Static)
            models_widget.update("❌ No API key available. Please enter an API key in the input field above.")
            return
        
        self.app.notify("Loading models...", severity="information")
        success, result = await forge_api.list_models(api_key)
        
        models_widget = self.query_one("#models-list", Static)
        if success and isinstance(result, list):
            if result:
                # Display models like in the original CLI
                models_text = "✅ Available models:\n"
                for model in result:
                    if isinstance(model, dict):
                        model_id = model.get('id', str(model))
                    else:
                        model_id = str(model)
                    models_text += f"  - {model_id}\n"
                models_widget.update(models_text.strip())
                self.app.notify(f"Loaded {len(result)} models", severity="information")
            else:
                models_widget.update("No models available")
                self.app.notify("No models found", severity="warning")
        else:
            error_msg = f"❌ Error loading models: {result}"
            models_widget.update(error_msg)
            self.app.notify(f"Failed to load models: {result}", severity="error")

    @on(Button.Pressed, "#test-chat-button")
    @on(Button.Pressed, "#send-test-button")
    async def handle_test_chat(self):
        model = self.query_one("#model-input", Input).value
        message = self.query_one("#message-input", Input).value
        
        if not model or not message:
            self.app.notify("Please enter both model and message", severity="error")
            return

        forge_api = self.app.forge_api
        
        # Get API key from input field or use stored key (like original CLI)
        api_key_input = self.query_one("#api-key-input", Input).value.strip()
        
        if api_key_input:
            # User provided an API key
            api_key = api_key_input
            self.app.notify(f"Using provided API key: {api_key[:8]}...", severity="information")
        elif forge_api.forge_api_key:
            # Use stored API key
            api_key = forge_api.forge_api_key
            self.app.notify(f"Using stored API key: {api_key[:8]}...", severity="information")
        else:
            # No API key available, try to get one from user info
            success, result = await forge_api.get_user_info()
            if success and result.get('forge_api_keys'):
                api_keys = result['forge_api_keys']
                if api_keys:
                    # Handle both string format and dict format like original CLI
                    first_key = api_keys[0]
                    if isinstance(first_key, dict):
                        api_key = first_key.get('key')
                    else:
                        api_key = str(first_key)
                    
                    if api_key:
                        forge_api.forge_api_key = api_key  # Store for future use
                        self.app.notify(f"Using API key from user info: {api_key[:8]}...", severity="information")
                    else:
                        api_key = None
                else:
                    api_key = None
            else:
                api_key = None
        
        # Check if we have an API key
        if not api_key:
            self.app.notify("❌ No API key available. Please enter an API key or create one first.", severity="error")
            results_widget = self.query_one("#test-results", Static)
            results_widget.update("❌ No API key available. Please enter an API key in the input field above.")
            return
        
        self.app.notify("Sending test message...", severity="information")
        success, result = await forge_api.test_chat_completion(model, message, api_key)
        
        results_widget = self.query_one("#test-results", Static)
        if success:
            if isinstance(result, dict) and 'choices' in result:
                response_content = result.get('choices', [{}])[0].get('message', {}).get('content', 'No response')
                results_widget.update(f"✅ Chat completion successful!\nResponse: {response_content}")
            else:
                results_widget.update(f"✅ Success: {result}")
            self.app.notify("Chat completion successful!", severity="information")
        else:
            results_widget.update(f"❌ Test failed: {result}")
            self.app.notify(f"Test failed: {result}", severity="error")


class ForgeApp(App):
    """Main Forge TUI Application"""
    
    # Load external CSS file
    CSS_PATH = Path(__file__).parent / "styles.tcss"
    
    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("f1", "toggle_dark", "Toggle Dark Mode"),
        Binding("f2", "refresh_all", "Refresh All Data"),
        Binding("ctrl+n", "new_api_key", "New API Key"),
        Binding("ctrl+p", "new_provider", "New Provider"),
    ]

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.forge_api = ForgeAPI(self.config)
        self.title = "Forge TUI - Middleware Service Manager"
        self.sub_title = "Unified AI Provider Management"
        
        # Set theme based on config
        theme = self.config.get('ui', 'default_theme', 'dark').lower()
        self.dark = theme == 'dark'
        
        # Auto-refresh timer
        self.auto_refresh_timer = None
        self.auto_refresh_interval = self.config.getint('ui', 'auto_refresh_interval', 0)

    def compose(self) -> ComposeResult:
        with Container():
            with Horizontal(classes="header-container"):
                yield Header(show_clock=True)
                yield Button("Exit", id="exit-button", variant="error", classes="exit-btn")
            with TabbedContent(initial="auth"):
                with TabPane("🔐 Authentication", id="auth"):
                    yield AuthTab()
                with TabPane("🔑 API Keys", id="api-keys"):
                    yield APIKeysTab()
                with TabPane("🔌 Providers", id="providers"):
                    yield ProvidersTab()
                with TabPane("🧪 Testing", id="testing"):
                    yield TestingTab()
            yield Footer()

    def action_toggle_dark(self) -> None:
        """Toggle dark mode"""
        self.dark = not self.dark
        self.notify(f"Dark mode: {'On' if self.dark else 'Off'}")

    def action_refresh_all(self) -> None:
        """Refresh all data"""
        self.notify("Refreshing all data...", severity="information")
        # Trigger refresh on all tabs
        for tab in ["api-keys", "providers"]:
            try:
                tab_widget = self.query_one(f"#{tab}")
                if hasattr(tab_widget, 'refresh_data'):
                    tab_widget.refresh_data()
            except:
                pass

    async def action_new_api_key(self) -> None:
        """Quick create new API key"""
        result = await self.push_screen(CreateAPIKeyScreen())
        if result:
            self.notify("API key created successfully!", severity="information")

    async def action_new_provider(self) -> None:
        """Quick add new provider"""
        result = await self.push_screen(AddProviderScreen())
        if result:
            self.notify("Provider added successfully!", severity="information")

    def action_quit(self) -> None:
        """Quit the application"""
        self.exit()

    @on(Button.Pressed, "#exit-button")
    def handle_exit_button(self) -> None:
        """Handle exit button press"""
        self.exit()

    def on_mount(self) -> None:
        """Called when app starts"""
        self.notify("Welcome to Forge TUI! Press F1 to toggle dark mode.", severity="information")
        
        # Set up auto-refresh timer if configured
        if self.auto_refresh_interval > 0:
            self.auto_refresh_timer = self.set_interval(
                self.auto_refresh_interval,
                self._auto_refresh
            )
        
        # Perform initial health check
        self.call_later(self._initial_health_check)

    async def _initial_health_check(self):
        """Check server health on startup"""
        success, message = await self.forge_api.health_check()
        if success:
            self.notify("✅ Connected to Forge server", severity="information")
        else:
            self.notify(f"⚠️ Server connection issue: {message}", severity="warning")

    def _auto_refresh(self):
        """Auto-refresh data periodically"""
        if self.forge_api.token:
            try:
                # Refresh current tab data asynchronously
                self.call_later(self._do_auto_refresh)
            except Exception as e:
                # Silent fail for auto-refresh
                pass

    async def _do_auto_refresh(self):
        """Actually perform the auto-refresh operation"""
        try:
            # Refresh current tab data
            current_tab = self.query_one(TabbedContent).active
            if current_tab in ["api-keys", "providers"]:
                tab_widget = self.query_one(f"#{current_tab}")
                if hasattr(tab_widget, 'refresh_data'):
                    await tab_widget.refresh_data()
        except Exception as e:
            # Silent fail for auto-refresh
            pass

    def format_datetime(self, dt_str: str) -> str:
        """Format datetime string for display"""
        if not dt_str or dt_str == 'Never':
            return 'Never'
        try:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M')
        except:
            return dt_str[:16] if len(dt_str) > 16 else dt_str

    def truncate_text(self, text: str, max_length: int = None) -> str:
        """Truncate text if too long"""
        if not max_length:
            max_length = self.config.getint('display', 'max_text_length', 50)
        
        if not text or len(text) <= max_length:
            return text
        
        return text[:max_length-3] + "..."


def main():
    """Run the Forge TUI application"""
    app = ForgeApp()
    app.run()


if __name__ == "__main__":
    main()
