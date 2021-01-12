import yaml
from pathlib import Path
from argparse import ArgumentParser
from typing import Dict, Any, List
from copy import deepcopy
import re

CONF_PATH = Path("hogo.yml")

def __validate_language(lang: str) -> bool:
    return re.match("[a-z][a-z]_[A-Z][A-Z]", lang) is not None

def __validate_region(region: str) -> bool:
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
            if __validate_region(args.region):
                self["server.region"] = args.region
        if args.realm is not None:
            self["server.realm"] = args.realm
        if args.language is not None:
            if __validate_language(args.language):
                self["data.language"] = args.language
        if args.client_id is not None:
            self["client.id"] = args.client_id
        if args.client_pass is not None:
            self["client.pass"] = args.client_pass
    
    def copy(self) -> "Config":
        result = Config()
        result.data = deepcopy(self.data)

def add_default_config_args(parser: ArgumentParser) -> None:
    parser.add_argument("--language", "-l", type=str, help="Language of the item names")
    parser.add_argument("--region", "-r", type=str, help="Region of the realm")
    parser.add_argument("--realm", "-s", type=str, help="Realm to load data from")
    parser.add_argument("--client-id", "-c", type=str, help="API Client ID")
    parser.add_argument("--client-pass", "-p", type=str, help="API Client Secret")

def init_config_parser(parser: ArgumentParser) -> None:
    parsers = parser.add_subparsers(dest="subcommand")
    init_parser = parsers.add_parser("init", help="Initializes the config with initial values")
    add_default_config_args(init_parser)
    update_parser = parsers.add_parser("update", help="Updates the config with cli arguments")
    add_default_config_args(update_parser)
    get_parser = parsers.add_parser("get", help="Print the value of a property")
    get_parser.add_argument("prop", type=str, help="Property to read")
    set_parser = parsers.add_parser("set", help="Set the value of a property")
    set_parser.add_argument("prop", type=str, help="Property to write")
    set_parser.add_argument("value", type=str, help="Value to set the property to")
    add_parser = parsers.add_parser("add", help="Adds a value to a list property")
    add_parser.add_argument("prop", type=str, help="The list property to add to")
    add_parser.add_argument("values", type=str, nargs="+", help="The value to be added to the list")
    add_parser = parsers.add_parser("remove", help="Removes a value to from a list property")
    add_parser.add_argument("prop", type=str, help="The list property to remove from")
    add_parser.add_argument("values", type=str, nargs="+", help="The value to be removed from the list")

def handle_config_command(args, config: Config) -> int:
    new_config: Config = None
    if args.subcommand == "init":
        new_config = __init_config(args)
    elif args.subcommand == "update":
        new_config = config
    elif args.subcommand == "get":
        val = config[args.prop]
        if val is None:
            print(f"No value stored for {args.prop}")
            return 1
        else:
            print(val)
    elif args.subcommand == "set":
        new_config = Config()
        new_config.load()
        val = int(args.value) if args.value.isdigit() else args.value
        new_config[args.prop] = val
    elif args.subcommand == "add":
        new_config = Config()
        new_config.load()
        prev = new_config[args.prop]
        prev = set() if prev is None else set(prev)
        for value in args.values:
            val = int(value) if value.isdigit() else value
            prev.add(val)
        new_config[args.prop] = list(prev)
    elif args.subcommand == "remove":
        new_config = Config()
        new_config.load()
        prev = new_config[args.prop]
        prev = set() if prev is None else set(prev)
        for value in args.values:
            val = int(value) if value.isdigit() else value
            prev.remove(val)
        new_config[args.prop] = list(prev)
    else:
        return 1
    if new_config is not None:
        new_config.store()
    return 1

def __init_config(args) -> Config:
    result = Config()
    result.update_from_args(args)
    if "server.region" not in result:
        while True:
            region = input("Server region (default: us): ")
            region = "us" if region == "" else region
            if __validate_region(region):
                result["server.region"] = region
                break
            else:
                print("Invalid region, try again")
    if "data.language" not in result:
        while True:
            language = input("Data language (default: en_US): ")
            language = "en_US" if language == "" else language
            if __validate_language(language):
                result["data.language"] = language
                break
            else:
                print("Invalid language locale, try again")
    if "server.realm" not in result:
        result["server.realm"] = input("Select realm: ")
    if "client.id" not in result:
        result["client.id"] = input("API client ID: ")
    if "client.pass" not in result:
        result["client.pass"] = input("API client secret: ")
    return result
