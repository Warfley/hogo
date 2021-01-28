import requests as req
from config import Config
from pathlib import Path
from typing import List, Tuple, Dict, Union, Iterable
from urllib import parse
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
                       Recipe, \
                       NormalRecipe, \
                       ItemQuality, \
                       ItemStack

from enum import Enum
from dataclasses import dataclass

import re

ParameterList = Union[Dict[str, str], Iterable[Tuple[str, str]]]

class Namespace(Enum):
    STATIC="static"
    DYNAMIC="dynamic"
    PROFILE="profile"

class WoWAPI:
    def __init__(self, conf: Config):
        self.conf: Config = conf
        self.token: str = None
    
    def generate_token(self) -> None:
        url = f"https://{self.conf['server.region']}.battle.net/oauth/token"
        auth_data = (self.conf["client.id"], self.conf["client.pass"])
        resp: req.Response = req.post(url, auth=auth_data, data={"grant_type": "client_credentials"})
        assert resp.status_code == 200
        resp_data = resp.json()
        self.token = resp_data["access_token"]
    
    def __construct_url(self, path: str, namespace: Namespace, params: ParameterList = {}) -> str:
        extended_params: List[Tuple[str, str]] = [(key, value) for key, value in 
                                                  (params.items() if isinstance(params, dict) else params)]
        extended_params.extend([
            ("locale", self.conf["data.language"]),
            ("namespace", f"{namespace.value}-{self.conf['server.region']}"),
            ("access_token", self.token)
        ])
        param_list = [f"{parse.quote(key)}={parse.quote(value)}" for key, value in extended_params]
        return f"https://{self.conf['server.region']}.api.blizzard.com{path}?{'&'.join(param_list)}"

    def load_connected_realm_list(self) -> List[int]:
        url = self.__construct_url("/data/wow/connected-realm/index", Namespace.DYNAMIC)
        resp: req.Response = req.get(url)
        assert resp.status_code == 200
        resp_data = resp.json()
        href_regex = re.compile("https://[a-z]{2,2}\\.api\\.blizzard\\.com/data/wow/connected-realm/([\\d]+)")
        result: List[int] = []
        for ce in resp_data["connected_realms"]:
            match = href_regex.match(ce["href"])
            assert match is not None
            realm_id = int(match.group(1))
            result.append(realm_id)
        return result
    
    def load_connected_realm_data(self, realm_id: int) -> ConnectedRealm:
        url = self.__construct_url(f"/data/wow/connected-realm/{realm_id}", Namespace.DYNAMIC)
        resp: req.Response = req.get(url)
        assert resp.status_code == 200
        resp_data = resp.json()
        realms = [Realm(realm["id"], realm["name"], realm["slug"]) for realm in resp_data["realms"]]
        return ConnectedRealm(realm_id, realms)
    
    def load_realms(self) -> List[ConnectedRealm]:
        realm_ids = self.load_connected_realm_list()
        return [self.load_connected_realm_data(rid) for rid in realm_ids]
    
    def load_profession_list(self) -> List[Profession]:
        url = self.__construct_url("/data/wow/profession/index", Namespace.STATIC)
        resp: req.Response = req.get(url)
        assert resp.status_code == 200
        resp_data = resp.json()
        return [Profession(p["id"], p["name"], []) for p in resp_data["professions"]]
    
    @staticmethod
    def __get_profession_tier_expansions(tier_ids: List[int]) -> Dict[int, int]:
        tier_ids = sorted(tier_ids)[::-1]
        # this is really a mess:
        # shadowlands made a huge jump, the rest is sorted descending
        shadowlands_id = tier_ids[0]
        result = {
            tid: i+1 for i, tid in enumerate(tier_ids[1:])
        }
        result[shadowlands_id] = 9
        return result
    
    def load_profession_tiers(self, profession_id) -> List[ProfessionTier]:
        url = self.__construct_url(f"/data/wow/profession/{profession_id}", Namespace.STATIC)
        resp: req.Response = req.get(url)
        assert resp.status_code == 200
        resp_data = resp.json()
        if "skill_tiers" not in resp_data:
            return []
        tier_expansions = self.__get_profession_tier_expansions([tier_data["id"] for tier_data in resp_data["skill_tiers"]])
        return [ProfessionTier(id=tier_data["id"], name=tier_data["name"], expansion=tier_expansions[tier_data["id"]]) 
                for tier_data in resp_data["skill_tiers"]]

    def load_professions(self) -> List[Profession]:
        profs = self.load_profession_list()
        for prof in profs:
            prof.tiers = self.load_profession_tiers(prof.id)
        return profs
    
    def load_recipe_list(self, profession: Profession, tier: ProfessionTier) -> List[Recipe]:
        profession_id = profession.id
        tier_id = tier.id
        url = self.__construct_url(f"/data/wow/profession/{profession_id}/skill-tier/{tier_id}", Namespace.STATIC)
        resp: req.Response = req.get(url)
        assert resp.status_code == 200
        resp_data = resp.json()
        if "categories" not in resp_data:
            return []
        result: List[Recipe] = []
        for cat in resp_data["categories"]:
            cat_name = cat["name"]
            result.extend([NormalRecipe(id=r["id"], category=cat_name, name=r["name"],
                                        profession_id=profession_id, tier_id=tier_id,
                                        expansion=tier.expansion, crafted_item=None,
                                        reagents=[]) for r in cat["recipes"]],)
        return result
    
    def load_recipe_data(self, recipe: Recipe) -> Recipe:
        url = self.__construct_url(f"/data/wow/recipe/{recipe.id}", Namespace.STATIC)
        resp: req.Response = req.get(url)
        assert resp.status_code == 200
        resp_data = resp.json()
        if "crafted_item" not in resp_data:
            items = self.search_items(resp_data["name"])
            assert len(items) <= 1
            if not items:
                return None
            if "crafted_quantity" not in resp_data:
                resp_data["crafted_quantity"] = {"value": 1}
            resp_data["crafted_item"] = {"id": items[0]}
        q_data = resp_data["crafted_quantity"]
        quantity = q_data["value"] if "value" in q_data \
             else (q_data["maximum"] - q_data["minimum"]) / 2 + q_data["minimum"]
        recipe.crafted_item = ItemStack(quantity, resp_data["crafted_item"]["id"])
        recipe.reagents = [ItemStack(rg["quantity"], rg["reagent"]["id"]) for rg in resp_data["reagents"]]
        return recipe
    
    def load_recipes(self, profession: Profession, tier: ProfessionTier) -> List[Recipe]:
        result = self.load_recipe_list(profession, tier)
        for r in result:
            self.load_recipe_data(r)
        return result
    
    def load_item(self, item_id: int, expansion: int) -> Item:
        url = self.__construct_url(f"/data/wow/item/{item_id}", Namespace.STATIC)
        resp: req.Response = req.get(url)
        assert resp.status_code == 200
        resp_data = resp.json()
        return Item(id=item_id, name=resp_data["name"], vendor_price=resp_data["purchase_price"],
                    quality=ItemQuality(resp_data["quality"]["type"]), item_class=resp_data["item_class"]["id"],
                    item_subclass=resp_data["item_subclass"]["id"], expansion=expansion)
    
    def search_items(self, item_name: str) -> List[int]:
        name_parts = [part for part in item_name.split(" ") if len(part) > 3]
        params=[
            ("orderby", "id"),
            ("_page", "1")
        ]
        params.extend([(f"name.{self.conf['data.language']}", part) for part in name_parts])
        url = self.__construct_url(f"/data/wow/search/item", Namespace.STATIC, params=params)
        resp: req.Response = req.get(url)
        assert resp.status_code == 200
        resp_data = resp.json()
        return [result["data"]["id"] for result in resp_data["results"]]
    
    def load_auctions(self, connected_realm_id: int) -> List[Auction]:
        url = self.__construct_url(f"/data/wow/connected-realm/{connected_realm_id}/auctions", Namespace.DYNAMIC)
        resp: req.Response = req.get(url)
        assert resp.status_code == 200
        resp_data = resp.json()
        result = []
        for auction_data in resp_data["auctions"]:
            if "buyout" not in auction_data and "unit_price" not in auction_data:
                continue # only support direct buy auctions
            item_data: dict = auction_data["item"]
            bonus_lists = item_data.get("bonus_lists", [])
            modifiers = [ItemModifier(m["type"], m["value"]) for m in item_data.get("modifiers", [])]
            pet_info = PetInfo(item_data["pet_breed_id"], item_data["pet_level"], 
                               item_data["pet_quality_id"], item_data["pet_species_id"]) if "pet_level" in item_data \
                        else None
            item = AuctionHouseItem.create(item_data["id"], bonus_lists, modifiers, pet_info)
            quantity = auction_data["quantity"]
            price = auction_data["buyout"] / quantity if "buyout" in auction_data \
               else auction_data["unit_price"]
            auction = Auction(auction_data["id"], price, quantity, auction_data["time_left"],
                              item)
            result.append(auction)
        return result
