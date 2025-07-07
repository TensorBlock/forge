#!/usr/bin/env python3
import json
from getpass import getpass
from http import HTTPStatus
from typing import Any

import requests


class ForgeManager:
    """A tool for managing the Forge middleware service"""

    def __init__(self, api_url: str = "http://localhost:8000/v1"):
        self.api_url = api_url
        self.token = None
        self.forge_api_key = None

    def register(self, username: str, email: str, password: str) -> bool:
        """Register a new user"""
        url = f"{self.api_url}/auth/register"
        data = {"username": username, "email": email, "password": password}

        try:
            response = requests.post(url, json=data)

            if response.status_code == HTTPStatus.OK:
                user_data = response.json()
                if user_data.get("forge_api_keys"):
                    self.forge_api_key = user_data["forge_api_keys"][0]
                print(f"✅ User {username} registered successfully!")
                print(f"🔑 Forge API Key: {self.forge_api_key}")
                return True
            else:
                print(f"❌ Registration failed: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"❌ Error during registration: {str(e)}")
            return False

    def login(self, username: str, password: str) -> bool:
        """Login and get a JWT token"""
        url = f"{self.api_url}/auth/token"
        data = {"username": username, "password": password}

        try:
            response = requests.post(url, data=data)

            if response.status_code == HTTPStatus.OK:
                token_data = response.json()
                self.token = token_data["access_token"]
                print("✅ Login successful!")
                return True
            else:
                print(f"❌ Login failed: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"❌ Error during login: {str(e)}")
            return False

    def get_user_info(self) -> dict | None:
        """Get current user information"""
        if not self.token:
            print("❌ Not authenticated. Please login first.")
            return None

        url = f"{self.api_url}/users/me"
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            response = requests.get(url, headers=headers)

            if response.status_code == HTTPStatus.OK:
                user_data = response.json()
                print("✅ User information retrieved successfully!")

                # Display all API keys if available
                if user_data.get("forge_api_keys"):
                    print("🔑 Forge API Keys:")
                    for i, key in enumerate(user_data["forge_api_keys"], 1):
                        print(f"  {i}. {key}")
                else:
                    print("⚠️ No API keys found")

                return user_data
            else:
                print(f"❌ Failed to get user info: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"❌ Error getting user info: {str(e)}")
            return None

    def create_forge_api_key(
        self, name: str | None, allowed_provider_key_ids: list[int] | None
    ) -> dict | None:
        """Create a new Forge API key with an optional name and scope"""
        if not self.token:
            print("❌ Not authenticated. Please login first.")
            return None

        url = f"{self.api_url}/api-keys/"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {}
        if name:
            payload["name"] = name
        if (
            allowed_provider_key_ids is not None
        ):  # Empty list means scope to no providers
            payload["allowed_provider_key_ids"] = allowed_provider_key_ids
        # If allowed_provider_key_ids is None (user skipped input), the field is omitted,
        # and backend defaults (currently means no specific provider restrictions by this key)

        try:
            response = requests.post(url, headers=headers, json=payload)

            if (
                response.status_code == HTTPStatus.OK
            ):  # Assuming 200 OK for create, FastAPI often returns 201 Created
                # Let's adjust if backend returns 201. For now, expecting 200 from existing pattern.
                new_key_data = response.json()
                print("✅ Forge API Key created successfully!")
                print(f"   ID: {new_key_data.get('id')}")
                print(
                    f"   Key: {new_key_data.get('key')} (This is the actual key, save it securely!)"
                )
                print(f"   Name: {new_key_data.get('name', 'N/A')}")
                print(f"   Active: {new_key_data.get('is_active')}")
                print(f"   Created At: {new_key_data.get('created_at')}")
                print(
                    f"   Allowed Provider Key IDs: {new_key_data.get('allowed_provider_key_ids', [])}"
                )
                # Update self.forge_api_key if it's still used by other parts of CLI for default tests
                if not self.forge_api_key:  # Or based on some other logic
                    self.forge_api_key = new_key_data.get("key")
                return new_key_data
            else:
                print(f"❌ Failed to create Forge API key: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"❌ Error creating Forge API key: {str(e)}")
            return None

    def add_provider_key(
        self,
        provider_name: str,
        api_key: str,
        base_url: str | None = None,
        model_mapping: dict[str, str] | None = None,
        config: dict[str, str] | None = None,
    ) -> bool:
        """Add a provider key"""
        if not self.token:
            print("❌ Not authenticated. Please login first.")
            return False

        url = f"{self.api_url}/provider-keys/"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        data = {
            "provider_name": provider_name,
            "api_key": api_key,
            "base_url": base_url,
            "model_mapping": model_mapping,
            "config": json.loads(config) if config else None,
        }

        try:
            response = requests.post(url, headers=headers, json=data)

            if response.status_code == HTTPStatus.OK:
                print(f"✅ Successfully added {provider_name} API key!")
                return True
            else:
                print(f"❌ Error adding provider key: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"❌ Error adding provider key: {str(e)}")
            return False

    def list_provider_keys(self) -> list[dict[str, Any]]:
        """List all provider keys"""
        if not self.token:
            print("❌ Not authenticated. Please login first.")
            return []

        url = f"{self.api_url}/provider-keys/"
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            response = requests.get(url, headers=headers)

            if response.status_code == HTTPStatus.OK:
                keys = response.json()
                print(f"✅ Found {len(keys)} provider keys:")
                for key in keys:
                    print(f"  - {key['id']}: {key['provider_name']}")
                    if key.get("base_url"):
                        print(f"    Base URL: {key['base_url']}")
                    if key.get("config"):
                        print(f"    Config: {key['config']}")
                return keys
            else:
                print(f"❌ Error listing provider keys: {response.status_code}")
                print(response.text)
                return []
        except Exception as e:
            print(f"❌ Error listing provider keys: {str(e)}")
            return []

    def delete_provider_key(self, provider_name: str) -> bool:
        """Delete a provider key"""
        if not self.token:
            print("❌ Not authenticated. Please login first.")
            return False

        url = f"{self.api_url}/provider-keys/{provider_name}"
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            response = requests.delete(url, headers=headers)

            if response.status_code == HTTPStatus.OK:
                print(f"✅ Successfully deleted {provider_name} API key!")
                return True
            else:
                print(f"❌ Error deleting provider key: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"❌ Error deleting provider key: {str(e)}")
            return False

    def test_chat_completion(
        self, model: str, message: str, api_key: str | None = None
    ) -> bool:
        """Test chat completion with a specific model"""
        if not api_key and not self.forge_api_key:
            print("❌ No API key provided. Please provide an API key.")
            return False

        url = f"{self.api_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": api_key or self.forge_api_key,
        }
        data = {
            "model": model,
            "messages": [{"role": "user", "content": message}],
        }

        try:
            response = requests.post(url, json=data, headers=headers)

            if response.status_code == HTTPStatus.OK:
                result = response.json()
                print("✅ Chat completion successful!")
                print(f"Response: {result['choices'][0]['message']['content']}")
                return True
            else:
                print(f"❌ Chat completion failed: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"❌ Error during chat completion: {str(e)}")
            return False

    def list_models(self, api_key: str | None = None) -> list[str] | None:
        """List available models"""
        if not api_key and not self.forge_api_key:
            print("❌ No API key provided. Please provide an API key.")
            return None

        url = f"{self.api_url}/models"
        headers = {
            "Content-Type": "application/json",
            "X-API-KEY": api_key or self.forge_api_key,
        }

        try:
            response = requests.get(url, headers=headers)

            if response.status_code == HTTPStatus.OK:
                result = response.json()
                models = result.get("data", [])
                print("✅ Available models:")
                for model in models:
                    print(f"  - {model}")
                return models
            else:
                print(f"❌ Failed to list models: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"❌ Error listing models: {str(e)}")
            return None

    def list_forge_api_keys(self) -> list[dict[str, Any]]:
        """List all Forge API keys for the current user"""
        if not self.token:
            print("❌ Not authenticated. Please login first.")
            return []

        url = f"{self.api_url}/api-keys/"  # Using the JWT authenticated route
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            response = requests.get(url, headers=headers)

            if response.status_code == HTTPStatus.OK:
                keys_data = response.json()
                print(f"✅ Found {len(keys_data)} Forge API key(s):")
                for i, key_info in enumerate(keys_data, 1):
                    print(f"  {i}. ID: {key_info.get('id')}")
                    print(f"     Key (Masked): {key_info.get('key')}")
                    print(f"     Name: {key_info.get('name', 'N/A')}")
                    print(f"     Active: {key_info.get('is_active')}")
                    print(f"     Created At: {key_info.get('created_at')}")
                    print(f"     Last Used At: {key_info.get('last_used_at', 'Never')}")
                    print(
                        f"     Allowed Provider Key IDs: {key_info.get('allowed_provider_key_ids', [])}"
                    )
                return keys_data
            else:
                print(f"❌ Error listing Forge API keys: {response.status_code}")
                print(response.text)
                return []
        except Exception as e:
            print(f"❌ Error listing Forge API keys: {str(e)}")
            return []

    def update_forge_api_key(
        self,
        key_id: int,
        name: str | None = None,
        is_active: bool | None = None,
        allowed_provider_key_ids: list[int] | None = None,
    ) -> dict | None:
        """Update an existing Forge API key"""
        if not self.token:
            print("❌ Not authenticated. Please login first.")
            return None

        url = f"{self.api_url}/api-keys/{key_id}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = (
                name if name else ""
            )  # Send empty string if user wants to clear name
        if is_active is not None:
            payload["is_active"] = is_active
        if allowed_provider_key_ids is not None:
            payload[
                "allowed_provider_key_ids"
            ] = allowed_provider_key_ids  # Empty list revokes all, list of IDs sets scope

        if not payload:  # Nothing to update
            print("ℹ️ No update parameters provided.")
            # Optionally, fetch and return the current key data or just return None
            # For now, let's try to fetch the current key data if no updates are made.
            current_keys = self.list_forge_api_keys()
            if current_keys:
                for key in current_keys:
                    if key.get("id") == key_id:
                        return key
            return None

        try:
            response = requests.put(url, headers=headers, json=payload)

            if response.status_code == HTTPStatus.OK:
                updated_key_data = response.json()
                print("✅ Forge API Key updated successfully!")
                print(f"   ID: {updated_key_data.get('id')}")
                # Key value itself doesn't change on update, so no need to print it fully
                print(f"   Name: {updated_key_data.get('name', 'N/A')}")
                print(f"   Active: {updated_key_data.get('is_active')}")
                print(f"   Created At: {updated_key_data.get('created_at')}")
                print(
                    f"   Last Used At: {updated_key_data.get('last_used_at', 'Never')}"
                )
                print(
                    f"   Allowed Provider Key IDs: {updated_key_data.get('allowed_provider_key_ids', [])}"
                )
                return updated_key_data
            elif response.status_code == HTTPStatus.NOT_FOUND:
                print(f"❌ Forge API Key with ID '{key_id}' not found.")
                return None
            else:
                print(f"❌ Failed to update Forge API key: {response.status_code}")
                print(response.text)
                return None
        except Exception as e:
            print(f"❌ Error updating Forge API key: {str(e)}")
            return None

    def delete_forge_api_key(self, key_id: int) -> bool:
        """Delete a specific Forge API key by its ID"""
        if not self.token:
            print("❌ Not authenticated. Please login first.")
            return False

        url = f"{self.api_url}/api-keys/{key_id}"
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            response = requests.delete(url, headers=headers)

            if response.status_code == HTTPStatus.OK:  # Assuming 200 OK for delete
                deleted_key_info = (
                    response.json()
                )  # The API returns the deleted key info
                print(
                    f"✅ Forge API Key with ID '{deleted_key_info.get('id')}' (key: {deleted_key_info.get('key')}) deleted successfully!"
                )
                # If the deleted key was stored in self.forge_api_key, clear it
                if self.forge_api_key == deleted_key_info.get("key"):
                    self.forge_api_key = None
                return True
            elif response.status_code == HTTPStatus.NOT_FOUND:
                print(f"❌ Forge API Key with ID '{key_id}' not found.")
                return False
            else:
                print(f"❌ Error deleting Forge API key: {response.status_code}")
                print(response.text)
                return False
        except Exception as e:
            print(f"❌ Error deleting Forge API key: {str(e)}")
            return False


def main():
    # Create Forge manager
    forge = ForgeManager()

    while True:
        print("\n=== Forge CLI Interactive Mode ===")
        print("1. Register")
        print("2. Login")
        print("3. Get User Info")
        print("4. Create Forge API Key")
        print("5. Delete Forge API Key")
        print("6. List Forge API Keys")
        print("7. Update Forge API Key")
        print("8. Add Provider Key")
        print("9. List Provider Keys")
        print("10. Delete Provider Key")
        print("11. Test Chat Completion")
        print("12. List Models")
        print("0. Exit")

        choice = input("\nEnter your choice (0-12): ")

        if choice == "0":
            break

        elif choice == "1":
            username = input("Enter username: ")
            email = input("Enter email: ")
            password = getpass("Enter password: ")
            forge.register(username, email, password)

        elif choice == "2":
            username = input("Enter username: ")
            password = getpass("Enter password: ")
            forge.login(username, password)

        elif choice == "3":
            if not forge.token:
                token = input("Enter JWT token: ")
                forge.token = token
            forge.get_user_info()

        elif choice == "4":
            if not forge.token:
                token = input("Enter JWT token: ")
                forge.token = token

            key_name = input(
                "Enter a name for the new Forge API key (optional, press Enter to skip): "
            ).strip()
            if not key_name:
                key_name = None

            allowed_ids_str = input(
                "Enter comma-separated Provider Key IDs to allow for this key (optional, press Enter to skip, type 'none' for no providers): "
            ).strip()
            allowed_provider_key_ids: list[int] | None = None
            if allowed_ids_str.lower() == "none":
                allowed_provider_key_ids = []  # Explicitly scope to no providers
            elif allowed_ids_str:
                try:
                    allowed_provider_key_ids = [
                        int(id_str.strip())
                        for id_str in allowed_ids_str.split(",")
                        if id_str.strip()
                    ]
                except ValueError:
                    print(
                        "❌ Invalid Provider Key IDs. Please enter comma-separated numbers."
                    )
                    continue
            # If allowed_ids_str is empty (user pressed Enter), allowed_provider_key_ids remains None (backend default)

            forge.create_forge_api_key(
                name=key_name, allowed_provider_key_ids=allowed_provider_key_ids
            )

        elif choice == "5":
            if not forge.token:
                token = input("Enter JWT token: ")
                forge.token = token
            try:
                key_id_to_delete = int(
                    input("Enter the ID of the Forge API Key to delete: ").strip()
                )
                forge.delete_forge_api_key(key_id_to_delete)
            except ValueError:
                print("❌ Invalid ID. Please enter a number.")

        elif choice == "6":
            if not forge.token:
                token = input("Enter JWT token: ")
                forge.token = token
            forge.list_forge_api_keys()

        elif choice == "7":
            if not forge.token:
                token = input("Enter JWT token: ")
                forge.token = token
            try:
                key_id_to_update = int(
                    input("Enter the ID of the Forge API Key to update: ").strip()
                )
            except ValueError:
                print("❌ Invalid ID. Please enter a number.")
                continue

            print("Enter new values or press Enter to keep current value.")

            new_name_str = input(
                "New name (or Enter to keep current, type 'clear' to remove name): "
            ).strip()
            new_name: str | None = None
            if new_name_str.lower() == "clear":
                new_name = ""  # Send empty string to clear
            elif new_name_str:
                new_name = new_name_str
            # If new_name_str is empty, new_name remains None (don't update)

            new_active_str = (
                input("New active status (true/false or Enter to keep current): ")
                .strip()
                .lower()
            )
            new_is_active: bool | None = None
            if new_active_str == "true":
                new_is_active = True
            elif new_active_str == "false":
                new_is_active = False
            elif new_active_str:
                print("❌ Invalid active status. Please enter 'true' or 'false'.")
                # continue # Or handle more gracefully
            # If new_active_str is empty, new_is_active remains None (don't update)

            new_ids_str = input(
                "New comma-separated Provider Key IDs (Enter to keep current, 'none' for no providers, 'clear' to remove scope restrictions if backend supports it, else same as 'none'): "
            ).strip()
            new_allowed_ids: list[int] | None = None
            if (
                new_ids_str.lower() == "none" or new_ids_str.lower() == "clear"
            ):  # Treat clear as setting to empty list
                new_allowed_ids = []
            elif new_ids_str:
                try:
                    new_allowed_ids = [
                        int(id_str.strip())
                        for id_str in new_ids_str.split(",")
                        if id_str.strip()
                    ]
                except ValueError:
                    print(
                        "❌ Invalid Provider Key IDs. Please enter comma-separated numbers."
                    )
                    continue
            # If new_ids_str is empty, new_allowed_ids remains None (don't update)

            forge.update_forge_api_key(
                key_id_to_update, new_name, new_is_active, new_allowed_ids
            )

        elif choice == "8":
            if not forge.token:
                token = input("Enter JWT token: ")
                forge.token = token
            provider = input("Enter provider name: ")
            key = getpass("Enter provider API key: ")
            base_url = input("Enter provider base URL (optional, press Enter to skip): ")
            config = input("Enter provider config in json string format (optional, press Enter to skip): ")
            forge.add_provider_key(provider, key, base_url=base_url, config=config)

        elif choice == "9":
            if not forge.token:
                token = input("Enter JWT token: ")
                forge.token = token
            forge.list_provider_keys()

        elif choice == "10":
            provider = input("Enter provider name to delete: ")
            forge.delete_provider_key(provider)

        elif choice == "11":
            model = input("Enter model ID: ")
            message = input("Enter message: ")
            api_key = input("Enter your Forge API key: ").strip()
            if not api_key:
                if forge.forge_api_key:
                    print(
                        f"ℹ️ Using stored Forge API key: {forge.forge_api_key[:10]}..."
                    )
                    api_key = forge.forge_api_key
                else:
                    print("❌ API key is required and none stored.")
                    continue
            forge.test_chat_completion(model, message, api_key)

        elif choice == "12":
            api_key = input(
                "Enter your Forge API key (or press Enter to use stored key if available): "
            ).strip()
            if not api_key:
                if forge.forge_api_key:
                    print(
                        f"ℹ️ Using stored Forge API key: {forge.forge_api_key[:10]}..."
                    )
                    api_key = forge.forge_api_key
                else:
                    print("❌ API key is required and none stored.")
                    continue
            forge.list_models(api_key)

        else:
            print("❌ Invalid choice. Please try again.")


if __name__ == "__main__":
    main()
