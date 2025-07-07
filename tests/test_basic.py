import os
from http import HTTPStatus

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_TEST_URL", "http://localhost:8000")
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpassword123"
TEST_EMAIL = "test@example.com"

# OpenAI test credentials - Fill these in with your actual API key for testing
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def test_register_user():
    """Test user registration"""
    print("Testing user registration...")
    url = f"{API_BASE_URL}/auth/register"
    data = {"username": TEST_USERNAME, "email": TEST_EMAIL, "password": TEST_PASSWORD}
    response = requests.post(url, json=data)

    if response.status_code == HTTPStatus.OK:
        print("✅ User registration successful!")
        user_data = response.json()
        print(f"Forge API Key: {user_data['forge_api_key']}")
        return user_data
    elif (
        response.status_code == HTTPStatus.BAD_REQUEST
        and "already exists" in response.json().get("detail", "")
    ):
        print("⚠️ User already exists, will attempt login instead")
        return None
    else:
        print(f"❌ User registration failed: {response.text}")
        return None


def test_login():
    """Test login and get JWT token"""
    print("\nTesting login...")
    url = f"{API_BASE_URL}/auth/token"
    data = {"username": TEST_USERNAME, "password": TEST_PASSWORD}
    response = requests.post(url, data=data)

    if response.status_code == HTTPStatus.OK:
        token_data = response.json()
        print("✅ Login successful!")
        return token_data["access_token"]
    else:
        print(f"❌ Login failed: {response.text}")
        return None


def test_add_provider_key(token):
    """Test adding an OpenAI provider key"""
    print("\nTesting adding provider key...")
    url = f"{API_BASE_URL}/provider-keys/"
    headers = {"Authorization": f"Bearer {token}"}
    data = {
        "provider_name": "openai",
        "api_key": OPENAI_API_KEY,
        "model_mapping": {"test-model": "gpt-3.5-turbo"},
    }
    response = requests.post(url, json=data, headers=headers)

    if response.status_code == HTTPStatus.OK:
        print("✅ Provider key added successfully!")
        return True
    elif (
        response.status_code == HTTPStatus.BAD_REQUEST
        and "already exists" in response.json().get("detail", "")
    ):
        print("⚠️ Provider key already exists")
        return True
    else:
        print(f"❌ Adding provider key failed: {response.text}")
        return False


def test_list_provider_keys(token):
    """Test listing provider keys"""
    print("\nTesting listing provider keys...")
    url = f"{API_BASE_URL}/provider-keys/"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)

    if response.status_code == HTTPStatus.OK:
        keys = response.json()
        print(f"✅ Found {len(keys)} provider keys:")
        for key in keys:
            print(f"  - {key['provider_name']}")
        return True
    else:
        print(f"❌ Listing provider keys failed: {response.text}")
        return False


def get_forge_api_key(token):
    """Get the user's forge API key"""
    url = f"{API_BASE_URL}/users/me"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)

    if response.status_code == HTTPStatus.OK:
        user_data = response.json()
        return user_data["forge_api_key"]
    else:
        print(f"❌ Failed to get user info: {response.text}")
        return None


def test_chat_completion(forge_api_key):
    """Test chat completion using the Forge API key"""
    print("\nTesting chat completion with Forge...")
    url = f"{API_BASE_URL}/chat/completions"
    headers = {"X-API-KEY": forge_api_key}
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Hello, how are you today?"}],
    }

    print("Sending request to Forge API...")
    response = requests.post(url, json=data, headers=headers)

    if response.status_code == HTTPStatus.OK:
        result = response.json()
        print("✅ Chat completion successful!")
        print(f"Response: {result['choices'][0]['message']['content']}")
        return True
    else:
        print(f"❌ Chat completion failed: {response.text}")
        return False


def test_mapped_model(forge_api_key):
    """Test chat completion using a mapped model name"""
    print("\nTesting chat completion with mapped model...")
    url = f"{API_BASE_URL}/chat/completions"
    headers = {"X-API-KEY": forge_api_key}
    data = {
        "model": "test-model",  # This should map to gpt-3.5-turbo
        "messages": [{"role": "user", "content": "What's the capital of France?"}],
    }

    print("Sending request with mapped model name...")
    response = requests.post(url, json=data, headers=headers)

    if response.status_code == HTTPStatus.OK:
        result = response.json()
        print("✅ Mapped model test successful!")
        print(f"Response: {result['choices'][0]['message']['content']}")
        return True
    else:
        print(f"❌ Mapped model test failed: {response.text}")
        return False


def run_tests():
    """Run all tests"""
    if not OPENAI_API_KEY:
        print(
            "⚠️ Warning: OPENAI_API_KEY is not set. Set it in .env for a complete test."
        )
        return

    # Register user
    user_data = test_register_user()

    # Login
    token = test_login()
    if not token:
        print("❌ Tests failed: Unable to log in")
        return

    # Add provider key
    if not test_add_provider_key(token):
        print("❌ Tests failed: Unable to add provider key")
        return

    # List provider keys
    test_list_provider_keys(token)

    # Get Forge API key
    forge_api_key = get_forge_api_key(token)
    if not forge_api_key:
        if user_data:
            forge_api_key = user_data["forge_api_key"]
        else:
            print("❌ Tests failed: Unable to get Forge API key")
            return

    print(f"\n🔑 Using Forge API Key: {forge_api_key}")

    # Test chat completion
    if not test_chat_completion(forge_api_key):
        print("❌ Tests failed: Chat completion failed")
        return

    # Test mapped model
    test_mapped_model(forge_api_key)

    print("\n✅ All tests completed!")


if __name__ == "__main__":
    run_tests()
