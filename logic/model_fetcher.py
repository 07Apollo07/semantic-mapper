import requests

def fetch_models(base_url, api_key):
    """
    Fetches the list of available models from the given Base URL.
    Expects an OpenAI-compatible /v1/models endpoint.
    """
    if not base_url:
        return []
    
    # Ensure URL ends with /v1/models or just use as is if user provided full path
    url = f"{base_url.rstrip('/')}/v1/models"
    
    headers = {
        "Authorization": f"Bearer {api_key}" if api_key else "",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # OpenAI style: { "data": [ {"id": "model-id", ...}, ... ] }
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            return [model["id"] for model in data["data"] if "id" in model]
        # Fallback for some local providers returning a list directly
        elif isinstance(data, list):
            return [model.get("id", model) if isinstance(model, dict) else model for model in data]
        return []
            
    except Exception as e:
        print(f"Error fetching models from {url}: {e}")
        return []
