from config import Config
from argparse import ArgumentParser
from pathlib import Path
from wow_api import WoWAPI
from data_types import ConnectedRealm, \
                       Realm, \
                       Profession, \
                       ProfessionTier, \
                       Item, \
                       Recipe, \
                       NormalRecipe, \
                       LegendaryRecipe, \
                       DisenchantRecipe, \
                       ItemQuality, \
                       ItemStack
import yaml
from typing import List, Dict, Any, Tuple, Set, Tuple

from logging import info, warning

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
            return [ConnectedRealm.deserialize(crd) for crd in raw_data]
    
    def __store_realms(self) -> None:
        realm_file = self.data_dir/"realms.yml"
        with open(realm_file, "w") as fl:
            raw_data = [r.serialize() for r in self.__realms]
            yaml.dump(raw_data, fl)
    
    def __load_professions(self) -> List[Profession]:
        profession_file = self.data_dir/"professions.yml"
        if not profession_file.exists():
            return []
        with open(profession_file, "r") as fl:
            raw_data = yaml.load(fl, Loader=yaml.FullLoader)
            return [Profession.deserialize(pd) for pd in raw_data]
    
    def __store_professions(self) -> None:
        profession_file = self.data_dir/"professions.yml"
        with open(profession_file, "w") as fl:
            raw_data = [p.serialize() for p in self.__professions]
            yaml.dump(raw_data, fl)
    
    def __load_recipes(self) -> List[Recipe]:
        recipe_file = self.data_dir/"recipes.yml"
        if not recipe_file.exists():
            return []
        with open(recipe_file, "r") as fl:
            raw_data = yaml.load(fl, Loader=yaml.FullLoader)
            return [Recipe.deserialize(rd) for rd in raw_data]
    
    def __store_recipes(self) -> None:
        recipe_file = self.data_dir/"recipes.yml"
        with open(recipe_file, "w") as fl:
            raw_data = [r.serialize() for r in self.__recipes]
            yaml.dump(raw_data, fl)

    def __load_items(self) -> List[Item]:
        item_file = self.data_dir/"items.yml"
        if not item_file.exists():
            return []
        with open(item_file, "r") as fl:
            raw_data = yaml.load(fl, Loader=yaml.FullLoader)
            return [Item.deserialize(i) for i in raw_data]
    
    def __store_items(self) -> None:
        item_file = self.data_dir/"items.yml"
        with open(item_file, "w") as fl:
            raw_data = [i.serialize() for i in self.__items]
            yaml.dump(raw_data, fl)

    def update_realms(self) -> None:
        self.api.generate_token()
        self.__realms = self.api.load_realms()
        self.__store_realms()
    
    def update_professions(self) -> None:
        self.api.generate_token()
        self.__professions = self.api.load_professions()
        self.__store_professions()
    
    @staticmethod
    def __normal_recipe_to_legendary(recipe: NormalRecipe, rank: int) -> LegendaryRecipe:
        return LegendaryRecipe(id=recipe.id,
                               category=recipe.category,
                               name=f"{recipe.name} (Rank {rank})",
                               profession_id=recipe.profession_id,
                               tier_id=recipe.tier_id,
                               expansion=recipe.expansion,
                               item_id=recipe.crafted_item.item_id,
                               reagents=recipe.reagents,
                               rank=rank)

    # shadowlands specific code
    @staticmethod
    def __make_legendary_recipes(recipes: List[NormalRecipe]) -> List[Recipe]:
        by_item: Dict[int, List[NormalRecipe]] = {}
        for recipe in recipes:
            r_list = by_item.get(recipe.crafted_item.item_id, [])
            r_list.append(recipe)
            by_item[recipe.crafted_item.item_id] = r_list
        result: List[Recipe] = []
        for same_item_recipes in by_item.values():
            if len(same_item_recipes) == 1:
                result.extend(same_item_recipes)
                continue
            # this is a legendary recipe the ids are ascending with the rank
            legendary_recipes = [DataService.__normal_recipe_to_legendary(recipe, i + 1) \
                                 for i, recipe in enumerate(sorted(same_item_recipes, key=lambda r: r.id))]
            result.extend(legendary_recipes)
        return result

    def update_recipes(self, profession_tiers: List[Tuple[Profession, ProfessionTier]]) -> None:
        self.api.generate_token()
        self.__recipes = []
        sl_exp = self.config["data.expansions.shadowlands"]
        legendary_professions = {
            self.config["data.profession_ids.blacksmithing"],
            self.config["data.profession_ids.tailoring"],
            self.config["data.profession_ids.leatherworking"],
            self.config["data.profession_ids.jewelcrafting"],
        }
        for prof, tier in profession_tiers:
            recipes = self.api.load_recipes(prof, tier)
            # add legendary information for shadowlands recipes
            if tier.expansion == sl_exp and prof.id in legendary_professions:
                recipes = self.__make_legendary_recipes(recipes)
            self.__recipes.extend(recipes)
        self.__store_recipes()
    
    def __update_item(self, item_id: int, cache: Set[int], expansion: int) -> None:
        if item_id in cache:
            return
        self.__items.append(self.api.load_item(item_id, expansion))
        cache.add(item_id)

    def update_items(self) -> None:
        self.api.generate_token()
        self.__items = []
        cache = set()
        for recipe in self.get_recipes():
            crafted_item = recipe.item_id if isinstance(recipe, LegendaryRecipe) \
                           else recipe.crafted_item.item_id if isinstance(recipe, NormalRecipe) \
                           else None
            if crafted_item is not None:
                self.__update_item(crafted_item, cache, recipe.expansion)
            for reagent in recipe.reagents:
                self.__update_item(reagent.item_id, cache, recipe.expansion)
        self.__store_items()
    
    def __get_enchantment_mats_by_expansion(self, expansions: Set[int], item_cache: Dict[int, Item]) -> Dict[int, Dict[ItemQuality, int]]:
        enchant_mat_class = self.config["data.item_classes.crafting_material.id"]
        enchantment_mat_subclass = self.config["data.item_classes.crafting_material.subclasses.enchantment"]
        enchantment_id = self.config["data.profession_ids.enchanting"]
        enchantment_prof, _ = self.prof_tiers_by_id(enchantment_id, None)
        prof_tiers = {(enchantment_id, tier.id) for tier in enchantment_prof.tiers if tier.expansion in expansions}
        tier_expansions = {tier.id: tier.expansion for tier in enchantment_prof.tiers if tier.expansion in expansions}

        recipes = self.profession_recipes(prof_tiers)

        result: Dict[int, Dict[ItemQuality, int]] = {exp: {} for exp in expansions}

        # iterate of all recipes and search for the mats
        for recipe in recipes:
            if not isinstance(recipe, NormalRecipe):
                continue
            recipe_exp = tier_expansions[recipe.tier_id]
            for reagent in recipe.reagents:
                reagent_item = item_cache[reagent.item_id]
                if reagent_item.item_class == enchant_mat_class and reagent_item.item_subclass == enchantment_mat_subclass:
                    result[recipe_exp][reagent_item.quality] = reagent_item.id
        return result
    
    def create_disenchantment_recipes(self, expansions: Set[int]) -> List[DisenchantRecipe]:
        enchantment_id = self.config["data.profession_ids.enchanting"]
        enchantment_prof, _ = self.prof_tiers_by_id(enchantment_id, None)
        expansion_tiers = {tier.expansion: tier for tier in enchantment_prof.tiers}
        probability_tables = self.config["data.disenchantment"]
        quality_ids = {
            ItemQuality.COMMON: 1,
            ItemQuality.UNCOMMON: 2,
            ItemQuality.RARE: 3,
            ItemQuality.EPIC: 4
        }
        item_cache: Dict[int, Item] = {item.id: item for item in self.get_items()}
        enchantment_mats = self.__get_enchantment_mats_by_expansion(expansions, item_cache)
        recipes: List[DisenchantRecipe] = []
        for expansion, mats in enchantment_mats.items():
            for quality in mats.keys():
                tier = expansion_tiers[expansion]
                recipe_id = -(expansion * 10 + quality_ids[quality])
                recipe_name = f"{tier.name}: Disenchanting {quality.value}"
                probabilities: Dict[ItemQuality, float] = {ItemQuality(quality): prob for quality, prob in probability_tables[quality.value].items()}
                crafted_items = []
                for item_quality, item_prob in probabilities.items():
                    if item_quality in mats:
                        crafted_items.append(ItemStack(item_prob, mats[item_quality]))
                recipe = DisenchantRecipe(id=recipe_id, category="disenchant", name=recipe_name,
                                          profession_id=enchantment_id, tier_id=tier.id,
                                          expansion=expansion, reagent_quality=quality,
                                          crafted_items=crafted_items)
                recipes.append(recipe)
        self.__recipes.extend(recipes)
        self.__store_recipes()

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
    
    def professions_by_expansion(self, expansion: int) -> List[Tuple[Profession, ProfessionTier]]:
        result = []
        for prof in self.get_professions():
            if len(prof.tiers) > 0:
                tier: ProfessionTier = [tier for tier in prof.tiers if tier.expansion == expansion][0]
                result.append((prof, tier))
        return result


    def latest_professions(self) -> List[Tuple[Profession, ProfessionTier]]:
        current_expansion = self.config["data.expansions.current"]
        return self.professions_by_expansion(current_expansion)
    
    def all_professions(self) -> List[Tuple[Profession, ProfessionTier]]:
        result = []
        for prof in self.get_professions():
            result.extend([(prof, tier) for tier in prof.tiers])
        return result
    
    def prof_tiers_by_id(self, prof_id: int, tier_id: int) -> Tuple[Profession, ProfessionTier]:
        for prof in self.get_professions():
            if prof.id == prof_id:
                if tier_id is None:
                    return prof, None
                for tier in prof.tiers:
                    if tier.id == tier_id:
                        return prof, tier
                return prof, None
        return None, None
    
    def config_professions(self) -> List[Tuple[Profession, ProfessionTier]]:
        result = []
        for prof_tier in self.config.get_or_default("data.professions", []):
            pt = prof_tier.split("-")
            prof_id = int(pt[0])
            tier_id = int(pt[1])
            prof, tier = self.prof_tiers_by_id(prof_id, tier_id)
            assert prof is not None and tier is not None
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
    enchantment_id = config["data.profession_ids.enchanting"]
    data = DataService(config)
    if args.target == "realms":
        info("Updating realms...")
        data.update_realms()
        info("Realms successfully updated")
    elif args.target == "professions":
        info("Updating professions...")
        data.update_professions()
        info("Professions successfully updated")
    elif args.target == "recipes":
        info("Updating recipes...")
        prof_tiers = data.all_professions() if args.professions == "all" \
                else data.config_professions() if args.professions == "config" \
                else data.latest_professions()
        expansions = {tier.expansion for prof, tier in prof_tiers if prof.id == enchantment_id}
        data.update_recipes(prof_tiers)
        info("Creating disenchantment recipes...")
        data.create_disenchantment_recipes(expansions)
        info("Recipes successfully updated")
    elif args.target == "items":
        info("Updating items...")
        data.update_items()
        info("Items successfully updated")
    else: # all
        info("Updating realms...")
        data.update_realms()
        info("Realms successfully updated")
        info("Updating professions...")
        data.update_professions()
        info("Professions successfully updated")
        info("Updating recipes...")
        prof_tiers = data.latest_professions()
        data.update_recipes(prof_tiers)
        info("Recipes successfully updated")
        info("Updating items...")
        data.update_items()
        info("Items successfully updated")
        info("Creating disenchantment recipes...")
        expansions = {tier.expansion for prof, tier in prof_tiers if prof.id == enchantment_id}
        data.create_disenchantment_recipes(expansions)
        info("Disenchantment recipes successfully created")
    return 0
