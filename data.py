from config import Config
from argparse import ArgumentParser
from pathlib import Path
from wow_api import WoWAPI, ConnectedRealm, Realm, Profession, ProfessionTier, ItemStack, Recipe, Item
import yaml
from typing import List, Dict, Any

def serialize_realm(r: Realm) -> Dict[str, Any]:
    return {"id": r.id, "name": r.name}

def serialize_connected_realm(cr: ConnectedRealm) -> Dict[str, Any]:
    return {"id": cr.id, "realms": [serialize_realm(r) for r in cr.realms]}

def deserialize_realm(data: Dict[str, Any]) -> Realm:
    return Realm(data["id"], data["name"])

def deserialize_connected_realm(data: Dict[str, Any]) -> ConnectedRealm:
    return ConnectedRealm(data["id"], [deserialize_realm(r) for r in data["realms"]])

def serialize_profession_tier(pt: ProfessionTier) -> Dict[str, Any]:
    return {"id": pt.id, "name": pt.name}

def serialize_profession(p: Profession) -> Dict[str, Any]:
    return {"id": p.id, "name": p.name, "tiers": [serialize_profession_tier(pt) for pt in p.tiers.values()]}

def deserialize_profession_tier(data: Dict[str, Any]) -> ProfessionTier:
    # Recipes are stored seperately
    return ProfessionTier(data["id"], data["name"], {})

def deserialize_profession(data: Dict[str, Any]) -> Profession:
    return Profession(data["id"], data["name"], {td["id"]: deserialize_profession_tier(td) for td in data["tiers"]})

def serialize_item_stack(s: ItemStack) -> Dict[str, Any]:
    return {"count": s.count, "item_id": s.item_id}

def serialize_recipe(r: Recipe) -> Dict[str, Any]:
    return {"id": r.id, "category": r.category, "name": r.name, "crafted_item": serialize_item_stack(r.crafted_item), 
    "profession": {
        "id": r.profession_id,
        "tier": r.tier_id
    }, "reagents": [serialize_item_stack(ri) for ri in r.reagents]}

def deserialize_item_stack(data: Dict[str, Any]) -> ItemStack:
    return ItemStack(data["count"], data["item_id"])

def deserialize_recipe(data: Dict[str, Any]) -> Recipe:
    return Recipe(data["id"], data["category"], data["name"],
                 data["profession"]["id"], data["profession"]["tier"],
                  deserialize_item_stack(data["crafted_item"]),
                  [deserialize_item_stack(ri) for ri in data["reagents"]])

def serialize_item(i: Item) -> Dict[str, Any]:
    return {"id": i.id, "name": i.name, "vendor_price": i.vendor_price if i.vendor_price is not None else 0}

def deserialize_item(data: Dict[str, Any]) -> Item:
    return Item(data["id"], data["name"], None if data["vendor_price"] == 0 else data["vendor_price"])

class DataService:
    def __init__(self, config: Config, data_dir: Path = Path("data")):
        self.config = config
        self.data_dir = data_dir/f"{config['server.region']}.{config['data.language']}"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.api = WoWAPI(config)
        self.realms: Dict[int, ConnectedRealm] = self.__load_realms()
        self.professions: Dict[int, Profession] = self.__load_professions
        self.recipes = {}
        self.items = {}

    def __load_realms(self) -> Dict[int, ConnectedRealm]:
        realm_file = self.data_dir/"realms.yml"
        if not realm_file.exists():
            return {}
        with open(realm_file, "r") as fl:
            raw_data = yaml.load(fl, Loader=yaml.FullLoader)
            return {crd["id"]: deserialize_connected_realm(crd) for crd in raw_data}
    
    def __store_realms(self) -> None:
        realm_file = self.data_dir/"realms.yml"
        with open(realm_file, "w") as fl:
            raw_data = [serialize_connected_realm(r) for r in self.realms.values()]
            yaml.dump(raw_data, fl)
    
    def __load_professions(self) -> List[Profession]:
        profession_file = self.data_dir/"professions.yml"
        if not profession_file.exists():
            return {}
        with open(profession_file, "r") as fl:
            raw_data = yaml.load(fl, Loader=yaml.FullLoader)
            return {pd["id"]: deserialize_profession(pd) for pd in raw_data}
    
    def __store_professions(self) -> None:
        profession_file = self.data_dir/"professions.yml"
        with open(profession_file, "w") as fl:
            raw_data = [serialize_profession(p) for p in self.professions.values()]
            yaml.dump(raw_data, fl)

    def update_realms(self) -> None:
        self.api.generate_token()
        realms = self.api.load_realms()
        self.realms = {r.id: r for r in realms}
        self.__store_realms()
    
    def update_professions(self) -> None:
        self.api.generate_token()
        professions = self.api.load_professions()
        self.professions = {p.id: p for p in professions}
        self.__store_professions()
    
    def clear_realms(self) -> None:
        self.realms = {}
        realm_file = self.data_dir/"realms.yml"
        realm_file.unlink()

    def clear_professions(self) -> None:
        self.professions = {}
        profession_file = self.data_dir/"professions.yml"
        profession_file.unlink()
        

def __init_update_parser(parser: ArgumentParser) -> None:
    parsers = parser.add_subparsers(dest="target")
    parsers.add_parser("all", help="Update all data (default)")
    parsers.add_parser("realms", help="Update realm list")
    parsers.add_parser("professions", help="Update profession list")
    recipe_parser = parsers.add_parser("recipes", help="Update recipe list")
    recipe_parser.add_argument("--professions", type=str, choices=["all", "latest", "config"], default=False, help="Professions to load recipes from (default latest)")
    parsers.add_parser("items", help="Update item list for items used in loaded recipes")

def __init_list_parser(parser: ArgumentParser) -> None:
    parsers = parser.add_subparsers(dest="target")
    parsers.add_parser("realms", help="Lists realms")
    prof_parser = parsers.add_parser("professions", help="Lists professions")
    prof_parser.add_argument("--no-tiers", action="store_false", default=False, help="Don't show the different tiers of a profession")
    recipe_parser = parsers.add_parser("recipes", help="List all recipes")
    recipe_parser.add_argument("--profession", "-p", type=str, default="all", help="Only list recipes from that profession (profession id or all)")
    recipe_parser.add_argument("--profession-tier", "-t", type=str, default="all", help="Only list recipes from that profession tier (tier id or all, requires --profession)")
    parsers.add_parser("items", help="Lists all items")

def __init_search_parser(parser: ArgumentParser) -> None:
    parsers = parser.add_subparsers(dest="target")
    parsers.add_parser("realms", help="Lists realms matching the search").add_argument("searchterms", type=str, nargs="+")
    prof_parser = parsers.add_parser("professions", help="Lists professions matching the search")
    prof_parser.add_argument("--no-tiers", action="store_false", default=False, help="Don't show the different tiers of a profession")
    prof_parser.add_argument("searchterms", type=str, nargs="+")
    recipe_parser = parsers.add_parser("recipes", help="List recipes matching the search")
    recipe_parser.add_argument("--profession", "-p", type=str, default="all", help="Only list recipes from that profession (profession id or all)")
    recipe_parser.add_argument("--profession-tier", "-t", type=str, default="all", help="Only list recipes from that profession tier (tier id or all, requires --profession)")
    recipe_parser.add_argument("searchterms", type=str, nargs="+")
    parsers.add_parser("items", help="Lists items matching the search").add_argument("searchterms", type=str, nargs="+")

def __init_clear_parser(parser: ArgumentParser) -> None:
    parsers = parser.add_subparsers(dest="target")
    parsers.add_parser("all", help="Clear all data (default)")
    parsers.add_parser("realms", help="Clear realm list")
    parsers.add_parser("professions", help="Clear profession list")
    parsers.add_parser("recipes", help="Clear recipe list")
    parsers.add_parser("items", help="Clear item list")

def init_data_parser(parser: ArgumentParser) -> None:
    parser.add_argument("--format", "-f", default="human", choices=["human", "csv", "json"])

    parsers = parser.add_subparsers(dest="subcommand")

    update_parser = parsers.add_parser("update", help="Updates the locally stored database from the blizzard API")
    __init_update_parser(update_parser)

    list_parser = parsers.add_parser("list", help="Lists the information in the given format")
    __init_list_parser(list_parser)

    search_parser = parsers.add_parser("search", help="Lists the information in the given format containing a search string")
    __init_search_parser(search_parser)

    clear_parser = parsers.add_parser("clear", help="Clear saved data")
    __init_clear_parser(clear_parser)


def handle_data_command(args, config: Config) -> int:
    if args.subcommand == "update":
        return __handle_update(args, config)
    elif args.subcommand == "list":
        return __handle_list(args, config)
    elif args.subcommand == "search":
        return __handle_search(args, config)
    elif args.subcommand == "clear":
        return __handle_clear(args, config)
    return 1

def __handle_update(args, config: Config) -> int:
    data = DataService(config)
    if args.target == "realms":
        print("Updating realms...", end=" ", flush=True)
        data.update_realms()
        print("done")
    elif args.target == "professions":
        print("Updating professions...", end=" ", flush=True)
        data.update_professions()
        print("done")
    elif args.target == "recipes":
        pass
    elif args.target == "items":
        pass
    else: # all
        print("Updating realms...", end=" ", flush=True)
        data.update_realms()
        print("done")
        print("Updating professions...", end=" ", flush=True)
        data.update_professions()
        print("done")
    return 0

def __handle_list(args, config: Config) -> int:
    return 0

def __handle_search(args, config: Config) -> int:
    return 0

def __handle_clear(args, config: Config) -> int:
    return 0