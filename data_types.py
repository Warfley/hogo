from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any

class ItemQuality(Enum):
    COMMON = "COMMON"
    UNCOMMON = "UNCOMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"

@dataclass
class Realm:
    id: int
    name: str
    slug: str

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "Realm":
        return Realm(data["id"], data["name"], data["slug"])
    
    def serialize(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug
        }

@dataclass
class ConnectedRealm:
    id: int
    realms: List[Realm]

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "ConnectedRealm":
        return ConnectedRealm(data["id"], [Realm.deserialize(realm_data) for realm_data in data["realms"]])
    
    def serialize(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "realms": [realm.serialize() for realm in self.realms]
        }

@dataclass
class Item:
    id: int
    name: str
    vendor_price: int
    quality: ItemQuality
    item_class: int
    item_subclass: int
    expansion: int

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "Item":
        return Item(id=data["id"],
                    name=data["name"],
                    vendor_price=data["price"],
                    quality=ItemQuality(data["quality"]),
                    item_class=data["class"],
                    item_subclass=data["subclass"],
                    expansion=data["expansion"])
    
    def serialize(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "price": self.vendor_price,
            "quality": self.quality.value,
            "class": self.item_class,
            "subclass": self.item_subclass,
            "expansion": self.expansion
        }

@dataclass
class ItemStack:
    count: float
    item_id: int

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "ItemStack":
        return ItemStack(count=data["count"], item_id=data["item_id"])

    def serialize(self) -> Dict[str, Any]:
        return {
            "count": self.count,
            "item_id": self.item_id
        }

@dataclass
class Recipe:
    id: int
    category: str
    name: str
    profession_id: int
    tier_id: int
    expansion: int

    @staticmethod
    def _deserialize_init_params(data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": data["id"],
            "category": data["category"],
            "name": data["name"],
            "profession_id": data["profession"]["id"],
            "tier_id": data["profession"]["tier"],
            "expansion": data["expansion"]
        }
    
    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "Recipe":
        if data["type"] == "normal":
            return NormalRecipe.deserialize(data)
        elif data["type"] == "legendary":
            return LegendaryRecipe.deserialize(data)
        elif data["type"] == "disenchant":
            return DisenchantRecipe.deserialize(data)
        else:
            raise RuntimeError()
    
    def serialize(self) -> Dict[str, Any]:
        return {
            "type": "normal" if isinstance(self, NormalRecipe) else \
                    "legendary" if isinstance(self, LegendaryRecipe) else \
                    "disenchant" if isinstance(self, DisenchantRecipe) else \
                    "unknown",
            "id": self.id,
            "category": self.category,
            "name": self.name,
            "profession": {
                "id": self.profession_id,
                "tier": self.tier_id
            },
            "expansion": self.expansion
        }

@dataclass
class NormalRecipe(Recipe):
    crafted_item: ItemStack
    reagents: List[ItemStack]

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "NormalRecipe":
        super_params = Recipe._deserialize_init_params(data)
        return NormalRecipe(crafted_item=ItemStack.deserialize(data["crafted_item"]),
                            reagents=[ItemStack.deserialize(reagent) for reagent in data["reagents"]],
                            **super_params)
    
    def serialize(self) -> Dict[str, Any]:
        result = super().serialize()
        result["crafted_item"] = self.crafted_item.serialize()
        result["reagents"] = [reagent.serialize() for reagent in self. reagents]
        return result

@dataclass
class LegendaryRecipe(Recipe):
    item_id: int
    reagents: List[ItemStack]
    rank: int

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "LegendaryRecipe":
        super_params = Recipe._deserialize_init_params(data)
        return LegendaryRecipe(item_id=data["item_id"],
                               reagents=[ItemStack.deserialize(reagent) for reagent in data["reagents"]],
                               rank=data["rank"],
                               **super_params)
    
    def serialize(self) -> Dict[str, Any]:
        result = super().serialize()
        result["item_id"] = self.item_id
        result["reagents"] = [reagent.serialize() for reagent in self. reagents]
        result["rank"] = self.rank
        return result

@dataclass
class DisenchantRecipe(Recipe):
    reagent_quality: ItemQuality
    crafted_items: List[ItemStack]

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "DisenchantRecipe":
        super_params = Recipe._deserialize_init_params(data)
        return DisenchantRecipe(reagent_quality=ItemQuality(data["reagent_quality"]),
                                crafted_items=[ItemStack.deserialize(stack_data) for stack_data in data["crafted_items"]],
                                **super_params)
    
    def serialize(self) -> Dict[str, Any]:
        result = super().serialize()
        result["reagent_quality"] = self.reagent_quality.value
        result["crafted_items"] = [stack.serialize() for stack in self.crafted_items]
        return result

@dataclass
class ProfessionTier:
    id: int
    name: str
    expansion: int

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "ProfessionTier":
        return ProfessionTier(id=data["id"],
                              name=data["name"],
                              expansion=data["expansion"])
    
    def serialize(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "expansion": self.expansion
        }

@dataclass
class Profession:
    id: int
    name: str
    tiers: List[ProfessionTier]

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "Profession":
        return Profession(id=data["id"],
                          name=data["name"],
                          tiers=[ProfessionTier.deserialize(tier_data) for tier_data in data["tiers"]])
    
    def serialize(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tiers": [tier.serialize() for tier in self.tiers]
        }

@dataclass
class ItemModifier:
    modifier_type: int
    value: int

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "ItemModifier":
        return ItemModifier(modifier_type=data["type"],
                            value=data["value"])
    
    def serialize(self) -> Dict[str, Any]:
        return {
            "type": self.modifier_type,
            "value": self.value
        }

@dataclass
class PetInfo:
    breed_id: int
    level: int
    quality_id: int
    species_id: int

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "PetInfo":
        return PetInfo(breed_id=data["breed"],
                       level=data["level"],
                       quality_id=data["quality"],
                       species_id=data["species"])
    
    def serialize(self) -> Dict[str, Any]:
        return {
            "breed": self.breed_id,
            "level": self.level,
            "quality": self.quality_id,
            "species": self.species_id
        }

@dataclass
class AuctionHouseItem:
    id: int
    bonus_lists: List[int]
    modifiers: List[ItemModifier]

    @staticmethod
    def create(id: int, bonus_lists: List[int], modifiers: List[ItemModifier], pet_info: PetInfo) -> "AuctionHouseItem":
        if pet_info is None:
            return AuctionHouseItem(id, bonus_lists, modifiers)
        return AuctionHousePetItem(id, bonus_lists, modifiers, pet_info)

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> "AuctionHouseItem":
        params = {"id": data["id"],
                  "bonus_lists": [bonus for bonus in data.get("bonus_lists", [])],
                  "modifiers": [ItemModifier.deserialize(mod_data) for mod_data in data.get("modifiers", [])]
        }
        if "pet_info" in data:
            return AuctionHousePetItem(pet_info=PetInfo.deserialize(data[PetInfo]), **params)
        return AuctionHouseItem(**params)
    
    def serialize(self) -> Dict[str, Any]:
        result = {"id": self.id}
        if self.bonus_lists:
            result["bonus_lists"] = self.bonus_lists.copy()
        if self.modifiers:
            result["modifiers"] = [mod.serialize() for mod in self.modifiers]
        return result

@dataclass
class AuctionHousePetItem(AuctionHouseItem):
    pet_info: PetInfo

    def serialize(self) -> Dict[str, Any]:
        result = super().serialize()
        result["pet_info"] = self.pet_info.serialize()
        return result

@dataclass
class Auction:
    id: int
    price: int
    quantity: int
    time_left: str
    item: AuctionHouseItem

class CombinedAuction:
    @staticmethod
    def generate_id(price: int, item: AuctionHouseItem) -> str:
        return f"Price={price}; item={str(item)})"

    def __init__(self, auction: Auction=None, data: Dict[str, Any]=None):
        assert (auction is not None) != (data is not None)
        self.price: int = None
        self.item: AuctionHouseItem = None
        self.quantity: int = None
        if auction is not None:
            self.price = auction.price
            self.item = auction.item
            self.quantity = auction.quantity
        else:
            self.price = data["price"]
            self.quantity = data["quantity"]
            self.item = AuctionHouseItem.deserialize(data["item"])
        self.id = self.generate_id(self.price, self.item)
    
    def serialize(self) -> Dict[str, Any]:
        return {"price": self.price, "quantity": self.quantity, "item": self.item.serialize()}
