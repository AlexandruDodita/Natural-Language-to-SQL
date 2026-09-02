CREATE TABLE circuits
(
    circuitId  INTEGER
        primary key autoincrement,
    circuitRef TEXT default '' not null,
    name       TEXT default '' not null,
    location   TEXT,
    country    TEXT,
    lat        REAL,
    lng        REAL,
    alt        INTEGER,
    url        TEXT default '' not null
        unique
);

-- circuits column meanings:
--   circuitId : circuit Id; unique identification number of the circuit
--   circuitRef : circuit reference name
--   name : full name of circuit
--   location : location of circuit
--   country : country of circuit
--   lat : latitude; latitude of location of circuit
--   lng : longitude; longitude of location of circuit; commonsense evidence: Location coordinates: (lat, lng)
--   alt : not useful

CREATE TABLE constructorResults
(
    constructorResultsId INTEGER
        primary key autoincrement,
    raceId               INTEGER default 0 not null,
    constructorId        INTEGER default 0 not null,
    points               REAL,
    status               TEXT,
    foreign key (raceId) references races(raceId),
    foreign key (constructorId) references constructors(constructorId)

);

-- constructorResults column meanings:
--   constructorResultsId : constructor Results Id
--   raceId : race Id
--   constructorId : constructor Id

CREATE TABLE constructorStandings
(
    constructorStandingsId INTEGER
        primary key autoincrement,
    raceId                 INTEGER default 0 not null,
    constructorId          INTEGER default 0 not null,
    points                 REAL   default 0 not null,
    position               INTEGER,
    positionText           TEXT,
    wins                   INTEGER default 0 not null,
    foreign key (raceId) references races(raceId),
    foreign key (constructorId) references constructors(constructorId)
);

-- constructorStandings column meanings:
--   constructorStandingsId : constructor Standings Id; unique identification of the constructor standing records
--   raceId : race id; id number identifying which races
--   constructorId : constructor id; id number identifying which id
--   points : how many points acquired in each race
--   position : position or track of circuits
--   positionText : position text; same with position, not quite useful

CREATE TABLE constructors
(
    constructorId  INTEGER
        primary key autoincrement,
    constructorRef TEXT default '' not null,
    name           TEXT default '' not null
        unique,
    nationality    TEXT,
    url            TEXT default '' not null
);

-- constructors column meanings:
--   constructorId : constructor Id; the unique identification number identifying constructors
--   constructorRef : Constructor Reference name
--   name : full name of the constructor
--   nationality : nationality of the constructor
--   url : the introduction website of the constructor; commonsense evidence: How to find out the detailed introduction of the constructor: through its url

CREATE TABLE driverStandings
(
    driverStandingsId INTEGER
        primary key autoincrement,
    raceId            INTEGER default 0 not null,
    driverId          INTEGER default 0 not null,
    points            REAL   default 0 not null,
    position          INTEGER,
    positionText      TEXT,
    wins              INTEGER default 0 not null,
    foreign key (raceId) references races(raceId),
    foreign key (driverId) references drivers(driverId)
);

-- driverStandings column meanings:
--   driverStandingsId : driver Standings Id; the unique identification number identifying driver standing records
--   raceId : constructor Reference name; id number identifying which races
--   driverId : id number identifying which drivers
--   points : how many points acquired in each race
--   position : position or track of circuits
--   positionText : position text; same with position, not quite useful

CREATE TABLE drivers
(
    driverId    INTEGER
        primary key autoincrement,
    driverRef   TEXT default '' not null,
    number      INTEGER,
    code        TEXT,
    forename    TEXT default '' not null,
    surname     TEXT default '' not null,
    dob         DATE,
    nationality TEXT,
    url         TEXT default '' not null
        unique
);

-- drivers column meanings:
--   driverId : driver ID; the unique identification number identifying each driver
--   driverRef : driver reference name
--   code : abbreviated code for drivers; if "null" or empty, it means it doesn't have code
--   dob : date of birth
--   nationality : nationality of drivers
--   url : the introduction website of the drivers

CREATE TABLE lapTimes
(
    raceId       INTEGER not null,
    driverId     INTEGER not null,
    lap          INTEGER not null,
    position     INTEGER,
    time         TEXT,
    milliseconds INTEGER,
    primary key (raceId, driverId, lap),
    foreign key (raceId) references races(raceId),
    foreign key (driverId) references drivers(driverId)
);

-- lapTimes column meanings:
--   raceId : race ID; the identification number identifying race
--   driverId : driver ID; the identification number identifying each driver
--   lap : lap number
--   position : position or track of circuits
--   time : lap time; in minutes / seconds / ...

CREATE TABLE pitStops
(
    raceId       INTEGER not null,
    driverId     INTEGER not null,
    stop         INTEGER not null,
    lap          INTEGER not null,
    time         TEXT    not null,
    duration     TEXT,
    milliseconds INTEGER,
    primary key (raceId, driverId, stop),
    foreign key (raceId) references races(raceId),
    foreign key (driverId) references drivers(driverId)
);

-- pitStops column meanings:
--   raceId : race ID; the identification number identifying race
--   driverId : driver ID; the identification number identifying each driver
--   stop : stop number
--   lap : lap number
--   time : exact time
--   duration : duration time; seconds/

CREATE TABLE qualifying
(
    qualifyId     INTEGER
        primary key autoincrement,
    raceId        INTEGER default 0 not null,
    driverId      INTEGER default 0 not null,
    constructorId INTEGER default 0 not null,
    number        INTEGER default 0 not null,
    position      INTEGER,
    q1            TEXT,
    q2            TEXT,
    q3            TEXT,
    foreign key (raceId) references races(raceId),
    foreign key (driverId) references drivers(driverId),
    foreign key (constructorId) references constructors(constructorId)
);

-- qualifying column meanings:
--   qualifyId : qualify Id; the unique identification number identifying qualifying; How does F1 Sprint qualifying work? Sprint qualifying is essentially a short-form Grand Prix – a race that is one-third the number of laps of the main event on Sunday. However, the drivers are battling for positions on the grid for the start of Sunday's race.
--   raceId : race Id; the identification number identifying each race
--   driverId : driver Id; the identification number identifying each driver
--   constructorId : constructor id
--   position : position or track of circuit
--   q1 : qualifying 1; time in qualifying 1; in minutes / seconds / ... commonsense evidence: Q1 lap times determine pole position and the order of the front 10 positions on the grid. The slowest driver in Q1 starts 10th, the next starts ninth and so on. All 20 F1 drivers participate in the first period, called Q1, with each trying to set the fastest time possible. Those in the top 15 move on to the next period of qualifying, called Q2. The five slowest drivers are eliminated and will start the race in the last five positions on the grid.
--   q2 : qualifying 2; time in qualifying 2; in minutes / seconds / ... commonsense evidence: only top 15 in the q1 has the record of q2 Q2 is slightly shorter but follows the same format. Drivers try to put down their best times to move on to Q1 as one of the 10 fastest cars. The five outside of the top 10 are eliminated and start the race from 11th to 15th based on their best lap time.
--   q3 : qualifying 3; time in qualifying 3; in minutes / seconds / ... commonsense evidence: only top 10 in the q2 has the record of q3

CREATE TABLE races
(
    raceId    INTEGER
        primary key autoincrement,
    year      INTEGER default 0            not null,
    round     INTEGER default 0            not null,
    circuitId INTEGER default 0            not null,
    name      TEXT    default ''           not null,
    date      DATE    default '0000-00-00' not null,
    time      TEXT,
    url       TEXT unique,
    foreign key (year) references seasons(year),
    foreign key (circuitId) references circuits(circuitId)
);

-- races column meanings:
--   raceId : race ID; the unique identification number identifying the race
--   circuitId : Circuit Id
--   name : name of the race
--   date : duration time
--   time : time of the location
--   url : introduction of races

CREATE TABLE results
(
    resultId        INTEGER
        primary key autoincrement,
    raceId          INTEGER default 0  not null,
    driverId        INTEGER default 0  not null,
    constructorId   INTEGER default 0  not null,
    number          INTEGER,
    grid            INTEGER default 0  not null,
    position        INTEGER,
    positionText    TEXT    default '' not null,
    positionOrder   INTEGER default 0  not null,
    points          REAL   default 0  not null,
    laps            INTEGER default 0  not null,
    time            TEXT,
    milliseconds    INTEGER,
    fastestLap      INTEGER,
    rank            INTEGER default 0,
    fastestLapTime  TEXT,
    fastestLapSpeed TEXT,
    statusId        INTEGER default 0  not null,
    foreign key (raceId) references races(raceId),
    foreign key (driverId) references drivers(driverId),
    foreign key (constructorId) references constructors(constructorId),
    foreign key (statusId) references status(statusId)
);

-- results column meanings:
--   resultId : Result ID; the unique identification number identifying race result
--   raceId : race ID; the identification number identifying the race
--   driverId : driver ID; the identification number identifying the driver
--   constructorId : constructor Id; the identification number identifying which constructors
--   grid : the number identifying the area where cars are set into a grid formation in order to start the race.
--   position : The finishing position or track of circuits
--   positionText : position text; not quite useful
--   positionOrder : position order; the finishing order of positions
--   laps : lap number
--   time : finish time; commonsense evidence: 1. if the value exists, it means the driver finished the race. 2. Only the time of the champion shows in the format of "minutes: seconds.millionsecond", the time of the other drivers shows as "seconds.millionsecond" , which means their actual time is the time of the champion adding the value in this cell.
--   milliseconds : the actual finishing time of drivers in milliseconds; the actual finishing time of drivers
--   fastestLap : fastest lap; fastest lap number
--   rank : starting rank positioned by fastest lap speed
--   fastestLapTime : fastest Lap Time; faster (smaller in the value) "fastestLapTime" leads to higher rank (smaller is higher rank)
--   fastestLapSpeed : fastest Lap Speed; (km / h)
--   statusId : status Id; its category description appear in the table status

CREATE TABLE seasons
(
    year INTEGER default 0  not null
        primary key,
    url  TEXT    default '' not null
        unique
);

-- seasons column meanings:
--   year : race ID; the unique identification number identifying the race
--   url : website link of season race introduction

CREATE TABLE status
(
    statusId INTEGER
        primary key autoincrement,
    status   TEXT default '' not null
);

-- status column meanings:
--   statusId : status ID; the unique identification number identifying status
--   status : full name of status
