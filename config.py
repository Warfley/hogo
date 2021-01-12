import yaml
from pathlib import Path
from typing import Dict, Any, List
from copy import deepcopy
import re

CONF_PATH = Path("hogo.yml")

def validate_language(lang: str) -> bool:
    return re.match("[a-z][a-z]_[A-Z][A-Z]", lang) is not None

def validate_region(region: str) -> bool:
    return region in ("us", "eu", "kr", "tw", "cn")

class Config:
    def __init__(self):
        self.data: Dict[str, Any] = {}
    
    def __getitem__(self, key: str) -> Any:
        parts = key.split(".")
        data: Dict[str, Any] = self.data
        for part in parts[:-1]:
            if part not in data:
                return None
            data = data[part]
        return data.get(parts[-1], None)

    def __setitem__(self, key: str, value: Any) -> None:
        parts = key.split(".")
        data = self.data
        for part in parts[:-1]:
            if part not in data:
                data[part] = {}
            data = data[part]
        data[parts[-1]] = value
    
    def __contains__(self, key: str) -> bool:
        return self.__getitem__(key) is not None

    def load(self, filename: Path = CONF_PATH) -> None:
        if filename.exists():
            with open(filename, "r") as fl:
                self.data = yaml.load(fl, Loader=yaml.FullLoader)
        else:
            self.data = {}
    
    def store(self, filename: Path = CONF_PATH) -> None:
        with open(filename, "w") as fl:
            yaml.dump(self.data, fl)

    def validate(self) -> bool:
        return "server.region" in self \
           and "server.realm" in self \
           and "client.id" in self \
           and "client.pass" in self \
           and "data.language" in self
    
    def update_from_args(self, args) -> None:
        if args.region is not None:
            if validate_region(args.region):
                self["server.region"] = args.region
        if args.realm is not None:
            self["server.realm"] = args.realm
        if args.language is not None:
            if validate_language(args.language):
                self["data.language"] = args.language
        if args.client_id is not None:
            self["client.id"] = args.client_id
        if args.client_pass is not None:
            self["client.pass"] = args.client_pass
    
    def copy(self) -> "Config":
        result = Config()
        result.data = deepcopy(self.data)
    
    def get_or_default(self, key: str, default: Any) -> Any:
        result = self[key]
        if result is None:
            return default
        return result
