import json
from pathlib import Path
from typing import Union


def authenticate(filename: Union[Path, str], identifier: str) -> dict:
    """
    Get the authentication token from JSON file
    :param filename: path to JSON file
    :param identifier: the identifier to get
    :return: str
    """
    with open(filename) as file:
        data = json.load(file)
        file.close()

    return data.get(identifier)
