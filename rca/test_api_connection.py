import sys
import os

# Ensure the parent directory is in sys.path to import rca modules
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from rca.api_router import get_chat_completion

def test_api():
    print("Testing API Connection based on rca/api_config.yaml...")
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello! Please reply with a short message confirming that the API connection is successful."}
    ]
    
    try:
        response = get_chat_completion(messages=messages, temperature=0.7)
        print("\n✅ API Connection Successful!")
        print("-" * 40)
        print("Response from model:")
        print(response)
        print("-" * 40)
    except Exception as e:
        print("\n❌ API Connection Failed!")
        print("Error details:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api()
