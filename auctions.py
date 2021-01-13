from config import Config
from wow_api import WoWAPI, AuctionHouseItem, ItemModifier, PetInfo, Auction, Item, Recipe
from argparse import ArgumentParser
from data import DataService
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
import yaml

def serialize_modifier(modifier: ItemModifier) -> Dict[str, Any]:
    return {"type": modifier.key, "value": modifier.value}

def serialize_pet_info(pet_info: PetInfo) -> Dict[str, Any]:
    return {"breed": pet_info.breed_id, "level": pet_info.level, "quality": pet_info.quality_id, "species": pet_info.species_id}

def serialize_item(item: AuctionHouseItem) -> Dict[str, Any]:
    data = {"id": item.id,
            "modifiers": [serialize_modifier(m) for m in item.modifiers],
            "bonus_lists": [bl for bl in item.bonus_lists]
           }
    if item.pet_info is not None:
        data["pet_info"] = serialize_pet_info(item.pet_info)
    return data

def deserialize_modifier(data: Dict[str, Any]) -> ItemModifier:
    return ItemModifier(data["type"], data["value"])

def deserialize_pet_info(data: Dict[str, Any]) -> PetInfo:
    return PetInfo(data["breed"], data["level"], data["quality"], data["species"])

def deserialize_item(data: Dict[str, Any]) -> AuctionHouseItem:
    modifiers = [deserialize_modifier(md) for md in data["modifiers"]]
    pet_info = deserialize_pet_info(data["pet_info"]) if "pet_info" in data \
          else None
    return AuctionHouseItem(data["id"], data["bonus_lists"], modifiers, pet_info)

class AuctionInfo:
    @staticmethod
    def generate_id(price: int, item: AuctionHouseItem) -> str:
        return f"Price={price}; item={str(item)})"

    def __init__(self, auction: Auction=None, data: Dict[str, Any]=None):
        assert (auction is not None) != (data is not None)
        if auction is not None:
            self.price = auction.price
            self.item = auction.item
            self.quantity = auction.quantity
        else:
            self.price = data["price"]
            self.quantity = data["quantity"]
            self.item = deserialize_item(data["item"])
        self.id = self.generate_id(self.price, self.item)
    
    def serialize(self) -> Dict[str, Any]:
        return {"price": self.price, "quantity": self.quantity, "item": serialize_item(self.item)}
    


class AuctionHouse:
    def __init__(self, config: Config, data_dir: Path = Path("auctions")):
        self.config = config
        self.data_file = data_dir/f"{config['server.region']}.{config['server.realm']}.yml"
        self.__auctions: Dict[int, List[AuctionInfo]] = {}
        data_dir.mkdir(parents=True, exist_ok=True)
        self.api = WoWAPI(config)
    
    def get_auctions(self) -> Dict[int, List[AuctionInfo]]:
        if self.__auctions == {}:
            self.__auctions = self.__load_data()
        return self.__auctions
    
    def __load_data(self) -> Dict[int, List[AuctionInfo]]:
        if not self.data_file.exists():
            return {}
        with open(self.data_file, "r") as fl:
            raw_data = yaml.load(fl, Loader=yaml.FullLoader)
            result = {}
            for ad in raw_data:
                auction = AuctionInfo(data=ad)
                al = result.get(auction.item.id, [])
                al.append(auction)
                result[auction.item.id] = al
            return result
    
    def __store_data(self) -> None:
        with open(self.data_file, "w") as fl:
            raw_data = []
            for al in self.__auctions.values():
                raw_data.extend([a.serialize() for a in al])
            yaml.dump(raw_data, fl)
    
    def update(self, connected_realm_id: int, filter_items: Set[int]=set()) -> None:
        self.api.generate_token()
        cache: Dict[str, AuctionInfo] = {}
        auctions = self.api.load_auctions(connected_realm_id)
        self.__auctions = {}
        for a in auctions:
            if len(filter_items) > 0 and a.item.id not in filter_items:
                continue
            aid = AuctionInfo.generate_id(a.price, a.item)
            if aid in cache:
                cache[aid].quantity += a.quantity
            else:
                ai = AuctionInfo(auction=a)
                cache[aid] = ai
                al = self.__auctions.get(a.item.id, [])
                al.append(ai)
                self.__auctions[a.item.id] = al
        self.__store_data()
    
    def clear_data(self) -> None:
        self.__auctions = {}
        self.data_file.unlink()
    
    def find_auctions(self, keywords: List[str], datasvc: DataService, cache: Dict[int, Item]={}) -> List[Auction]:
        items = datasvc.get_items()
        matches = [i for i in items if all([kw.lower() in i.name.lower() for kw in keywords])]
        result = []
        auctions = self.get_auctions()
        for m in matches:
            result.extend(auctions.get(m.id, []))
            cache[m.id] = m
        return result
    
    def compute_prices(self, items: Set[int]) -> Dict[int, int]:
        result = {}
        auctions = self.get_auctions()
        for item in items:
            if item in auctions:
                result[item] = sorted(auctions[item], key=lambda a: a.price)[0].price
        return result

    
def init_auction_parser(parser: ArgumentParser) -> None:
    parser.add_argument("--update", "-u", action="store_true", default=False, help="Update before taking the action")

    parsers = parser.add_subparsers(dest="subcommand")
    parsers.add_parser("update", help="Update local AH data")
    search_parser = parsers.add_parser("search", help="Search auctions")
    search_parser.add_argument("keywords", type=str, nargs="+")
    profit_parser = parsers.add_parser("profit", help="Compute profit")
    profit_parser.add_argument("--professions", "-p", nargs="+", type=str, default=["config"],
                               help="Using crafting from these professions, profession names " +\
                                    "in configured language or 'config' to read from config (default=config)")
    profit_parser.add_argument("--vendor-items", "-v", nargs="+", type=int, help="The IDs of items that can be bought " +\
                               "from the vendor. Additional to data.vendor_items config")
    profit_parser.add_argument("--buy", "-b", type=str, nargs="+", help="Items to be always bought, even if the can be crafted cheaper. Additional to auctions.buy config")
    profit_parser.add_argument("--ignore", "-i", type=str, nargs="+", help="Items to ignore for crafting. Additional to auctions.ignore config")
    profit_parser.add_argument("--specific", "-s", type=str, help="Specific items to check production costs for. Additional to auctions.specific config. If not set, all non ignored items will be checked")

def __get_connected_realm_id(config) -> int:
    data = DataService(config)
    connected_realm_id, _ = data.find_realm(config["server.realm"])
    return connected_realm_id

def __get_item_filter(config: Config, data: DataService) -> Set[int]:
    return set([i.id for i in data.get_items()])

def handle_auction_command(args, config: Config) -> int:
    ah = AuctionHouse(config)
    data = DataService(config)
    if args.subcommand == "update":
        print("Updating auction list...", end=" ", flush=True)
        ah.update(__get_connected_realm_id(config), __get_item_filter(config, data))
        print("done")
        return 0
    if args.update:
        print("Updating auction list...", end=" ", flush=True)
        ah.update(__get_connected_realm_id(config), __get_item_filter(config, data))
        print("done")
    
    if args.subcommand == "search":
        item_cache: Dict[int, Item] = {}
        matches = ah.find_auctions(args.keywords, data, item_cache)
        for match in sorted(matches, key=lambda m: m.price):
            print_auction(match, item_cache)
    if args.subcommand == "profit":
        handle_profit(args, config, data, ah)
    return 0

def price_to_string(price: int) -> str:
    return f"{price // 10000}g {price // 100 % 100}s {price % 100}b"

def print_auction(auction: AuctionInfo, cache: Dict[int, Item]) -> None:
    item_name = cache[auction.item.id].name
    print(f"{item_name} ({auction.quantity}): {price_to_string(auction.price)}")

def __build_item_cache(data: DataService) -> Dict[int, Item]:
    return {i.id: i for i in data.get_items()}

def __build_recipe_cache(recipes: List[Recipe]) -> Tuple[Dict[int,  Recipe], Set[int]]:
    crafted_items: Dict[int, Recipe] = {}
    all_items: Set[int] = set()
    for recipe in recipes:
        if recipe.crafted_item is None:
            continue
        crafted_items[recipe.crafted_item.item_id] = recipe
        all_items.add(recipe.crafted_item.item_id)
        for reagent in recipe.reagents:
            all_items.add(reagent.item_id)
    return crafted_items, all_items

def __get_item_ids(items: List[str], data: DataService) -> List[int]:
    if items is None:
        return []
    return [data.find_item(itm) for itm in items]

def __get_professions(prof_list: List[str], config: Config, data: DataService) -> Set[Tuple[int, int]]:
    result = set() if prof_list is None \
        else set([data.find_profession_tier(prof) for prof in prof_list])
    for prof_tier in config.get_or_default("data.professions", []):
        pt = prof_tier.split("-")
        prof = int(pt[0])
        tier = int(pt[1])
        result.add((prof, tier))
    return result

def __items_from_list_and_conf(item_list: List[str], config_path: str, config: Config, data: DataService) -> Set[int]:
    result = set() if item_list is None \
        else set(__get_item_ids(item_list, data))
    result.update(config.get_or_default(config_path, []))
    return result

def __compute_production_costs(crafted_items: Dict[int, Recipe], item_cache: Dict[int, Item],
                               buy_items: Set[int], ignore_items: Set[int], specific_items: Set[int],
                               min_prices: Dict[int, Tuple[int, int]]) -> Dict[int, int]:
    to_compute = list(crafted_items.keys())
    computed = set()
    result: Dict[int, int] = {}
    while len(to_compute) > 0:
        iid = to_compute.pop()
        # Skip items we already computed (as requirement of an earlier item)
        # or that is ignored, or not specified
        if iid in computed or iid in ignore_items or (len(specific_items) > 0 and iid not in specific_items):
            continue
        recipe = crafted_items[iid]
        # check requirements
        requirements: List[int] = []
        for reagent in recipe.reagents:
            # if we can craft this and haven't computed it's price, this is a requirement
            if reagent.item_id in crafted_items and reagent.item_id not in computed:
                requirements.append(reagent.item_id)
        # first resolve requirements
        if len(requirements) > 0:
            # we poped ourselfs earlier, so we need to push again
            to_compute.append(iid)
            # also add all the requirements to be poped first
            to_compute.extend(requirements)
            continue
        # if there are no uncomputed requirements, compute the price
        total_costs = 0
        for reagent in recipe.reagents:
            # if we can't buy it, skrew it
            if reagent.item_id not in min_prices:
                print("Reagent: " + item_cache[reagent.item_id].name + " is not obtainable... Skipping computation for: " + item_cache[iid].name)
                total_costs = -1
                break
            # if we can buy/craft it, add it's cost to the total
            total_costs += min_prices[reagent.item_id][0] * reagent.count
        # no matter if this a success (i.e. all reagents are obtainable), we finished this one
        computed.add(iid)
        if total_costs < 0: # at least one reagent is unobtainable
            continue
        # the result
        result[iid] = total_costs
        # if this is cheaper than buying, make this the default method of obtaining this
        if iid not in buy_items:
            if iid not in min_prices or min_prices[iid][0] > total_costs:
                min_prices[iid] = (total_costs, 2)
    return result

def handle_profit(args, config: Config, data: DataService, ah: AuctionHouse) -> int:
    print("Loading recipes...", end=" ", flush=True)
    professions: Set[Tuple[int, int]] = __get_professions(args.professions, config, data)
    recipes: List[Recipe] = data.profession_recipes(professions)
    print("done")
    print("Indexing items...", end=" ", flush=True)
    item_cache: Dict[int, Item] = __build_item_cache(data)
    crafted_items, all_items = __build_recipe_cache(recipes)
    vendor_items = __items_from_list_and_conf(args.vendor_items, "data.vendor_items", config, data)
    ignore_items = __items_from_list_and_conf(args.ignore, "auctions.ignore", config, data)
    buy_items = __items_from_list_and_conf(args.buy, "auctions.buy", config, data)
    specific_items = __items_from_list_and_conf(args.specific, "auctions.specific", config, data)
    print("done")
    print("Computing item prices...", end=" ", flush=True)
    ah_prices: Dict[int, int] = ah.compute_prices(all_items)
    # The second int indicates how the item is obtained, AH(0), Vendor(1), crafted(2)
    min_prices: Dict[int, Tuple[int, int]] = {}
    for iid, ah_price in ah_prices.items():
        item = item_cache[iid]
        # if we can buy from a vendor, do that if it is cheaper
        min_prices[iid] = (item.vendor_price, 1) if iid in vendor_items and \
                                                    item.vendor_price < ah_price \
                                                 else (ah_price, 0)
    print("done")
    print("Computing production costs...", end=" ", flush=True)
    production_costs: Dict[int, int] = __compute_production_costs(crafted_items, item_cache,
                                                                  buy_items, ignore_items,
                                                                  specific_items, min_prices)
    print("done")
    for item, costs in production_costs.items():
        price = ah_prices.get(item, 0)
        profit = round(price * 0.95) - costs
        print(f"{item_cache[item].name}: Price={price_to_string(price)} Costs={price_to_string(costs)} Profit={price_to_string(profit)}")
        recipe = crafted_items[item]
        for reagent in recipe.reagents:
            rprice, method = min_prices[reagent.item_id]
            method_msg = "AH" if method == 0 \
                    else "Vendor" if method == 1 \
                    else "Crafted"
            print(f"    {item_cache[reagent.item_id].name}: {reagent.count} * {rprice} ({rprice*reagent.count}) from {method_msg}")



