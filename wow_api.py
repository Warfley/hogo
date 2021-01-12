import requests as req
from config import Config
from pathlib import Path
from typing import Dict, List, Tuple
from urllib import parse

from enum import Enum
from dataclasses import dataclass

import re

class Namespace(Enum):
    STATIC="static"
    DYNAMIC="dynamic"
    PROFILE="profile"

@dataclass
class Realm:
    id: int
    name: str

@dataclass
class ConnectedRealm:
    id: int
    realms: List[Realm]

@dataclass
class Item:
    id: int
    name: str
    vendor_price: int

@dataclass
class ItemStack:
    count: int
    item_id: int

@dataclass
class Recipe:
    id: int
    category: str
    name: str
    profession_id: int
    tier_id: int
    crafted_item: ItemStack
    reagents: List[ItemStack]

@dataclass
class ProfessionTier:
    id: int
    name: str
    recipes: Dict[int, Recipe]

@dataclass
class Profession:
    id: int
    name: str
    tiers: Dict[int, ProfessionTier]

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
    
    def __construct_url(self, path: str, namespace: Namespace, params: Dict[str, str] = {}) -> str:
        extended_params: Dict[str, str] = params.copy()
        extended_params.update({
            "locale": self.conf["data.language"],
            "namespace": f"{namespace.value}-{self.conf['server.region']}",
            "access_token": self.token
        })
        param_list = [f"{parse.quote(key)}={parse.quote(value)}" for key, value in extended_params.items()]
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
        realms = [Realm(realm["id"], realm["name"]) for realm in resp_data["realms"]]
        return ConnectedRealm(realm_id, realms)
    
    def load_realms(self) -> List[ConnectedRealm]:
        realm_ids = self.load_connected_realm_list()
        return [self.load_connected_realm_data(rid) for rid in realm_ids]
    
    def load_profession_list(self) -> List[Profession]:
        url = self.__construct_url("/data/wow/profession/index", Namespace.STATIC)
        resp: req.Response = req.get(url)
        assert resp.status_code == 200
        resp_data = resp.json()
        return [Profession(p["id"], p["name"], {}) for p in resp_data["professions"]]
    
    def load_profession_tiers(self, profession_id) -> List[ProfessionTier]:
        url = self.__construct_url(f"/data/wow/profession/{profession_id}", Namespace.STATIC)
        resp: req.Response = req.get(url)
        assert resp.status_code == 200
        resp_data = resp.json()
        return [ProfessionTier(pt["id"], pt["name"], {}) for pt in resp_data["skill_tiers"]] \
            if "skill_tiers" in resp_data else []

    def load_professions(self) -> List[Profession]:
        profs = self.load_profession_list()
        for prof in profs:
            prof.tiers = {t.id: t for t in self.load_profession_tiers(prof.id)}
        return profs
    