from config import Config
from wow_api import WoWAPI, AuctionHouseItem, ItemModifier, PetInfo, Auction
from argparse import ArgumentParser
from data import DataService
from pathlib import Path
from typing import List, Dict, Any
import yaml

def serialize_modifier(modifier: ItemModifier) -> Dict[str, Any]:
    return {"type": modifier.key, "value": modifier.value}

def serialize_pet_info(pet_info: PetInfo) -> Dict[str, Any]:
    return {"breed": pet_info.breed_id, "level": pet_info.level, "quality": pet_info.quality_id, "species": pet_info.species_id}

def serialize_item(item: AuctionHouseItem) -> Dict[str, Any]:
    data = {"id": item.id,
            "modifiers": [serialize_modifier(m) for m in item.modifiers],
            "bonus_lists": item.bonus_lists
           }
    if item.pet_info is not None:
        data["pet_info"] = serialize_pet_info(item.pet_info)
    return data

def serialize_auction(auction: Auction) -> Dict[str, Any]:
    return {"id": auction.id, "price": auction.price, "quantity": auction.quantity, 
            "time_left": auction.time_left, "item": serialize_item(auction.item)}

def deserialize_modifier(data: Dict[str, Any]) -> ItemModifier:
    return ItemModifier(data["type"], data["value"])

def deserialize_pet_info(data: Dict[str, Any]) -> PetInfo:
    return PetInfo(data["breed"], data["level"], data["quality"], data["species"])

def deserialize_item(data: Dict[str, Any]) -> AuctionHouseItem:
    modifiers = [deserialize_modifier(md) for md in data["modifiers"]]
    pet_info = deserialize_pet_info(data["pet_info"]) if "pet_info" in data \
          else None
    return AuctionHouseItem(data["id"], data["bonus_lists"], modifiers, pet_info)

def deserialize_auction(data: Dict[str, Any]) -> Auction:
    return Auction(data["id"], data["price"], data["quantity"], data["time_left"],
                   deserialize_item(data["item"]))

class AuctionHouse:
    def __init__(self, config: Config, data_dir: Path = Path("auctions")):
        self.config = config
        self.data_file = data_dir/f"{config['server.region']}.{config['server.realm']}.yml"
        self.__auctions: Dict[int, Auction] = {}
        data_dir.mkdir(parents=True, exist_ok=True)
        self.api = WoWAPI(config)
    
    def get_auctions(self) -> Dict[int, Auction]:
        if self.__auctions == {}:
            self.__auctions = self.__load_data()
        return self.__auctions
    
    def __load_data(self) -> Dict[int, Auction]:
        if not self.data_file.exists():
            return {}
        with open(self.data_file, "r") as fl:
            raw_data = yaml.load(fl, Loader=yaml.FullLoader)
            self.__auctions = {ad["item"]["id"]: deserialize_auction(ad) for ad in raw_data}
    
    def __store_data(self) -> None:
        with open(self.data_file, "w") as fl:
            raw_data = [serialize_auction(a) for a in self.__auctions.values()]
            yaml.dump(raw_data, fl)
    
    def update(self, connected_realm_id: int) -> None:
        self.api.generate_token()
        auctions = self.api.load_auctions(connected_realm_id)
        self.__auctions = {a.item.id: a for a in auctions}
        self.__store_data()
    
    def clear_data(self) -> None:
        self.__auctions = {}
        self.data_file.unlink()
    
def init_auction_parser(parser: ArgumentParser) -> None:
    parser.add_argument("--update", "-u", action="store_true", default=False, help="Update before taking the action")

    parsers = parser.add_subparsers(dest="subcommand")
    parsers.add_parser("update", help="Update local AH data")
    search_parser = parsers.add_parser("search", help="Search auctions")
    search_parser.add_argument("keywords", type=str, nargs="+")
    profit_parser = parsers.add_parser("profit", help="Compute profit")
    profit_parser.add_argument("--professions", "-p", nargs="+", default=["config"], type=str, 
                               help="Using crafting from these professions, profession names " +\
                                    "in configured language or config to read from config (default=config)")
    profit_parser.add_argument("--search", "-s", type=str, help="Search terms to search for specific items")
    profit_parser.add_argument("--vendor-items", "-i", nargs="+", type=int, help="The IDs of items that can be bought " +\
                               "from the vendor. Alternatively add them to the 'data.vendor_items' config")

def __get_connected_realm_id(config) -> int:
    data = DataService(config)
    connected_realm_id, _ = data.find_realm(config["server.realm"])
    return connected_realm_id

def handle_auction_command(args, config: Config) -> int:
    ah = AuctionHouse(config)
    if args.subcommand == "update":
        print("Updating auction list...", end=" ", flush=True)
        ah.update(__get_connected_realm_id(config))
        print("done")
        return 0
    if args.update:
        print("Updating auction list...", end=" ", flush=True)
        ah.update(__get_connected_realm_id(config))
        print("done")
    # TODO: implement search and profit
    return 0
