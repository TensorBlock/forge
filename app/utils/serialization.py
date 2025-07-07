import json
from typing import Any, Dict

def serialize_dict(data: Dict[str, Any]) -> str:
    """
    Serialize a dictionary to a string using JSON.
    
    Args:
        data: The dictionary to serialize
        
    Returns:
        A JSON string representation of the dictionary
        
    Raises:
        TypeError: If the input is not a dictionary
        ValueError: If the dictionary contains non-serializable values
    """
    if not isinstance(data, dict):
        raise TypeError("Input must be a dictionary")
    
    return json.dumps(data)

def deserialize_dict(serialized_data: str) -> Dict[str, Any]:
    """
    Deserialize a string back into a dictionary using JSON.
    
    Args:
        serialized_data: The JSON string to deserialize
        
    Returns:
        The deserialized dictionary
        
    Raises:
        ValueError: If the input string is not valid JSON
    """
    return json.loads(serialized_data) 