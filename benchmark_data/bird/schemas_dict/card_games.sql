CREATE TABLE "cards"
(
    id                      INTEGER           not null
        primary key autoincrement,
    artist                  TEXT,
    asciiName               TEXT,
    availability            TEXT,
    borderColor             TEXT,
    cardKingdomFoilId       TEXT,
    cardKingdomId           TEXT,
    colorIdentity           TEXT,
    colorIndicator          TEXT,
    colors                  TEXT,
    convertedManaCost       REAL,
    duelDeck                TEXT,
    edhrecRank              INTEGER,
    faceConvertedManaCost   REAL,
    faceName                TEXT,
    flavorName              TEXT,
    flavorText              TEXT,
    frameEffects            TEXT,
    frameVersion            TEXT,
    hand                    TEXT,
    hasAlternativeDeckLimit INTEGER default 0 not null,
    hasContentWarning       INTEGER default 0 not null,
    hasFoil                 INTEGER default 0 not null,
    hasNonFoil              INTEGER default 0 not null,
    isAlternative           INTEGER default 0 not null,
    isFullArt               INTEGER default 0 not null,
    isOnlineOnly            INTEGER default 0 not null,
    isOversized             INTEGER default 0 not null,
    isPromo                 INTEGER default 0 not null,
    isReprint               INTEGER default 0 not null,
    isReserved              INTEGER default 0 not null,
    isStarter               INTEGER default 0 not null,
    isStorySpotlight        INTEGER default 0 not null,
    isTextless              INTEGER default 0 not null,
    isTimeshifted           INTEGER default 0 not null,
    keywords                TEXT,
    layout                  TEXT,
    leadershipSkills        TEXT,
    life                    TEXT,
    loyalty                 TEXT,
    manaCost                TEXT,
    mcmId                   TEXT,
    mcmMetaId               TEXT,
    mtgArenaId              TEXT,
    mtgjsonV4Id             TEXT,
    mtgoFoilId              TEXT,
    mtgoId                  TEXT,
    multiverseId            TEXT,
    name                    TEXT,
    number                  TEXT,
    originalReleaseDate     TEXT,
    originalText            TEXT,
    originalType            TEXT,
    otherFaceIds            TEXT,
    power                   TEXT,
    printings               TEXT,
    promoTypes              TEXT,
    purchaseUrls            TEXT,
    rarity                  TEXT,
    scryfallId              TEXT,
    scryfallIllustrationId  TEXT,
    scryfallOracleId        TEXT,
    setCode                 TEXT,
    side                    TEXT,
    subtypes                TEXT,
    supertypes              TEXT,
    tcgplayerProductId      TEXT,
    text                    TEXT,
    toughness               TEXT,
    type                    TEXT,
    types                   TEXT,
    uuid                    TEXT              not null
        unique,
    variations              TEXT,
    watermark               TEXT
);

-- cards column meanings:
--   id : unique id number identifying the cards
--   artist : The name of the artist that illustrated the card art.
--   asciiName : ascii Name; The ASCII(opens new window) (Basic/128) code formatted card name with no special unicode characters.
--   availability : A list of the card's available printing types.; "arena", "dreamcast", "mtgo", "paper", "shandalar"
--   borderColor : border Color; The color of the card border.; "black", "borderless", "gold", "silver", "white"
--   cardKingdomFoilId : card Kingdom Foil Id; commonsense evidence: cardKingdomFoilId, when paired with cardKingdomId that is not Null, is incredibly powerful.
--   cardKingdomId : card Kingdom Id; A list of all the colors in the color indicator
--   colorIdentity : color Identity; A list of all the colors found in manaCost, colorIndicator, and text
--   colorIndicator : color Indicator; A list of all the colors in the color indicator (The symbol prefixed to a card's types).
--   colors : A list of all the colors in manaCost and colorIndicator.; Some cards may not have values, such as cards with "Devoid" in its text.
--   convertedManaCost : converted Mana Cost; The converted mana cost of the card. Use the manaValue property.; if value is higher, it means that this card cost more converted mana
--   duelDeck : duel Deck; The indicator for which duel deck the card is in.
--   edhrecRank : rec Rank in edh; The card rank on EDHRec
--   faceConvertedManaCost : face Converted Mana Cost; The converted mana cost or mana value for the face for either half or part of the card.; if value is higher, it means that this card cost more converted mana for the face
--   faceName : face Name; The name on the face of the card.
--   flavorName : flavor Name; The promotional card name printed above the true card name on special cards that has no game function.
--   flavorText : flavor Text; The italicized text found below the rules text that has no game function.
--   frameEffects : frame Effects; The visual frame effects.; "colorshifted", "companion", "compasslanddfc", "devoid", "draft", "etched", "extendedart", "fullart", "inverted", "legendary", "lesson", "miracle", "mooneldrazidfc", "nyxtouched", "originpwdfc", "showcase", "snow", "sunmoondfc", "textless", "tombstone", "waxingandwaningmoondfc"
--   frameVersion : frame Version; The version of the card frame style.; "1993", "1997", "2003", "2015", "future"
--   hand : The starting maximum hand size total modifier.; A + or - character precedes an integer. commonsense evidence: positive maximum hand size: +1, +2, .... negative maximum hand size: -1, .... neural maximum hand size: 0....
--   hasAlternativeDeckLimit : has Alternative Deck Limit; If the card allows a value other than 4 copies in a deck.; 0: disallow 1: allow
--   hasContentWarning : has Content Warning; If the card marked by Wizards of the Coast (opens new window) for having sensitive content. See this official article (opens new window) for more information.; 0: doesn't have 1: has sensitve content or Wizards of the Coast commonsense evidence: Cards with this property may have missing or degraded properties and values.
--   hasFoil : has Foil; If the card can be found in foil; 0: cannot be found 1: can be found
--   hasNonFoil : has Non Foil; If the card can be found in non-foil; 0: cannot be found 1: can be found
--   isAlternative : is Alternative; If the card is an alternate variation to an original printing; 0: is not 1: is
--   isFullArt : is Full Art; If the card has full artwork.; 0: doesn't have, 1: has full artwork
--   isOnlineOnly : is Online Only; If the card is only available in online game variations.; 0: is not 1: is
--   isOversized : is Oversized; If the card is oversized.; 0: is not 1: is
--   isPromo : is Promotion; If the card is a promotional printing.; 0: is not 1: is
--   isReprint : is Reprint; If the card has been reprinted.; 0: has not 1: has not been
--   isReserved : is Reserved; If the card is on the Magic: The Gathering Reserved List (opens new window); If the card is on the Magic, it will appear in The Gathering Reserved List
--   isStarter : is Starter; If the card is found in a starter deck such as Planeswalker/Brawl decks.; 0: is not 1: is
--   isStorySpotlight : is Story Spotlight; If the card is a Story Spotlight card.; 0: is not 1: is
--   isTextless : is Text less; If the card does not have a text box.; commonsense evidence: 0: has a text box; 1: doesn't have a text box;
--   isTimeshifted : is Time shifted; If the card is time shifted; commonsense evidence: If the card is "timeshifted", a feature of certain sets where a card will have a different frameVersion.
--   keywords : A list of keywords found on the card.
--   layout : The type of card layout. For a token card, this will be "token"
--   leadershipSkills : leadership Skills; A list of formats the card is legal to be a commander in
--   life : The starting life total modifier. A plus or minus character precedes an integer.
--   loyalty : The starting loyalty value of the card.; Used only on cards with "Planeswalker" in its types. empty means unkown
--   manaCost : mana Cost; The mana cost of the card wrapped in brackets for each value.; commonsense evidence: manaCost is unconverted mana cost
--   mcmId : NOT USEFUL
--   mcmMetaId : NOT USEFUL
--   mtgArenaId : NOT USEFUL
--   mtgjsonV4Id : NOT USEFUL
--   mtgoFoilId : NOT USEFUL
--   mtgoId : NOT USEFUL
--   multiverseId : NOT USEFUL
--   name : The name of the card.; Cards with multiple faces, like "Split" and "Meld" cards are given a delimiter.
--   number : The number of the card
--   originalReleaseDate : original Release Date; The original release date in ISO 8601(opens new window) format for a promotional card printed outside of a cycle window, such as Secret Lair Drop promotions.
--   originalText : original Text; The text on the card as originally printed.
--   originalType : original Type; The type of the card as originally printed. Includes any supertypes and subtypes.
--   otherFaceIds : other Face Ids; A list of card UUID's to this card's counterparts, such as transformed or melded faces.
--   power : The power of the card.; commonsense evidence: ∞ means infinite power null or * refers to unknown power
--   printings : A list of set printing codes the card was printed in, formatted in uppercase.
--   promoTypes : promo Types; A list of promotional types for a card.; "arenaleague", "boosterfun", "boxtopper", "brawldeck", "bundle", "buyabox", "convention", "datestamped", "draculaseries", "draftweekend", "duels", "event", "fnm", "gameday", "gateway", "giftbox", "gilded", "godzillaseries", "instore", "intropack", "jpwalker", "judgegift", "league", "mediainsert", "neonink", "openhouse", "planeswalkerstamped", "playerrewards", "playpromo", "premiereshop", "prerelease", "promopack", "release", "setpromo", "stamped", "textured", "themepack", "thick", "tourney", "wizardsplaynetwork"
--   purchaseUrls : purchase Urls; Links that navigate to websites where the card can be purchased.
--   rarity : The card printing rarity.
--   scryfallId : NOT USEFUL
--   scryfallIllustrationId : NOT USEFUL
--   scryfallOracleId : NOT USEFUL
--   setCode : Set Code; The set printing code that the card is from.
--   side : The identifier of the card side.; Used on cards with multiple faces on the same card. commonsense evidence: if this value is empty, then it means this card doesn't have multiple faces on the same card.
--   subtypes : A list of card subtypes found after em-dash.
--   supertypes : super types; A list of card supertypes found before em-dash.; commonsense evidence: list of all types should be the union of subtypes and supertypes
--   tcgplayerProductId : tcg player ProductId
--   text : The rules text of the card.
--   toughness : The toughness of the card.
--   type : The type of the card as visible, including any supertypes and subtypes.; "Artifact", "Card", "Conspiracy", "Creature", "Dragon", "Dungeon", "Eaturecray", "Elemental", "Elite", "Emblem", "Enchantment", "Ever", "Goblin", "Hero", "Instant", "Jaguar", "Knights", "Land", "Phenomenon", "Plane", "Planeswalker", "Scariest", "Scheme", "See", "Sorcery", "Sticker", "Summon", "Token", "Tribal", "Vanguard", "Wolf", "You’ll", "instant"
--   types : A list of all card types of the card, including Un‑sets and gameplay variants.
--   uuid : The universal unique identifier (v5) generated by MTGJSON. Each entry is unique.; NOT USEFUL
--   watermark : The name of the watermark on the card.

CREATE TABLE "foreign_data"
(
    id           INTEGER not null
        primary key autoincrement,
    flavorText   TEXT,
    language     TEXT,
    multiverseid INTEGER,
    name         TEXT,
    text         TEXT,
    type         TEXT,
    uuid         TEXT
        references cards (uuid)
);

-- foreign_data column meanings:
--   id : unique id number identifying this row of data
--   flavorText : flavor Text; The foreign flavor text of the card.
--   language : The foreign language of card.
--   multiverseid : The foreign multiverse identifier of the card.
--   name : The foreign name of the card.
--   text : The foreign text ruling of the card.
--   type : The foreign type of the card. Includes any supertypes and subtypes.

CREATE TABLE "legalities"
(
    id     INTEGER not null
        primary key autoincrement,
    format TEXT,
    status TEXT,
    uuid   TEXT
        references cards (uuid)
            on update cascade on delete cascade
);

-- legalities column meanings:
--   id : unique id identifying this legality
--   format : format of play; each value refers to different rules to play
--   status : • legal • banned • restricted

CREATE TABLE "rulings"
(
    id   INTEGER not null
        primary key autoincrement,
    date DATE,
    text TEXT,
    uuid TEXT
        references cards (uuid)
            on update cascade on delete cascade
);

-- rulings column meanings:
--   id : unique id identifying this ruling
--   text : description about this ruling

CREATE TABLE "set_translations"
(
    id          INTEGER not null
        primary key autoincrement,
    language    TEXT,
    setCode     TEXT
        references sets (code)
            on update cascade on delete cascade,
    translation TEXT
);

-- set_translations column meanings:
--   id : unique id identifying this set
--   language : language of this card set
--   setCode : set code; the set code for this set
--   translation : translation of this card set

CREATE TABLE "sets"
(
    id               INTEGER           not null
        primary key autoincrement,
    baseSetSize      INTEGER,
    block            TEXT,
    booster          TEXT,
    code             TEXT              not null
        unique,
    isFoilOnly       INTEGER default 0 not null,
    isForeignOnly    INTEGER default 0 not null,
    isNonFoilOnly    INTEGER default 0 not null,
    isOnlineOnly     INTEGER default 0 not null,
    isPartialPreview INTEGER default 0 not null,
    keyruneCode      TEXT,
    mcmId            INTEGER,
    mcmIdExtras      INTEGER,
    mcmName          TEXT,
    mtgoCode         TEXT,
    name             TEXT,
    parentCode       TEXT,
    releaseDate      DATE,
    tcgplayerGroupId INTEGER,
    totalSetSize     INTEGER,
    type             TEXT
);

-- sets column meanings:
--   id : unique id identifying this set
--   baseSetSize : base Set Size; The number of cards in the set.
--   block : The block name the set was in.
--   booster : A breakdown of possibilities and weights of cards in a booster pack.
--   code : The set code for the set.
--   isFoilOnly : is Foil Only; If the set is only available in foil.
--   isForeignOnly : is Foreign Only; If the set is available only outside the United States of America.
--   isNonFoilOnly : is Non Foil Only; If the set is only available in non-foil.
--   isOnlineOnly : is Online Only; If the set is only available in online game variations.
--   isPartialPreview : is Partial Preview; If the set is still in preview (spoiled). Preview sets do not have complete data.
--   keyruneCode : keyrune Code; The matching Keyrune code for set image icons.
--   mcmId : magic card market id; The Magic Card Marketset identifier.
--   mcmIdExtras : magic card market ID Extras; The split Magic Card Market set identifier if a set is printed in two sets. This identifier represents the second set's identifier.
--   mcmName : magic card market name
--   mtgoCode : magic the gathering online code; The set code for the set as it appears on Magic: The Gathering Online; commonsense evidence: if the value is null or empty, then it doesn't appear on Magic: The Gathering Online
--   name : The name of the set.
--   parentCode : parent Code; The parent set code for set variations like promotions, guild kits, etc.
--   releaseDate : release Date; The release date in ISO 8601 format for the set.
--   tcgplayerGroupId : tcg player Group Id; The group identifier of the set on TCGplayer
--   totalSetSize : total Set Size; The total number of cards in the set, including promotional and related supplemental products but excluding Alchemy modifications - however those cards are included in the set itself.
--   type : The expansion type of the set.; "alchemy", "archenemy", "arsenal", "box", "commander", "core", "draft_innovation", "duel_deck", "expansion", "from_the_vault", "funny", "masterpiece", "masters", "memorabilia", "planechase", "premium_deck", "promo", "spellbook", "starter", "token", "treasure_chest", "vanguard"
