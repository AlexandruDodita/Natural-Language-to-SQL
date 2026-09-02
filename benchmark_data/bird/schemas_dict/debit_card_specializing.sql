CREATE TABLE customers
(
    CustomerID INTEGER UNIQUE     not null
        primary key,
    Segment    TEXT null,
    Currency   TEXT null
);

-- customers column meanings:
--   CustomerID : identification of the customer
--   Segment : client segment

CREATE TABLE gasstations
(
    GasStationID INTEGER    UNIQUE   not null
        primary key,
    ChainID      INTEGER          null,
    Country      TEXT null,
    Segment      TEXT null
);

-- gasstations column meanings:
--   GasStationID : Gas Station ID
--   ChainID : Chain ID
--   Segment : chain segment

CREATE TABLE products
(
    ProductID   INTEGER   UNIQUE      not null
        primary key,
    Description TEXT null
);

-- products column meanings:
--   ProductID : Product ID

CREATE TABLE "transactions_1k"
(
    TransactionID INTEGER
        primary key autoincrement,
    Date          DATE,
    Time          TEXT,
    CustomerID    INTEGER,
    CardID        INTEGER,
    GasStationID  INTEGER,
    ProductID     INTEGER,
    Amount        INTEGER,
    Price         REAL
);

-- transactions_1k column meanings:
--   TransactionID : Transaction ID
--   CustomerID : Customer ID
--   CardID : Card ID
--   GasStationID : Gas Station ID
--   ProductID : Product ID
--   Price : commonsense evidence: total price = Amount x Price

CREATE TABLE "yearmonth"
(
    CustomerID  INTEGER not null
        references customers
            on update cascade on delete cascade
        references customers,
    Date        TEXT    not null,
    Consumption REAL,
    primary key (Date, CustomerID)
);

-- yearmonth column meanings:
--   CustomerID : Customer ID
