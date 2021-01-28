import yaml
from pathlib import Path
from typing import Dict, Any, List
from copy import deepcopy
from data_types import ItemQuality
import re

CONF_PATH = Path("hogo.yml")

def validate_language(lang: str) -> bool:
    return re.match("[a-z][a-z]_[A-Z][A-Z]", lang) is not None

def validate_region(region: str) -> bool:
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
           and "data.language" in self \
           and "data.current_expansion" in self
        
    def fill_defaults(self):
        # professions
        if "data.profession_ids.blacksmithing" not in self:
            self["data.profession_ids.blacksmithing"] = 164
        if "data.profession_ids.leatherworking" not in self:
            self["data.profession_ids.leatherworking"] = 165
        if "data.profession_ids.alchemy" not in self:
            self["data.profession_ids.alchemy"] = 171
        if "data.profession_ids.herbalism" not in self:
            self["data.profession_ids.herbalism"] = 182
        if "data.profession_ids.cooking" not in self:
            self["data.profession_ids.cooking"] = 185
        if "data.profession_ids.mining" not in self:
            self["data.profession_ids.mining"] = 186
        if "data.profession_ids.tailoring" not in self:
            self["data.profession_ids.tailoring"] = 197
        if "data.profession_ids.engineering" not in self:
            self["data.profession_ids.engineering"] = 202
        if "data.profession_ids.enchanting" not in self:
            self["data.profession_ids.enchanting"] = 333
        if "data.profession_ids.fishing" not in self:
            self["data.profession_ids.fishing"] = 356
        if "data.profession_ids.skinning" not in self:
            self["data.profession_ids.skinning"] = 393
        if "data.profession_ids.jewelcrafting" not in self:
            self["data.profession_ids.jewelcrafting"] = 755
        if "data.profession_ids.inscription" not in self:
            self["data.profession_ids.inscription"] = 773
        if "data.profession_ids.archeology" not in self:
            self["data.profession_ids.archeology"] = 794
        # expansions:
        if "data.expansions.shadowlands" not in self:
            self["data.expansions.shadowlands"] = 9
        if "data.expansions.bfa" not in self:
            self["data.expansions.bfa"] = 8
        if "data.expansions.legion" not in self:
            self["data.expansions.legion"] = 7
        if "data.expansions.wod" not in self:
            self["data.expansions.wod"] = 6
        if "data.expansions.mop" not in self:
            self["data.expansions.mop"] = 5
        if "data.expansions.cataclysm" not in self:
            self["data.expansions.cataclysm"] = 4
        if "data.expansions.wotlk" not in self:
            self["data.expansions.wotlk"] = 3
        if "data.expansions.tbc" not in self:
            self["data.expansions.tbc"] = 2
        if "data.expansions.classic" not in self:
            self["data.expansions.classic"] = 1
        # disenchantment table
        if "data.disenchantment" not in self:
            # fixme: insert correct values
            self["data.disenchantment"] = {
                ItemQuality.COMMON.value: {
                    ItemQuality.COMMON.value: 1.5
                },
                ItemQuality.UNCOMMON.value: {
                    ItemQuality.COMMON.value: 1.5,
                    ItemQuality.UNCOMMON.value: 1.5
                },
                ItemQuality.RARE.value: {
                    ItemQuality.COMMON.value: 1.5,
                    ItemQuality.UNCOMMON.value: 1.5,
                    ItemQuality.RARE.value: 1.5
                },
                ItemQuality.EPIC.value: {
                    ItemQuality.COMMON.value: 1.5,
                    ItemQuality.UNCOMMON.value: 1.5,
                    ItemQuality.RARE.value: 1.5,
                    ItemQuality.EPIC.value: 1.5
                }
            }
        # item classes (only what is used by hogo)
        if "data.item_classes.armor.id" not in self:
            self["data.item_classes.armor.id"] = 4
        if "data.item_classes.weapon.id" not in self:
            self["data.item_classes.weapon.id"] = 2
        if "data.item_classes.crafting_material.id" not in self:
            self["data.item_classes.crafting_material.id"] = 7
        # item subclasses (only what is used by hogo)
        if "data.item_classes.crafting_material.subclasses.enchantment" not in self:
            self["data.item_classes.crafting_material.subclasses.enchantment"] = 12

    def update_from_args(self, args) -> None:
        if args.region is not None:
            if validate_region(args.region):
                self["server.region"] = args.region
        if args.realm is not None:
            self["server.realm"] = args.realm
        if args.language is not None:
            if validate_language(args.language):
                self["data.language"] = args.language
        if args.client_id is not None:
            self["client.id"] = args.client_id
        if args.client_pass is not None:
            self["client.pass"] = args.client_pass
    
    def copy(self) -> "Config":
        result = Config()
        result.data = deepcopy(self.data)
    
    def get_or_default(self, key: str, default: Any) -> Any:
        result = self[key]
        if result is None:
            return default
        return result
