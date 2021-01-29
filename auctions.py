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
                       ItemQuality, \
                       ItemStack
from argparse import ArgumentParser
from data import DataService
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple, Union, Iterable
from dataclasses import dataclass
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
    
    def compute_prices(self, items: Set[int]) -> Dict[int, CombinedAuction]:
        result = {}
        auctions = self.get_auctions()
        for item in items:
            if item in auctions:
                result[item] = sorted(auctions[item], key=lambda a: a.price)[0]
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
                    warning(f"Unknown key level {a.item.bonus_lists[-1]} for item {item}... Ignoring")
                    continue
                item_result[lvl] = min(item_result.get(lvl, 9999999999999), a.price)
            result[item] = item_result
        return result

# either vendor price, auction or a recipe
ReagentPrice = Union[int, CombinedAuction, Recipe]
class RecipeCostComputer:
    def __init__(self, config: Config, data: DataService):
        self.config: Config = config
        self.data: DataService = data

        self.__item_cache: Dict[str, Item] = None
        # maps expansion against item quality against items
        self.__disenchantable_items: Dict[int, Dict[ItemQuality, List[Item]]] = None

        self.__buy_items: Set[int] = set()

        self.__considerable_items: Set[int] = set()
        self.__craftable_items: Dict[int, List[Recipe]] = {}
        self.__legendary_items: Set[int] = set()
        self.__disenchanting_items: Dict[int, DisenchantRecipe] = {}
        self.__professions: List[Tuple[Profession, ProfessionTier]] = []
        self.__recipes: List[Recipe] = []
        self.__recipe_cache: Dict[int, Recipe] = {}

        self.__ah_prices: Dict[int, CombinedAuction] = {}
        # maps legendary item to rank and cost
        self.__legendary_prices: Dict[int, Dict[int, int]] = {}
        self.__recipe_selling_price: Dict[int, int] = {}

        # computation
        self.__min_prices: Dict[int, ReagentPrice] = {}
        self.__recipe_production_costs: Dict[int, int] = {}
        self.__disenchantable_min_items: Dict[int, int] = {}

    def _clear_items(self) -> None:
        self.__considerable_items = set()
        self.__craftable_items = {}
        self.__legendary_items = set()
        self.__disenchantable_items = {}
        self.__disenchanting_items = {}
        self.__disenchantable_items = None
        self.__disenchantable_min_items = {}

    def _clear_computations(self) -> None:
        self.__min_prices = {}
        self.__recipe_production_costs = {}

    @property
    def item_cache(self) -> Dict[str, Item]:
        if self.__item_cache is None:
            info("Indexing items...")
            self.__item_cache = {item.id: item for item in self.data.get_items()}
            info("Item indexing complete")
        return self.__item_cache
    @property
    def buy_items(self) -> Set[int]:
        return self.__buy_items
    @buy_items.setter
    def buy_items(self, items: Set[int]) -> None:
        self._clear_computations()
        self.__buy_items = items

    @property
    def disenchantable_items(self) -> Dict[int, Dict[ItemQuality, List[Item]]]:
        if self.__disenchantable_items is None:
            self._build_disenchantbale_item_cache()
        return self.__disenchantable_items

    @property
    def professions(self) -> List[Tuple[Profession, ProfessionTier]]:
        return self.__professions
    @professions.setter
    def professions(self, professions: Iterable[Tuple[Profession, ProfessionTier]]) -> None:
        self._clear_items()
        self._clear_computations()
        self.__professions = list(professions)
        info("Loading profession recipes...")
        self.__recipes = self.data.profession_recipes({(prof.id, tier.id) for prof, tier in self.__professions})
        info("Building recipe cache...")
        self.__recipe_cache = {recipe.id: recipe for recipe in self.__recipes}
        self._build_recipe_item_cache()
        info("Recipes loaded")

    @property
    def recipes(self) -> List[Recipe]:
        return self.__recipes
    @property
    def recipe_cache(self) -> Dict[int, Recipe]:
        return self.__recipe_cache
    @property
    def considerable_items(self) -> Set[int]:
        return self.__considerable_items
    @property
    def legendary_items(self) -> Set[int]:
        return self.__legendary_items
    @property
    def ah_prices(self) -> Dict[int, CombinedAuction]:
        return self.__ah_prices
    @property
    def legendary_prices(self) -> Dict[int, Dict[int, int]]:
        return self.__legendary_prices
    @property
    def craftable_items(self) -> Dict[int, List[Recipe]]:
        return self.__craftable_items
    @property
    def min_prices(self) -> Dict[int, ReagentPrice]:
        return self.__min_prices
    @property
    def recipe_production_costs(self) -> Dict[int, int]:
        return self.__recipe_production_costs
    @property
    def recipe_selling_price(self) -> Dict[int, int]:
        return self.__recipe_selling_price
    @property
    def disenchantable_min_items(self) -> Dict[int, int]:
        return self.__disenchantable_min_items

    def _build_recipe_item_cache(self) -> None:
        craftable: Dict[int, List[Recipe]] = {}
        considerable: Set[int] = set()
        legendary: Set[int] = set()
        for recipe in self.recipes:
            if isinstance(recipe, LegendaryRecipe):
                legendary.add(recipe.item_id)
            crafted_item = recipe.item_id if isinstance(recipe, LegendaryRecipe) \
                        else recipe.crafted_item.item_id if isinstance(recipe, NormalRecipe) \
                        else None
            if crafted_item is not None:
                item_recipes = craftable.get(crafted_item, [])
                item_recipes.append(recipe)
                craftable[crafted_item] = item_recipes
                considerable.add(crafted_item)
                for reagent in recipe.reagents:
                    considerable.add(reagent.item_id)
            else: # DisenchantableRecipe
                for item in recipe.crafted_items:
                    considerable.add(item.item_id)
                    item_recipes = craftable.get(item.item_id, [])
                    item_recipes.append(recipe)
                    craftable[crafted_item] = item_recipes
        # add all items that can be disenchanted
        for disenchantable_dict in self.disenchantable_items.values():
            for disenchantable_items in disenchantable_dict.values():
                considerable.update([item.id for item in disenchantable_items])
        self.__craftable_items = craftable
        self.__considerable_items = considerable
        self.__legendary_items = legendary
    
    def _build_disenchantbale_item_cache(self) -> None:
        enchanting_id = self.config["data.profession_ids.enchanting"]
        disenchantable_classes = {
            self.config["data.item_classes.armor.id"],
            self.config["data.item_classes.weapon.id"]
        }
        disenchantable_qualities = {
            ItemQuality.UNCOMMON,
            ItemQuality.RARE,
            ItemQuality.EPIC
        }
        expansions = {tier.expansion for prof, tier in self.professions if prof.id == enchanting_id}
        disenchantables: Dict[int, Dict[ItemQuality, List[Item]]] = {}
        for item in self.data.get_items():
            if item.expansion in expansions \
                   and item.item_class in disenchantable_classes \
                   and item.quality in disenchantable_qualities:
                exp_disenchantables = disenchantables.get(item.expansion, {})
                item_list = exp_disenchantables.get(item.quality, [])
                item_list.append(item)
                exp_disenchantables[item.quality] = item_list
                disenchantables[item.expansion] = exp_disenchantables
        self.__disenchantable_items = disenchantables
    
    def _get_vendor_prices(self, vendor_items: Set[int]) -> Dict[int, int]:
        return {
            item_id: self.item_cache[item_id].vendor_price for item_id in vendor_items
        }
    
    def _compute_recipe_ah_price(self) -> None:
        info("Computing selling prices for recipes")
        recipe_prices: Dict[int, int] = {}
        for recipe in self.recipes:
            recipe_price = 0
            if isinstance(recipe, LegendaryRecipe):
                recipe_price = self.__legendary_prices.get(recipe.item_id, {}).get(recipe.rank, 0)
            elif isinstance(recipe, NormalRecipe):
                price = self._get_min_price(recipe.crafted_item.item_id)
                if price is not None:
                    recipe_price = price * recipe.crafted_item.count
            else:
                for stack in recipe.crafted_items:
                    price = self._get_min_price(stack.item_id)
                    if price is not None:
                        recipe_price += price * stack.count
            if recipe_price:
                recipe_prices[recipe.id] = recipe_price
        self.__recipe_selling_price = recipe_prices

    def compute_baseline_prices(self, ah: AuctionHouse, vendor_items: Set[int]) -> None:
        info("Indexing auctions...")
        self._clear_computations()
        self.__ah_prices = ah.compute_prices(self.considerable_items)
        self.__legendary_prices = ah.compute_legendary_prices(self.legendary_items)
        info("Computing baseline prices...")
        vendor_prices = self._get_vendor_prices(vendor_items)
        min_prices = {}
        for item_id in self.considerable_items:
            vendor_price = vendor_prices.get(item_id)
            ah_auction = self.__ah_prices.get(item_id)
            if vendor_price is None and ah_auction is None:
                continue # not obtainable via buying
            min_prices[item_id] = ah_auction if vendor_price is None \
                             else vendor_price if ah_auction is None \
                             else ah_auction if ah_auction.price <= vendor_price \
                             else vendor_price
        self.__min_prices = min_prices
        self._compute_recipe_ah_price()
        info("Baseline prices successfully computed")
    
    def _get_requirements(self, recipe_id: int, reagents: List[int], trace: Set[int], computed: Set[int]) -> List[Tuple[Recipe, Set[int]]]:
        new_trace = trace.copy()
        new_trace.add(recipe_id)
        requirements: List[Recipe] = []
        for reagent in reagents:
            if reagent in self.__buy_items:
                continue
            reagent_recipes = self.craftable_items.get(reagent, [])
            requirements.extend([(reagent_recipe, new_trace) for reagent_recipe in reagent_recipes \
                                 if reagent_recipe.id not in computed \
                                 and reagent_recipe.id not in trace])
        return requirements
    
    def _get_min_price(self, item_id: int) -> int:
        price = self.__min_prices.get(item_id)
        return price if isinstance(price, int) \
          else price.price if isinstance(price, CombinedAuction) \
          else self.__recipe_production_costs[price.id] if isinstance(price, Recipe) \
          else None
    
    def _compute_reagent_costs(self, reagents: List[ItemStack]) -> int:
        result: int = 0
        for reagent in reagents:
            reagent_price = self._get_min_price(reagent.item_id)
            if reagent_price is None:
                warning("Reagent " + self.item_cache[reagent.item_id].name + " is not obtainable, skipping...")
                return None
            result += reagent_price * reagent.count
        return result

    def _compute_normal_production_cost(self, recipe: NormalRecipe, trace: Set[int], computed: Set[int]) -> Union[int, List[Tuple[Recipe, Set[int]]]]:
        requirements = self._get_requirements(recipe.id, [reagent.item_id for reagent in recipe.reagents], trace, computed)
        if requirements:
            return [(recipe, trace)] + requirements
        return self._compute_reagent_costs(recipe.reagents)

    def _compute_legendary_production_cost(self, recipe: LegendaryRecipe, trace: Set[int], computed: Set[int]) -> Union[int, List[Tuple[Recipe, Set[int]]]]:
        requirements = self._get_requirements(recipe.id, [reagent.item_id for reagent in recipe.reagents], trace, computed)
        if requirements:
            return [(recipe, trace)] + requirements
        return self._compute_reagent_costs(recipe.reagents)

    def _compute_disenchant_production_cost(self, recipe: DisenchantRecipe, trace: Set[int], computed: Set[int]) -> Union[int, List[Tuple[Recipe, Set[int]]]]:
        if recipe.reagent_quality not in self.disenchantable_items[recipe.expansion]:
            return None
        disenchantable = self.disenchantable_items[recipe.expansion][recipe.reagent_quality]
        requirements = self._get_requirements(recipe.id, [item.id for item in disenchantable], trace, computed)
        if requirements:
            return [(recipe, trace)] + requirements
        min_price, min_item = None, None
        for item in disenchantable:
            item_price = self._compute_reagent_costs([ItemStack(1, item.id)])
            if item_price is not None and (min_price is None or item_price < min_price):
                min_price = item_price
                min_item = item
        self.__disenchantable_min_items[recipe.id] = min_item.id
        return min_price

    def _update_min_price(self, item: ItemStack, recipe: Recipe) -> None:
        if item.item_id in self.__buy_items:
            return
        price = self.__recipe_production_costs[recipe.id] / item.count
        if item.item_id not in self.__min_prices or price < self._get_min_price(item.item_id):
            self.__min_prices[item.item_id] = recipe
    
    def compute_production_costs(self) -> None:
        self.__recipe_production_costs = {}
        info("Computing production costs...")
        # the set contains all the requirements that lead up to this one to break cyclic requirements
        to_compute: List[Tuple[Recipe, Set[int]]] = [(recipe, set()) for recipe in self.recipes]
        computed: Set[int] = set()
        while to_compute:
            recipe, trace = to_compute.pop()
            if recipe.id in computed:
                continue
            computation_result = self._compute_normal_production_cost(recipe, trace, computed) if isinstance(recipe, NormalRecipe) \
                            else self._compute_legendary_production_cost(recipe, trace, computed) if isinstance(recipe, LegendaryRecipe) \
                            else self._compute_disenchant_production_cost(recipe, trace, computed) if isinstance(recipe, DisenchantRecipe) \
                            else None
            if computation_result is None:
                warning("Can't compute production costs for recipe " + recipe.name + " skipping...")
                # Skip this if it comes up again
                computed.add(recipe.id)
                continue
            if isinstance(computation_result, list):
                to_compute.extend(computation_result)
                continue
            computed.add(recipe.id)
            self.__recipe_production_costs[recipe.id] = computation_result
            if isinstance(recipe, NormalRecipe):
                self._update_min_price(recipe.crafted_item, recipe)
            elif isinstance(recipe, LegendaryRecipe):
                self._update_min_price(ItemStack(1, recipe.item_id), recipe)
            else:
                for item_stack in recipe.crafted_items:
                    self._update_min_price(item_stack, recipe)
        info("Computation complete")
            

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
    profit_parser.add_argument("--vendor-items", "-v", nargs="+", type=str, help="Items that can be bought " +\
                               "from the vendor. Additional to data.vendor_items config")
    profit_parser.add_argument("--buy", "-b", type=str, nargs="+", help="Items to be always bought, even if the can be crafted cheaper. Additional to auctions.buy config")

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

def __get_item_ids(items: List[str], data: DataService) -> List[int]:
    if items is None:
        return []
    return [data.find_item(itm) for itm in items]

def __items_from_list_and_conf(item_list: List[str], config_path: str, config: Config, data: DataService) -> Set[int]:
    result = set() if item_list is None \
        else set(__get_item_ids(item_list, data))
    result.update(config.get_or_default(config_path, []))
    return result

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

def print_recipe(recipe: Recipe, costs: int, price: int, computer: RecipeCostComputer) -> None:
    profit = price * 0.95 - costs
    print(f"{recipe.name}: Price: {price_to_string(price)} Costs: {price_to_string(costs)} Profit: {price_to_string(profit)}")
    if isinstance(recipe, NormalRecipe) or isinstance(recipe, LegendaryRecipe):
        for reagent in recipe.reagents:
            reagent_item = computer.item_cache[reagent.item_id]
            reagent_price = computer.min_prices[reagent.item_id]
            reagent_price_value = reagent_price if isinstance(reagent_price, int) \
                             else reagent_price.price if isinstance(reagent_price, CombinedAuction) \
                             else computer.recipe_production_costs[reagent_price.id]
            reagent_price_label = "Vendor" if isinstance(reagent_price, int) \
                             else "AH" if isinstance(reagent_price, CombinedAuction) \
                             else f"Crafting: {reagent_price.name}"
            reagent_price_total = reagent_price_value * reagent.count
            print(f"    {reagent_item.name}: {price_to_string(reagent_price_value)} * {reagent.count} ({price_to_string(reagent_price_total)}) from {reagent_price_label}")
    else:
        reagent_id = computer.disenchantable_min_items[recipe.id]
        reagent = computer.item_cache[reagent_id]
        reagent_price = computer.min_prices[reagent_id]
        reagent_price_value = reagent_price if isinstance(reagent_price, int) \
                            else reagent_price.price if isinstance(reagent_price, CombinedAuction) \
                            else computer.recipe_production_costs[reagent_price.id]
        reagent_price_label = "Vendor" if isinstance(reagent_price, int) \
                            else "AH" if isinstance(reagent_price, CombinedAuction) \
                            else f"Crafting: {reagent_price.name}"
        print(f"    {reagent.name}: {price_to_string(reagent_price_value)} from {reagent_price_label}")

def handle_profit(args, config: Config, data: DataService, ah: AuctionHouse) -> int:
    professions: Set[Tuple[int, int]] = __get_professions(args.professions, config, data)
    vendor_items = __items_from_list_and_conf(args.vendor_items, "data.vendor_items", config, data)
    buy_items = __items_from_list_and_conf(args.buy, "auctions.buy", config, data)

    computer = RecipeCostComputer(config, data)
    computer.professions = [data.prof_tiers_by_id(prof_id, tier_id) for prof_id, tier_id in professions]
    computer.buy_items = buy_items
    computer.compute_baseline_prices(ah, vendor_items)
    computer.compute_production_costs()

    selling_price = computer.recipe_selling_price
    for recipe in sorted(computer.recipes, key=lambda recipe: not isinstance(recipe,NormalRecipe)):
        if recipe.id not in selling_price or recipe.id not in computer.recipe_production_costs:
            continue
        costs = computer.recipe_production_costs[recipe.id]
        price = selling_price[recipe.id]
        print_recipe(recipe, costs, price, computer)
