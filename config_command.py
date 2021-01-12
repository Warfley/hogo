from config import Config, validate_language, validate_region
from data import DataService
from argparse import ArgumentParser
from typing import List

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

    profession_parser = parsers.add_parser("professions", help="Configure the data.professions property, requires updated profession data")
    profession_parser.add_argument("action", type=str, choices=["add", "delete"])
    profession_parser.add_argument("professions", nargs="+", type=str, help="List of professions in the currently selected language to add/delete. " +\
                                   "Profession tiers are required, e.g. \"Shadowlands Blacksmithing\"")

    vendor_parser = parsers.add_parser("vendoritems", help="Configure the data.vendor_items property, requires updated item data")
    vendor_parser.add_argument("action", type=str, choices=["add", "delete"])
    vendor_parser.add_argument("items", nargs="+", type=str, help="List of the items in the currently selected language to add/delete.")

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
        prev = set(new_config.get_or_default(args.prop, []))
        for value in args.values:
            val = int(value) if value.isdigit() else value
            prev.add(val)
        new_config[args.prop] = list(prev)
    elif args.subcommand == "remove":
        new_config = Config()
        new_config.load()
        prev = set(new_config.get_or_default(args.prop, []))
        for value in args.values:
            val = int(value) if value.isdigit() else value
            prev.remove(val)
        new_config[args.prop] = list(prev)
    elif args.subcommand == "professions":
        if args.action == "add":
            new_config = __add_professions(args.professions, config)
        else:
            new_config = __delete_professions(args.professions, config)
    elif args.subcommand == "vendoritems":
        if args.action == "add":
            new_config = __add_vendor_items(args.items, config)
        else:
            new_config = __delete_vendor_items(args.items, config)
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
            if validate_region(region):
                result["server.region"] = region
                break
            else:
                print("Invalid region, try again")
    if "data.language" not in result:
        while True:
            language = input("Data language (default: en_US): ")
            language = "en_US" if language == "" else language
            if validate_language(language):
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

def __add_professions(professions: List[str], config: Config) -> Config:
    data = DataService(config)
    result = Config()
    result.load()
    prev = set(result.get_or_default("data.professions", []))
    for prof in professions:
        pid, tid = data.find_profession_tier(prof)
        if pid is None:
            print(f"Can't find profession {prof}... skipping")
            continue
        prev.add(f"{pid}-{tid}")
    result["data.professions"] = list(prev)
    return result

def __delete_professions(professions: List[str], config: Config) -> Config:
    data = DataService(config)
    result = Config()
    result.load()
    prev = set(result.get_or_default("data.professions", []))
    for prof in professions:
        pid, tid = data.find_profession_tier(prof)
        if pid is None:
            print(f"Can't find profession {prof}... skipping")
            continue
        prev.remove(f"{pid}-{tid}")
    result["data.professions"] = list(prev)
    return result

def __add_vendor_items(items: List[str], config: Config) -> Config:
    data = DataService(config)
    result = Config()
    result.load()
    prev = set(result.get_or_default("data.vendor_items", []))
    for item in items:
        iid = data.find_item(item)
        if iid is None:
            print(f"Can't find item {item}... skipping")
            continue
        prev.add(iid)
    result["data.vendor_items"] = list(prev)
    return result

def __delete_vendor_items(items: List[str], config: Config) -> Config:
    data = DataService(config)
    result = Config()
    result.load()
    prev = set(result.get_or_default("data.vendor_items", []))
    for item in items:
        iid = data.find_item(item)
        if iid is None:
            print(f"Can't find item {item}... skipping")
            continue
        prev.remove(iid)
    result["data.vendor_items"] = list(prev)
    return result