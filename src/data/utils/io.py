"""Input-Output utils
"""

import pickle
import json

import pandas as pd
from typing import Dict, Any

def save_pkl(d: Dict[str, Any], path: str) -> None:
    """Saves python object to pickle file

    Args:
        d (Dict[str, Any]): obj.
        path (str): path to .pkl file.

    Returns:
        None

    """
    with open(path, 'wb') as f:
        pickle.dump(d, f)

def load_pkl(path: str) -> Dict[str, Any]:
    """Loads pickle file.

    Args:
        path (str): path to pickle file.

    Returns:
        Dict[str, Any]: Python object.

    """
    with open(path, 'rb') as f:
        d = pickle.load(f)

    return d

def save_json(d: Dict[str, Any], path: str) -> None:
    """Saves python object to json file.

    Args:
        d (Dict[str, Any]): python object.
        path (str): Path to json file.

    Returns:
        None

    """
    with open(path, 'w') as f:
        json.dump(d, f, indent=4)

def load_json(path: str) -> Dict[str, Any]:
    """Loads json file.
    Args:
        path (str): path to json file.

    Returns:
        Dict[str, Any]: Python object.

    """
    with open(path, 'r') as f:
        d = json.load(f)

    return d
