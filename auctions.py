from config import Config
from wow_api import WoWAPI, AuctionHouseItem, ItemModifier, PetInfo, Auction, Item, Recipe, ItemStack
from data_types import ConnectedRealm, \
                       Realm, \
                       Profession, \
                       ProfessionTier, \
                       Item, \
                       ItemModifier, \
                       PetInfo, \
                       Auction, \
                       AuctionHouseItem, \
                       AuctionHousePetItem, \
                       CombinedAuction, \
                       Recipe, \
                       LegendaryRecipe, \
                       NormalRecipe, \
                       DisenchantRecipe, \
                       ItemStack
from argparse import ArgumentParser
from data import DataService
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple
import yaml

from logging import info, warning

class AuctionHouse:
    def __init__(self, config: Config, data_dir: Path = Path("auctions")):
        self.config = config
        self.data_file = data_dir/f"{config['server.region']}.{config['server.realm']}.yml"
        self.__auctions: Dict[int, List[CombinedAuction]] = {}
        data_dir.mkdir(parents=True, exist_ok=True)
        self.api = WoWAPI(config)
    
    def get_auctions(self) -> Dict[int, List[CombinedAuction]]:
        if self.__auctions == {}:
            self.__auctions = self.__load_data()
        return self.__auctions
    
    def __load_data(self) -> Dict[int, List[CombinedAuction]]:
        if not self.data_file.exists():
            return {}
        with open(self.data_file, "r") as fl:
            raw_data = yaml.load(fl, Loader=yaml.FullLoader)
            result = {}
            for ad in raw_data:
                auction = CombinedAuction(data=ad)
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
        cache: Dict[str, CombinedAuction] = {}
        auctions = self.api.load_auctions(connected_realm_id)
        self.__auctions = {}
        for a in auctions:
            if len(filter_items) > 0 and a.item.id not in filter_items:
                continue
            aid = CombinedAuction.generate_id(a.price, a.item)
            if aid in cache:
                cache[aid].quantity += a.quantity
            else:
                ai = CombinedAuction(auction=a)
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

    # shadowlands specific code
    def compute_legendary_prices(self, legendary_items: Set[int]) -> Dict[int, Dict[int, int]]:
        # Hardcoded because not all might be in the AH at any time, so we can't just deduce from sorting
        KEY_LEVELS = {
            1487: 1,
            1507: 2,
            1522: 3,
            1532: 4
        }
        result: Dict[int, Dict[int, int]] = {}
        auctions = self.get_auctions()
        legendary_auctions = {item: auctions[item] for item in legendary_items}
        for item, auctions in legendary_auctions.items():
            item_result = {}
            for a in auctions:
                lvl = KEY_LEVELS.get(a.item.bonus_lists[-1])
                if lvl is None:
                    warning(f"Unknown key level: {a.item.bonus_lists[-1]} for item {item}... Ignoring")
                    continue
                item_result[lvl] = min(item_result.get(lvl, 9999999999999), a.price)
            result[item] = item_result
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
        info("Updating auction list...")
        ah.update(__get_connected_realm_id(config), __get_item_filter(config, data))
        info("Auctionlist successfully updated")
        return 0
    if args.update:
        info("Updating auction list...")
        ah.update(__get_connected_realm_id(config), __get_item_filter(config, data))
        info("Auctionlist successfully updated")
    
    if args.subcommand == "search":
        item_cache: Dict[int, Item] = {}
        matches = ah.find_auctions(args.keywords, data, item_cache)
        for match in sorted(matches, key=lambda m: m.price):
            print_auction(match, item_cache)
    if args.subcommand == "profit":
        handle_profit(args, config, data, ah)
    return 0

def price_to_string(price: int) -> str:
    gold = price // 10000
    silver = price // 100 % 100
    bronze = price % 100
    result = ""
    if gold:
        result = f"{gold}g, "
    if silver:
        result = f"{result}{silver}s, "
    if bronze:
        result = f"{result}{bronze}b, "
    return result[:-2]

def print_auction(auction: CombinedAuction, cache: Dict[int, Item]) -> None:
    item_name = cache[auction.item.id].name
    print(f"{item_name} ({auction.quantity}): {price_to_string(auction.price)}")

def __build_item_cache(data: DataService) -> Dict[int, Item]:
    return {i.id: i for i in data.get_items()}

def __build_recipe_cache(recipes: List[Recipe]) -> Tuple[Dict[int,  Recipe], Set[int], Dict[int, Dict[int, Recipe]]]:
    crafted_items: Dict[int, Recipe] = {}
    all_items: Set[int] = set()
    legendary_items: Dict[int, Dict[int, Recipe]] = {}
    for recipe in recipes:
        if isinstance(recipe, DisenchantRecipe):
            continue
        if isinstance(recipe, LegendaryRecipe):
            legendary_item = legendary_items.get(recipe.item_id, {})
            legendary_item[recipe.rank] = recipe
            legendary_items[recipe.item_id] = legendary_item
        crafted_item = recipe.item_id if isinstance(recipe, LegendaryRecipe) \
                       else recipe.crafted_item.item_id
        crafted_items[crafted_item] = recipe
        all_items.add(crafted_item)
        for reagent in recipe.reagents:
            all_items.add(reagent.item_id)
    return crafted_items, all_items, legendary_items

def __get_item_ids(items: List[str], data: DataService) -> List[int]:
    if items is None:
        return []
    return [data.find_item(itm) for itm in items]

def __get_professions(prof_list: List[str], config: Config, data: DataService) -> Set[Tuple[int, int]]:
    result = set()
    for prof in prof_list:
        if prof == "config":
            for prof_tier in config.get_or_default("data.professions", []):
                pt = prof_tier.split("-")
                prof = int(pt[0])
                tier = int(pt[1])
                result.add((prof, tier))
        else:
            result.add(data.find_profession_tier(prof))
    return result

def __items_from_list_and_conf(item_list: List[str], config_path: str, config: Config, data: DataService) -> Set[int]:
    result = set() if item_list is None \
        else set(__get_item_ids(item_list, data))
    result.update(config.get_or_default(config_path, []))
    return result

def __check_recipe_requirements(recipe: Recipe, computed: Set[int], crafted_items: Dict[int, Recipe]) -> List[int]:
    result: List[int] = []
    for reagent in recipe.reagents:
        # if we can craft this and haven't computed it's price, this is a requirement
        if reagent.item_id in crafted_items and reagent.item_id not in computed:
            result.append(reagent.item_id)
    return result

def __compute_recipe_costs(recipe: Recipe, min_prices: Dict[int, Tuple[int, int]], item_cache: Dict[str, Item]) -> int:
    # if there are no uncomputed requirements, compute the price
    result = 0
    for reagent in recipe.reagents:
        # if we can't buy it, skrew it
        if reagent.item_id not in min_prices:
            warning("Reagent: " + item_cache[reagent.item_id].name + " is not obtainable... Skipping computation for: " + item_cache[recipe.crafted_item.item_id].name)
            return None
        # if we can buy/craft it, add it's cost to the total
        result += min_prices[reagent.item_id][0] * reagent.count
    quantity = 1 if isinstance(recipe, LegendaryRecipe) else recipe.crafted_item.count
    # compute price per item not per stack
    return round(result / quantity)


def __compute_production_costs(crafted_items: Dict[int, Recipe], item_cache: Dict[int, Item],
                               legendary_items: Dict[int, Dict[int, Recipe]], # shadowlands specific
                               buy_items: Set[int], ignore_items: Set[int], specific_items: Set[int],
                               min_prices: Dict[int, Tuple[int, int]]) -> Tuple[Dict[int, int], Dict[int, Dict[int, int]]]:
    to_compute = list(crafted_items.keys())
    computed = set()
    result: Dict[int, int] = {}
    legendary_result: Dict[int, Dict[int, int]] = {}
    while len(to_compute) > 0:
        iid = to_compute.pop()
        # Skip items we already computed (as requirement of an earlier item)
        # or that is ignored, or not specified
        if iid in computed or iid in ignore_items or (len(specific_items) > 0 and iid not in specific_items):
            continue
        recipe = crafted_items[iid]
        # check requirements
        requirements = __check_recipe_requirements(recipe, computed, crafted_items)
        # first resolve requirements
        if len(requirements) > 0:
            # we poped ourselfs earlier, so we need to push again
            to_compute.append(iid)
            # also add all the requirements to be poped first
            to_compute.extend(requirements)
            continue
        # Shadowlands specific code:
        regular_costs: int = None
        # ASSUMPTION: All reagents are the same only in different quantities
        # FIXME if this turns out to be wrong
        if iid in legendary_items:
            legendary_costs: Dict[int, int] = {}
            for lvl, legendary_recipe in legendary_items[iid].items():
                total_costs = __compute_recipe_costs(legendary_recipe, min_prices, item_cache)
                if total_costs is not None:
                    legendary_costs[lvl] = total_costs
            legendary_result[iid] = legendary_costs
        else:
            regular_costs = __compute_recipe_costs(recipe, min_prices, item_cache)
        # no matter if this a success (i.e. all reagents are obtainable), we finished this one
        computed.add(iid)
        if regular_costs is None: # either a legendary or at least one reagent is unobtainable
            continue
        # set the result
        result[iid] = regular_costs
        # if this is cheaper than buying, make this the default method of obtaining this
        if iid not in buy_items:
            if iid not in min_prices or min_prices[iid][0] > regular_costs:
                min_prices[iid] = (regular_costs, 2)
    return result, legendary_result

def __print_item(recipe: Recipe, production_cost: int, ah_price: int, min_prices: Dict[int, Tuple[int, int]], item_names: Dict[int, str]) -> None:
    item_id = recipe.item_id if isinstance(recipe, LegendaryRecipe) else recipe.crafted_item.item_id
    item_name = item_names[item_id]
    profit = round(ah_price * 0.95) - production_cost
    print(f"{item_name}: Price={price_to_string(ah_price)} Costs={price_to_string(production_cost)} Profit={price_to_string(profit)}")
    for reagent in recipe.reagents:
        rprice, method = min_prices[reagent.item_id]
        method_msg = "AH" if method == 0 \
                else "vendor" if method == 1 \
                else "crafting"
        print(f"    {item_names[reagent.item_id]}: {reagent.count} * {price_to_string(rprice)} ({price_to_string(rprice*reagent.count)}) from {method_msg}")


def handle_profit(args, config: Config, data: DataService, ah: AuctionHouse) -> int:
    info("Loading recipes...")
    professions: Set[Tuple[int, int]] = __get_professions(args.professions, config, data)
    recipes: List[Recipe] = data.profession_recipes(professions)
    info("Indexing items...")
    item_cache: Dict[int, Item] = __build_item_cache(data)
    crafted_items, all_items, legendary_items = __build_recipe_cache(recipes)
    vendor_items = __items_from_list_and_conf(args.vendor_items, "data.vendor_items", config, data)
    ignore_items = __items_from_list_and_conf(args.ignore, "auctions.ignore", config, data)
    buy_items = __items_from_list_and_conf(args.buy, "auctions.buy", config, data)
    specific_items = __items_from_list_and_conf(args.specific, "auctions.specific", config, data)
    info("Computing item prices...")
    ah_prices: Dict[int, int] = ah.compute_prices(all_items)
    legendary_prices: Dict[int, Dict[int, int]] = ah.compute_legendary_prices(set(legendary_items.keys()))
    # The second int indicates how the item is obtained, AH(0), Vendor(1), crafted(2)
    min_prices: Dict[int, Tuple[int, int]] = {}
    for iid, ah_price in ah_prices.items():
        item = item_cache[iid]
        # if we can buy from a vendor, do that if it is cheaper
        min_prices[iid] = (item.vendor_price, 1) if iid in vendor_items and \
                                                    item.vendor_price < ah_price \
                                                 else (ah_price, 0)
    info("Computing production costs...")
    production_costs, legendary_production_costs = __compute_production_costs(crafted_items, item_cache,
                                                                              legendary_items,
                                                                              buy_items, ignore_items,
                                                                              specific_items, min_prices)
    info("Price computation complete")
    # Printing
    LEGENDARY_ILVL = {
        1: 190,
        2: 210,
        3: 225,
        4: 235
    }
    item_names = {iid: item_cache[iid].name for iid in all_items}
    for item, costs in production_costs.items():
        if item not in ah_prices:
            continue
        recipe = crafted_items[item]
        __print_item(recipe, costs, ah_prices[item], min_prices, item_names)
    if legendary_production_costs: print("Legendaries:")
    for item, legendary_costs in legendary_production_costs.items():
        for lvl, costs in legendary_costs.items():
            if lvl not in legendary_prices[item]:
                continue
            item_names[item] = f"{item_cache[item].name} ({LEGENDARY_ILVL[lvl]})"
            recipe = legendary_items[item][lvl]
            __print_item(recipe, costs, legendary_prices[item][lvl], min_prices, item_names)
