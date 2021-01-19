from config import Config
from argparse import ArgumentParser
from pathlib import Path
from wow_api import WoWAPI, ConnectedRealm, Realm, Profession, ProfessionTier, ItemStack, Recipe, Item
import yaml
from typing import List, Dict, Any, Tuple, Set

def serialize_realm(r: Realm) -> Dict[str, Any]:
    return {"id": r.id, "name": r.name, "slug": r.slug}

def serialize_connected_realm(cr: ConnectedRealm) -> Dict[str, Any]:
    return {"id": cr.id, "realms": [serialize_realm(r) for r in cr.realms]}

def deserialize_realm(data: Dict[str, Any]) -> Realm:
    return Realm(data["id"], data["name"], data["slug"])

def deserialize_connected_realm(data: Dict[str, Any]) -> ConnectedRealm:
    return ConnectedRealm(data["id"], [deserialize_realm(r) for r in data["realms"]])

def serialize_profession_tier(pt: ProfessionTier) -> Dict[str, Any]:
    return {"id": pt.id, "name": pt.name}

def serialize_profession(p: Profession) -> Dict[str, Any]:
    return {"id": p.id, "name": p.name, "tiers": [serialize_profession_tier(pt) for pt in p.tiers]}

def deserialize_profession_tier(data: Dict[str, Any]) -> ProfessionTier:
    # Recipes are stored seperately
    return ProfessionTier(data["id"], data["name"])

def deserialize_profession(data: Dict[str, Any]) -> Profession:
    return Profession(data["id"], data["name"], [deserialize_profession_tier(td) for td in data["tiers"]])

def serialize_item_stack(s: ItemStack) -> Dict[str, Any]:
    if s is None:
        return {"count": 0, "item_id": 0}
    return {"count": s.count, "item_id": s.item_id}

def serialize_recipe(r: Recipe) -> Dict[str, Any]:
    result = {
        "id": r.id,
        "category": r.category,
        "name": r.name,
        "crafted_item": serialize_item_stack(r.crafted_item), 
        "profession": {
            "id": r.profession_id,
            "tier": r.tier_id
        },
        "reagents": [serialize_item_stack(ri) for ri in r.reagents]
    }
    if r.legendary_level is not None:
        result["legendary_level"] = r.legendary_level
    return result

def deserialize_item_stack(data: Dict[str, Any]) -> ItemStack:
    if data["count"] == 0:
        return None
    return ItemStack(data["count"], data["item_id"])

def deserialize_recipe(data: Dict[str, Any]) -> Recipe:
    return Recipe(data["id"], data["category"], data["name"],
                 data["profession"]["id"], data["profession"]["tier"],
                  deserialize_item_stack(data["crafted_item"]),
                  [deserialize_item_stack(ri) for ri in data["reagents"]],
                  data.get("legendary_level", None))

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
        self.__realms: List[ConnectedRealm] = []
        self.__professions: List[Profession] = []
        self.__recipes: List[Recipe] = []
        self.__items: List[Item] = []

    def get_realms(self) -> List[ConnectedRealm]:
        if self.__realms == []:
            self.__realms = self.__load_realms()
        return self.__realms

    def get_professions(self) -> List[Profession]:
        if self.__professions == []:
            self.__professions = self.__load_professions()
        return self.__professions

    def get_recipes(self) -> List[Recipe]:
        if self.__recipes == []:
            self.__recipes = self.__load_recipes()
        return self.__recipes

    def get_items(self) -> List[Item]:
        if self.__items == []:
            self.__items = self.__load_items()
        return self.__items

    def __load_realms(self) -> List[ConnectedRealm]:
        realm_file = self.data_dir/"realms.yml"
        if not realm_file.exists():
            return []
        with open(realm_file, "r") as fl:
            raw_data = yaml.load(fl, Loader=yaml.FullLoader)
            return [deserialize_connected_realm(crd) for crd in raw_data]
    
    def __store_realms(self) -> None:
        realm_file = self.data_dir/"realms.yml"
        with open(realm_file, "w") as fl:
            raw_data = [serialize_connected_realm(r) for r in self.__realms]
            yaml.dump(raw_data, fl)
    
    def __load_professions(self) -> List[Profession]:
        profession_file = self.data_dir/"professions.yml"
        if not profession_file.exists():
            return []
        with open(profession_file, "r") as fl:
            raw_data = yaml.load(fl, Loader=yaml.FullLoader)
            return [deserialize_profession(pd) for pd in raw_data]
    
    def __store_professions(self) -> None:
        profession_file = self.data_dir/"professions.yml"
        with open(profession_file, "w") as fl:
            raw_data = [serialize_profession(p) for p in self.__professions]
            yaml.dump(raw_data, fl)
    
    def __load_recipes(self) -> List[Recipe]:
        recipe_file = self.data_dir/"recipes.yml"
        if not recipe_file.exists():
            return []
        with open(recipe_file, "r") as fl:
            raw_data = yaml.load(fl, Loader=yaml.FullLoader)
            return [deserialize_recipe(rd) for rd in raw_data]
    
    def __store_recipes(self) -> None:
        recipe_file = self.data_dir/"recipes.yml"
        with open(recipe_file, "w") as fl:
            raw_data = [serialize_recipe(r) for r in self.__recipes]
            yaml.dump(raw_data, fl)

    def __load_items(self) -> List[Item]:
        item_file = self.data_dir/"items.yml"
        if not item_file.exists():
            return []
        with open(item_file, "r") as fl:
            raw_data = yaml.load(fl, Loader=yaml.FullLoader)
            return [deserialize_item(i) for i in raw_data]
    
    def __store_items(self) -> None:
        item_file = self.data_dir/"items.yml"
        with open(item_file, "w") as fl:
            raw_data = [serialize_item(i) for i in self.__items]
            yaml.dump(raw_data, fl)

    def update_realms(self) -> None:
        self.api.generate_token()
        self.__realms = self.api.load_realms()
        self.__store_realms()
    
    def update_professions(self) -> None:
        self.api.generate_token()
        self.__professions = self.api.load_professions()
        self.__store_professions()
    
    def update_recipes(self, profession_tiers: List[Tuple[int, int]]) -> None:
        self.api.generate_token()
        self.__recipes = []
        for prof, tier in profession_tiers:
            recipes = self.api.load_recipes(prof, tier)
            self.__recipes.extend(recipes)
        self.__store_recipes()
    
    def __update_item(self, item_id: int, cache: Set[int]) -> None:
        if item_id in cache:
            return
        self.__items.append(self.api.load_item(item_id))
        cache.add(item_id)

    def update_items(self) -> None:
        self.api.generate_token()
        self.__items = []
        cache = set()
        for recipe in self.get_recipes():
            if recipe.crafted_item is not None:
                self.__update_item(recipe.crafted_item.item_id, cache)
            for reagent in recipe.reagents:
                self.__update_item(reagent.item_id, cache)
        self.__store_items()

    def clear_realms(self) -> None:
        self.__realms = []
        realm_file = self.data_dir/"realms.yml"
        realm_file.unlink()

    def clear_professions(self) -> None:
        self.__professions = []
        profession_file = self.data_dir/"professions.yml"
        profession_file.unlink()
    
    def clear_recipes(self) -> None:
        self.__recipes = []
        recipe_file = self.data_dir/"recipes.yml"
        recipe_file.unlink()
    
    def clear_items(self) -> None:
        self.__items = []
        item_file = self.data_dir/"items.yml"
        item_file.unlink()
    
    def latest_professions(self) -> List[Tuple[int, int]]:
        result = []
        for prof in self.get_professions():
            if len(prof.tiers) > 0:
                tier: ProfessionTier = sorted(prof.tiers, key=lambda t: t.id)[-1]
                result.append((prof.id, tier.id))
        return result
    
    def all_professions(self) -> List[Tuple[int, int]]:
        result = []
        for prof in self.get_professions():
            result.extend([(prof.id, tier.id) for tier in prof.tiers])
        return result
    
    def config_professions(self) -> List[Tuple[int, int]]:
        result = []
        for prof_tier in self.config.get_or_default("data.professions", []):
            pt = prof_tier.split("-")
            prof = int(pt[0])
            tier = int(pt[1])
            result.append((prof, tier))
        return result
    
    def find_profession_tier(self, name: str) -> Tuple[int, int]:
        for prof in self.get_professions():
            for tier in prof.tiers:
                if tier.name == name:
                    return prof.id, tier.id
        return None, None
    
    def find_item(self, name:str) -> int:
        for item in self.get_items():
            if item.name == name:
                return item.id
        return None

    def find_realm(self, slug: str) -> Tuple[int, int]:
        for cr in self.get_realms():
            for r in cr.realms:
                if r.slug == slug:
                    return cr.id, r.id
        return None, None
    
    def profession_recipes(self, professions: Set[Tuple[int, int]]) -> List[Recipe]:
        recipes = self.get_recipes()
        return [r for r in recipes if (r.profession_id, r.tier_id) in professions]
    
def init_update_parser(parser: ArgumentParser) -> None:
    parsers = parser.add_subparsers(dest="target")
    all_parser = parsers.add_parser("all", help="Update all data (default)")
    all_parser.add_argument("--professions", type=str, choices=["all", "latest", "config"], default="latest", help="Professions to load recipes from (default latest)")
    parsers.add_parser("realms", help="Update realm list")
    parsers.add_parser("professions", help="Update profession list")
    recipe_parser = parsers.add_parser("recipes", help="Update recipe list")
    recipe_parser.add_argument("--professions", type=str, choices=["all", "latest", "config"], default="latest", help="Professions to load recipes from (default latest)")
    parsers.add_parser("items", help="Update item list for items used in loaded recipes")

def handle_update_command (args, config: Config) -> int:
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
        print("Updating recipes...", end=" ", flush=True)
        prof_tiers = data.all_professions() if args.professions == "all" \
                else data.config_professions if args.professions == "config" \
                else data.latest_professions()
        data.update_recipes(prof_tiers)
        print("done")        
    elif args.target == "items":
        print("Updating items...", end=" ", flush=True)
        data.update_items()
        print("Done")
    else: # all
        print("Updating realms...", end=" ", flush=True)
        data.update_realms()
        print("done")
        print("Updating professions...", end=" ", flush=True)
        data.update_professions()
        print("done")
        print("Updating recipes...", end=" ", flush=True)
        prof_tiers = data.latest_professions()
        data.update_recipes(prof_tiers)
        print("done")        
        print("Updating items...", end=" ", flush=True)
        data.update_items()
        print("Done")
    return 0
