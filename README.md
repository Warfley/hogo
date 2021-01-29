# hogo

hogo is a command line tool for calculating profits you can make by crafting items.
It does so by downloading the current auction house state and computing the production costs for every recipe of a given profession.

## Requirements
This program requires python3 with the libraries pyyaml and requests.
It should work on any operating system.

## Usage
To use this program you first need to download the game data (i.e. professions, recipes, etc.).
### Configuration
But before you can do this you need to create a `hogo.yml` file which serves as a configuration file.
To create that file first run:
```bash
$ python3 hogo config init
```
This will prompt you to enter some configuration data:
- Server region: one of the following: us, eu, ch, kr, tw or cn
- Data language: the locale of your language, e.g en_US, en_GB, de_DE, fr_FR
- Realm: the slug of the realm you want to fetch the ah info from (a slug is the lowercase name of a server without any special chars, e.g. Vol'jin becomes voljin)
- API client ID: The ID of your API client (you can create one at https://develop.battle.net/access/)
- API client secret: the secret of that API client

If you want to change these settings later, you don't need to create a completely new configuration.
For temporary changes you can just pass the following arguments right behind the hogo in the command:
- `--language` or `-l` to set the language/locale
- `--region` or `-r` to set the region
- `--realm` or `-s` to set the realm slug
- `--client-id` or `-c` to set the API client ID
- `--client-pass` or `-p` the API client secret

To make that change persistent you can call `config update`. Example to change the realm to Blackrock
```bash
$ python3 hogo -r blackrock config update
```

Besides these configurations you also to configure some things manually.
Generally speaking, the game data will be downloaded dynamically from the Blizzard API.

But this data is rather limited, therefore some information need to be given by hand.
One such information is which items can be bough of a vendor.
This can be submitted via different config commands.
As they require to lookup the name of certain items, these features are only available after the download of the data (see next section).
Too add vendor items just use the following command:
```bash
# if language is en_US
$ python3 hogo config vendoritems add "Orboreal Shard"
# de_DE
$ python3 hogo config vendoritems add "Orborealer Splitter"
```
If you don't add these configurations, the program can only look at the AH prices for computing the crafting costs.

Other useful configurations is `professions`, with which you can set your default professions so you don't have to add them to the command, and `buyitems` with which you can specify items that should always be bought and not crafted, even if crafting them yourself is cheaper (because it is just a waste of time):
```bash
$ python3 hogo professions add "Shadowlands Leatherworking"
$ python3 hogo buyitems add "Heavy Callous Hide"
```
Again these names have to be given in the currently selected language

### Loading game data
To download the game data, you can use the update command:
```
$ python3 hogo update
```
This takes a while. To update only certain parts of the data you can use sub commands, which you can look into with
```bash
$ python3 hogo update --help
```
By default it downloads only information about the newest expansion (i.e. only current professions). See `--help` for further information on how to download more.

Data can be downloaded for multiple languages without any conflict. so you can just add data in other languages via:
```bash
$ python3 hogo -l de_DE update
```

### Profit computations
So after the config was created and the data is downloaded, you can start to use the profit computation of this feature. This is accessible via the command `auctions`.

First you need to download the auction data. This can be either done with:
```bash
$ python3 hogo auctions update
```
but can also be combined with any other command by supplying the `-u` flag.

To compute the profit use the `profit` subcommand:
```bash
$ python3 hogo auctions -u profit
```
This will compute the profits for every recipe for any profession in your config.

You can configure this by using the following flags:
- `--professions` or `-p` compute the profit margins for the following professions (`config` to also consider the configured professions, otherwise only check out the ones given)
- `--buy` or `-b` to specify buy items, which will be *additional* to the ones in the configuration
- `--vendor-items` or `-v` to specify vendor items *additional* to the ones in the configuration

Example, compute profit margins for only alchemy with buying Rune Etched Vial from the vendor:
```bash
$ python3 hogo auctions -u profit -p "Shadowlands Alchemy" -v "Rune Etched Vial"
```
results in:
```
[...]
Spectral Flask of Power: Price: 647.0g, 90.0s Costs: 625g, 3s Profit: -10.0g, 47.0s, 50.0b
    Rune Etched Vial: 50s * 1 (50s) from AH
    Nightshade: 37g, 11s * 3 (111g, 33s) from AH
    Rising Glory: 17g, 31s * 4 (69g, 24s) from AH
    Marrowroot: 43g, 44s * 4 (173g, 76s) from AH
    Widowbloom: 38g, 55s * 4 (154g, 20s) from AH
    Vigil's Torch: 29g * 4 (116g) from AH
Spectral Flask of Stamina: Price: 250.0g Costs: 219g, 86s Profit: 17.0g, 64.0s
    Rune Etched Vial: 50s * 1 (50s) from AH
    Nightshade: 37g, 11s * 1 (37g, 11s) from AH
    Rising Glory: 17g, 31s * 3 (51g, 93s) from AH
    Marrowroot: 43g, 44s * 3 (130g, 32s) from AH
Spiritual Healing Potion: Price: 10.0g, 41.0s Costs: 8g, 84s Profit: 1.0g, 4.0s, 95.0b
    Rune Etched Vial: 50s * 1 (50s) from AH
    Death Blossom: 4g, 17s * 2 (8g, 34s) from AH
Spiritual Mana Potion: Price: 9.0g, 49.0s Costs: 8g, 84s Profit: 17.0s, 55.0b
    Rune Etched Vial: 50s * 1 (50s) from AH
    Death Blossom: 4g, 17s * 2 (8g, 34s) from AH
[...]
```
As you can see Rune Etched Vial is currently cheaper in the AH then from the vendor.

You can also combine professions:
```bash
$ python3 hogo auctions -u profit -p "Shadowlands Enchanting" "Shadowlands Leatherworking"
```
Gives you (amongst others) the following:
```
Boneshatter Armguards (Rank 1): Price: 4590.0g Costs: 12857g Profit: -8497.0g, 50.0s
    Enchanted Heavy Callous Hide: 2014g, 76s * 3 (6044g, 28s) from Crafting: Enchanted Heavy Callous Hide
    Heavy Callous Hide: 999g, 90s * 3 (2999g, 70s) from Crafting: Heavy Callous Hide
    Heavy Desolate Leather: 23g, 40s * 8 (187g, 20s) from Crafting: Heavy Desolate Leather
    Pallid Bone: 2g, 59s * 10 (25g, 90s) from AH
    Orboreal Shard: 449g, 99s * 8 (3599g, 92s) from AH
```
As you can see `Enchanted Heavy Callous Hide` is cheaper to produce yourself then it is to buy from the AH.

For further information see the `--help` page of each (sub-)command