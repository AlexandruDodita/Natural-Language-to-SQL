CREATE TABLE `Country` (
	`id`	INTEGER PRIMARY KEY AUTOINCREMENT,
	`name`	TEXT UNIQUE
);

-- Country column meanings:
--   id : the unique id for countries
--   name : country name

CREATE TABLE `League` (
	`id`	INTEGER PRIMARY KEY AUTOINCREMENT,
	`country_id`	INTEGER,
	`name`	TEXT UNIQUE,
	FOREIGN KEY(`country_id`) REFERENCES `country`(`id`)
);

-- League column meanings:
--   id : the unique id for leagues
--   country_id : country id; the unique id for countries
--   name : league name

CREATE TABLE "Match"
(
    id               INTEGER
        primary key autoincrement,
    country_id       INTEGER
        references Country,
    league_id        INTEGER
        references League,
    season           TEXT,
    stage            INTEGER,
    date             TEXT,
    match_api_id     INTEGER
        unique,
    home_team_api_id INTEGER
        references Team (team_api_id),
    away_team_api_id INTEGER
        references Team (team_api_id),
    home_team_goal   INTEGER,
    away_team_goal   INTEGER,
    home_player_X1   INTEGER,
    home_player_X2   INTEGER,
    home_player_X3   INTEGER,
    home_player_X4   INTEGER,
    home_player_X5   INTEGER,
    home_player_X6   INTEGER,
    home_player_X7   INTEGER,
    home_player_X8   INTEGER,
    home_player_X9   INTEGER,
    home_player_X10  INTEGER,
    home_player_X11  INTEGER,
    away_player_X1   INTEGER,
    away_player_X2   INTEGER,
    away_player_X3   INTEGER,
    away_player_X4   INTEGER,
    away_player_X5   INTEGER,
    away_player_X6   INTEGER,
    away_player_X7   INTEGER,
    away_player_X8   INTEGER,
    away_player_X9   INTEGER,
    away_player_X10  INTEGER,
    away_player_X11  INTEGER,
    home_player_Y1   INTEGER,
    home_player_Y2   INTEGER,
    home_player_Y3   INTEGER,
    home_player_Y4   INTEGER,
    home_player_Y5   INTEGER,
    home_player_Y6   INTEGER,
    home_player_Y7   INTEGER,
    home_player_Y8   INTEGER,
    home_player_Y9   INTEGER,
    home_player_Y10  INTEGER,
    home_player_Y11  INTEGER,
    away_player_Y1   INTEGER,
    away_player_Y2   INTEGER,
    away_player_Y3   INTEGER,
    away_player_Y4   INTEGER,
    away_player_Y5   INTEGER,
    away_player_Y6   INTEGER,
    away_player_Y7   INTEGER,
    away_player_Y8   INTEGER,
    away_player_Y9   INTEGER,
    away_player_Y10  INTEGER,
    away_player_Y11  INTEGER,
    home_player_1    INTEGER
        references Player (player_api_id),
    home_player_2    INTEGER
        references Player (player_api_id),
    home_player_3    INTEGER
        references Player (player_api_id),
    home_player_4    INTEGER
        references Player (player_api_id),
    home_player_5    INTEGER
        references Player (player_api_id),
    home_player_6    INTEGER
        references Player (player_api_id),
    home_player_7    INTEGER
        references Player (player_api_id),
    home_player_8    INTEGER
        references Player (player_api_id),
    home_player_9    INTEGER
        references Player (player_api_id),
    home_player_10   INTEGER
        references Player (player_api_id),
    home_player_11   INTEGER
        references Player (player_api_id),
    away_player_1    INTEGER
        references Player (player_api_id),
    away_player_2    INTEGER
        references Player (player_api_id),
    away_player_3    INTEGER
        references Player (player_api_id),
    away_player_4    INTEGER
        references Player (player_api_id),
    away_player_5    INTEGER
        references Player (player_api_id),
    away_player_6    INTEGER
        references Player (player_api_id),
    away_player_7    INTEGER
        references Player (player_api_id),
    away_player_8    INTEGER
        references Player (player_api_id),
    away_player_9    INTEGER
        references Player (player_api_id),
    away_player_10   INTEGER
        references Player (player_api_id),
    away_player_11   INTEGER
        references Player (player_api_id),
    goal             TEXT,
    shoton           TEXT,
    shotoff          TEXT,
    foulcommit       TEXT,
    card             TEXT,
    "cross"          TEXT,
    corner           TEXT,
    possession       TEXT,
    B365H            REAL,
    B365D            REAL,
    B365A            REAL,
    BWH              REAL,
    BWD              REAL,
    BWA              REAL,
    IWH              REAL,
    IWD              REAL,
    IWA              REAL,
    LBH              REAL,
    LBD              REAL,
    LBA              REAL,
    PSH              REAL,
    PSD              REAL,
    PSA              REAL,
    WHH              REAL,
    WHD              REAL,
    WHA              REAL,
    SJH              REAL,
    SJD              REAL,
    SJA              REAL,
    VCH              REAL,
    VCD              REAL,
    VCA              REAL,
    GBH              REAL,
    GBD              REAL,
    GBA              REAL,
    BSH              REAL,
    BSD              REAL,
    BSA              REAL
);

-- Match column meanings:
--   id : the unique id for matches
--   country_id : country id
--   league_id : league id
--   season : the season of the match
--   stage : the stage of the match
--   date : the date of the match; e.g. 2008-08-17 00:00:00
--   match_api_id : match api id; the id of the match api
--   home_team_api_id : home team api id; the id of the home team api
--   away_team_api_id : away team api id; the id of the away team api
--   home_team_goal : home team goal; the goal of the home team
--   away_team_goal : away team goal; the goal of the away team
--   goal : the goal of the match
--   shoton : shot on; the shot on goal of the match; commonsense reasoning: A shot on goal is a shot that enters the goal or would have entered the goal if it had not been blocked by the goalkeeper or another defensive player.
--   shotoff : shot off; the shot off goal of the match, which is the opposite of shot on
--   foulcommit : foul commit; the fouls occurred in the match
--   card : the cards given in the match
--   cross : Balls sent into the opposition team's area from a wide position in the match
--   corner : Ball goes out of play for a corner kick in the match
--   possession : The duration from a player taking over the ball in the match

CREATE TABLE `Player` (
	`id`	INTEGER PRIMARY KEY AUTOINCREMENT,
	`player_api_id`	INTEGER UNIQUE,
	`player_name`	TEXT,
	`player_fifa_api_id`	INTEGER UNIQUE,
	`birthday`	TEXT,
	`height`	INTEGER,
	`weight`	INTEGER
);

-- Player column meanings:
--   id : the unique id for players
--   player_api_id : player api id; the id of the player api
--   player_name : player name
--   player_fifa_api_id : player federation international football association api id; the id of the player fifa api
--   birthday : the player's birthday; e.g. 1992-02-29 00:00:00 commonsense reasoning: Player A is older than player B means that A's birthday is earlier than B's
--   height : the player's height
--   weight : the player's weight

CREATE TABLE "Player_Attributes" (
	`id`	INTEGER PRIMARY KEY AUTOINCREMENT,
	`player_fifa_api_id`	INTEGER,
	`player_api_id`	INTEGER,
	`date`	TEXT,
	`overall_rating`	INTEGER,
	`potential`	INTEGER,
	`preferred_foot`	TEXT,
	`attacking_work_rate`	TEXT,
	`defensive_work_rate`	TEXT,
	`crossing`	INTEGER,
	`finishing`	INTEGER,
	`heading_accuracy`	INTEGER,
	`short_passing`	INTEGER,
	`volleys`	INTEGER,
	`dribbling`	INTEGER,
	`curve`	INTEGER,
	`free_kick_accuracy`	INTEGER,
	`long_passing`	INTEGER,
	`ball_control`	INTEGER,
	`acceleration`	INTEGER,
	`sprint_speed`	INTEGER,
	`agility`	INTEGER,
	`reactions`	INTEGER,
	`balance`	INTEGER,
	`shot_power`	INTEGER,
	`jumping`	INTEGER,
	`stamina`	INTEGER,
	`strength`	INTEGER,
	`long_shots`	INTEGER,
	`aggression`	INTEGER,
	`interceptions`	INTEGER,
	`positioning`	INTEGER,
	`vision`	INTEGER,
	`penalties`	INTEGER,
	`marking`	INTEGER,
	`standing_tackle`	INTEGER,
	`sliding_tackle`	INTEGER,
	`gk_diving`	INTEGER,
	`gk_handling`	INTEGER,
	`gk_kicking`	INTEGER,
	`gk_positioning`	INTEGER,
	`gk_reflexes`	INTEGER,
	FOREIGN KEY(`player_fifa_api_id`) REFERENCES `Player`(`player_fifa_api_id`),
	FOREIGN KEY(`player_api_id`) REFERENCES `Player`(`player_api_id`)
);

-- Player_Attributes column meanings:
--   id : the unique id for players
--   player_fifa_api_id : player federation international football association api id; the id of the player fifa api
--   player_api_id : player api id; the id of the player api
--   date : e.g. 2016-02-18 00:00:00
--   overall_rating : the overall rating of the player; commonsense reasoning: The rating is between 0-100 which is calculated by FIFA. Higher overall rating means the player has a stronger overall strength.
--   potential : potential of the player; commonsense reasoning: The potential score is between 0-100 which is calculated by FIFA. Higher potential score means that the player has more potential
--   preferred_foot : preferred foot; the player's preferred foot when attacking; right/ left
--   attacking_work_rate : attacking work rate; the player's attacking work rate; commonsense reasoning: • high: implies that the player is going to be in all of your attack moves • medium: implies that the player will select the attack actions he will join in • low: remain in his position while the team attacks
--   defensive_work_rate : the player's defensive work rate; commonsense reasoning: • high: remain in his position and defense while the team attacks • medium: implies that the player will select the defensive actions he will join in • low: implies that the player is going to be in all of your attack moves instead of defensing
--   crossing : the player's crossing score; commonsense reasoning: Cross is a long pass into the opponent's goal towards the header of sixth-yard teammate. The crossing score is between 0-100 which measures the tendency/frequency of crosses in the box. Higher potential score means that the player performs better in crossing actions.
--   finishing : the player's finishing rate; 0-100 which is calculated by FIFA
--   heading_accuracy : heading accuracy; the player's heading accuracy; 0-100 which is calculated by FIFA
--   short_passing : short passing; the player's short passing score; 0-100 which is calculated by FIFA
--   volleys : the player's volley score; 0-100 which is calculated by FIFA
--   dribbling : the player's dribbling score; 0-100 which is calculated by FIFA
--   curve : the player's curve score; 0-100 which is calculated by FIFA
--   free_kick_accuracy : free kick accuracy; the player's free kick accuracy; 0-100 which is calculated by FIFA
--   long_passing : long passing; the player's long passing score; 0-100 which is calculated by FIFA
--   ball_control : ball control; the player's ball control score; 0-100 which is calculated by FIFA
--   acceleration : the player's acceleration score; 0-100 which is calculated by FIFA
--   sprint_speed : sprint speed; the player's sprint speed; 0-100 which is calculated by FIFA
--   agility : the player's agility; 0-100 which is calculated by FIFA
--   reactions : the player's reactions score; 0-100 which is calculated by FIFA
--   balance : the player's balance score; 0-100 which is calculated by FIFA
--   shot_power : shot power; the player's shot power; 0-100 which is calculated by FIFA
--   jumping : the player's jumping score; 0-100 which is calculated by FIFA
--   stamina : the player's stamina score; 0-100 which is calculated by FIFA
--   strength : the player's strength score; 0-100 which is calculated by FIFA
--   long_shots : long shots; the player's long shots score; 0-100 which is calculated by FIFA
--   aggression : the player's aggression score; 0-100 which is calculated by FIFA
--   interceptions : the player's interceptions score; 0-100 which is calculated by FIFA
--   positioning : the player's positioning score; 0-100 which is calculated by FIFA
--   vision : the player's vision score; 0-100 which is calculated by FIFA
--   penalties : the player's penalties score; 0-100 which is calculated by FIFA
--   marking : the player's markingscore; 0-100 which is calculated by FIFA
--   standing_tackle : standing tackle; the player's standing tackle score; 0-100 which is calculated by FIFA
--   sliding_tackle : sliding tackle; the player's sliding tackle score; 0-100 which is calculated by FIFA
--   gk_diving : goalkeep diving; the player's goalkeep diving score; 0-100 which is calculated by FIFA
--   gk_handling : goalkeep handling; the player's goalkeep diving score; 0-100 which is calculated by FIFA
--   gk_kicking : goalkeep kicking; the player's goalkeep kicking score; 0-100 which is calculated by FIFA
--   gk_positioning : goalkeep positioning; the player's goalkeep positioning score; 0-100 which is calculated by FIFA
--   gk_reflexes : goalkeep reflexes; the player's goalkeep reflexes score; 0-100 which is calculated by FIFA

CREATE TABLE "Team" (
	`id`	INTEGER PRIMARY KEY AUTOINCREMENT,
	`team_api_id`	INTEGER UNIQUE,
	`team_fifa_api_id`	INTEGER,
	`team_long_name`	TEXT,
	`team_short_name`	TEXT
);

-- Team column meanings:
--   id : the unique id for teams
--   team_api_id : team api id; the id of the team api
--   team_fifa_api_id : team federation international football association api id; the id of the team fifa api
--   team_long_name : team long name; the team's long name
--   team_short_name : team short name; the team's short name

CREATE TABLE `Team_Attributes` (
	`id`	INTEGER PRIMARY KEY AUTOINCREMENT,
	`team_fifa_api_id`	INTEGER,
	`team_api_id`	INTEGER,
	`date`	TEXT,
	`buildUpPlaySpeed`	INTEGER,
	`buildUpPlaySpeedClass`	TEXT,
	`buildUpPlayDribbling`	INTEGER,
	`buildUpPlayDribblingClass`	TEXT,
	`buildUpPlayPassing`	INTEGER,
	`buildUpPlayPassingClass`	TEXT,
	`buildUpPlayPositioningClass`	TEXT,
	`chanceCreationPassing`	INTEGER,
	`chanceCreationPassingClass`	TEXT,
	`chanceCreationCrossing`	INTEGER,
	`chanceCreationCrossingClass`	TEXT,
	`chanceCreationShooting`	INTEGER,
	`chanceCreationShootingClass`	TEXT,
	`chanceCreationPositioningClass`	TEXT,
	`defencePressure`	INTEGER,
	`defencePressureClass`	TEXT,
	`defenceAggression`	INTEGER,
	`defenceAggressionClass`	TEXT,
	`defenceTeamWidth`	INTEGER,
	`defenceTeamWidthClass`	TEXT,
	`defenceDefenderLineClass`	TEXT,
	FOREIGN KEY(`team_fifa_api_id`) REFERENCES `Team`(`team_fifa_api_id`),
	FOREIGN KEY(`team_api_id`) REFERENCES `Team`(`team_api_id`)
);

-- Team_Attributes column meanings:
--   id : the unique id for teams
--   team_fifa_api_id : team federation international football association api id; the id of the team fifa api
--   team_api_id : team api id; the id of the team api
--   date : e.g. 2010-02-22 00:00:00
--   buildUpPlaySpeed : build Up Play Speed; the speed in which attacks are put together; the score which is between 1-00 to measure the team's attack speed
--   buildUpPlaySpeedClass : build Up Play Speed Class; the speed class; commonsense reasoning: • Slow: 1-33 • Balanced: 34-66 • Fast: 66-100
--   buildUpPlayDribbling : build Up Play Dribbling; the tendency/ frequency of dribbling
--   buildUpPlayDribblingClass : build Up Play Dribbling Class; the dribbling class; commonsense reasoning: • Little: 1-33 • Normal: 34-66 • Lots: 66-100
--   buildUpPlayPassing : build Up Play Passing; affects passing distance and support from teammates
--   buildUpPlayPassingClass : build Up Play Passing Class; the passing class; commonsense reasoning: • Short: 1-33 • Mixed: 34-66 • Long: 66-100
--   buildUpPlayPositioningClass : build Up Play Positioning Class; A team's freedom of movement in the 1st two thirds of the pitch; Organised / Free Form
--   chanceCreationPassing : chance Creation Passing; Amount of risk in pass decision and run support
--   chanceCreationPassingClass : chance Creation Passing Class; the chance creation passing class; commonsense reasoning: • Safe: 1-33 • Normal: 34-66 • Risky: 66-100
--   chanceCreationCrossing : chance Creation Crossing; The tendency / frequency of crosses into the box
--   chanceCreationCrossingClass : chance Creation Crossing Class; the chance creation crossing class; commonsense reasoning: • Little: 1-33 • Normal: 34-66 • Lots: 66-100
--   chanceCreationShooting : chance Creation Shooting; The tendency / frequency of shots taken
--   chanceCreationShootingClass : chance Creation Shooting Class; the chance creation shooting class; commonsense reasoning: • Little: 1-33 • Normal: 34-66 • Lots: 66-100
--   chanceCreationPositioningClass : chance Creation Positioning Class; A team’s freedom of movement in the final third of the pitch; Organised / Free Form
--   defencePressure : defence Pressure; Affects how high up the pitch the team will start pressuring
--   defencePressureClass : defence Pressure Class; the defence pressure class; commonsense reasoning: • Deep: 1-33 • Medium: 34-66 • High: 66-100
--   defenceAggression : defence Aggression; Affect the team’s approach to tackling the ball possessor
--   defenceAggressionClass : defence Aggression Class; the defence aggression class; commonsense reasoning: • Contain: 1-33 • Press: 34-66 • Double: 66-100
--   defenceTeamWidth : defence Team Width; Affects how much the team will shift to the ball side
--   defenceTeamWidthClass : defence Team Width Class; the defence team width class; commonsense reasoning: • Narrow: 1-33 • Normal: 34-66 • Wide: 66-100
--   defenceDefenderLineClass : defence Defender Line Class; Affects the shape and strategy of the defence; Cover/ Offside Trap
