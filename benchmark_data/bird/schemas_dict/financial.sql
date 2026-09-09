CREATE TABLE account
(
    account_id  INTEGER default 0 not null
        primary key,
    district_id INTEGER default 0 not null,
    frequency   TEXT   not null,
    date        DATE          not null,
    foreign key (district_id) references district (district_id)
);

-- account column meanings:
--   account_id : account id; the id of the account
--   district_id : location of branch
--   frequency : frequency of the acount
--   date : the creation date of the account; in the form YYMMDD

CREATE TABLE card
(
    card_id INTEGER default 0 not null
        primary key,
    disp_id INTEGER           not null,
    type    TEXT    not null,
    issued  DATE          not null,
    foreign key (disp_id) references disp (disp_id)
);

-- card column meanings:
--   card_id : credit card id; id number of credit card
--   disp_id : disposition id
--   type : type of credit card; "junior": junior class of credit card; "classic": standard class of credit card; "gold": high-level credit card
--   issued : the date when the credit card issued; in the form YYMMDD

CREATE TABLE client
(
    client_id   INTEGER        not null
        primary key,
    gender      TEXT not null,
    birth_date  DATE       not null,
    district_id INTEGER        not null,
    foreign key (district_id) references district (district_id)
);

-- client column meanings:
--   client_id : the unique number
--   gender : F：female M：male
--   birth_date : birth date
--   district_id : location of branch

CREATE TABLE disp
(
    disp_id    INTEGER        not null
        primary key,
    client_id  INTEGER        not null,
    account_id INTEGER        not null,
    type      TEXT not null,
    foreign key (account_id) references account (account_id),
    foreign key (client_id) references client (client_id)
);

-- disp column meanings:
--   disp_id : disposition id; unique number of identifying this row of record
--   client_id : id number of client
--   account_id : id number of account
--   type : type of disposition; "OWNER" : "USER" : "DISPONENT" commonsense evidence: the account can only have the right to issue permanent orders or apply for loans

CREATE TABLE district
(
    district_id INTEGER default 0 not null
        primary key,
    A2          TEXT   not null,
    A3          TEXT   not null,
    A4          TEXT       not null,
    A5          TEXT           not null,
    A6          TEXT           not null,
    A7          TEXT           not null,
    A8          INTEGER        not null,
    A9          INTEGER           not null,
    A10         REAL not null,
    A11         INTEGER           not null,
    A12         REAL null,
    A13         REAL not null,
    A14         INTEGER           not null,
    A15         INTEGER        null,
    A16         INTEGER          not null
);

-- district column meanings:
--   district_id : location of branch
--   A2 : district_name
--   A3 : region
--   A4 : number of inhabitants
--   A5 : no. of municipalities with inhabitants < 499; municipality < district < region
--   A6 : no. of municipalities with inhabitants 500-1999; municipality < district < region
--   A7 : no. of municipalities with inhabitants 2000-9999; municipality < district < region
--   A8 : no. of municipalities with inhabitants > 10000; municipality < district < region
--   A9 : not useful
--   A10 : ratio of urban inhabitants
--   A11 : average salary
--   A12 : unemployment rate 1995
--   A13 : unemployment rate 1996
--   A14 : no. of entrepreneurs per 1000 inhabitants
--   A15 : no. of committed crimes 1995
--   A16 : no. of committed crimes 1996

CREATE TABLE loan
(
    loan_id    INTEGER default 0 not null
        primary key,
    account_id INTEGER           not null,
    date       DATE          not null,
    amount     INTEGER           not null,
    duration   INTEGER           not null,
    payments   REAL not null,
    status     TEXT    not null,
    foreign key (account_id) references account (account_id)
);

-- loan column meanings:
--   loan_id : the id number identifying the loan data
--   account_id : the id number identifying the account
--   date : the date when the loan is approved
--   amount : approved amount; unit：US dollar
--   duration : loan duration; unit：month
--   payments : monthly payments; unit：month
--   status : repayment status; 'A' stands for contract finished, no problems; 'B' stands for contract finished, loan not paid; 'C' stands for running contract, OK so far; 'D' stands for running contract, client in debt

CREATE TABLE `order`
(
    order_id   INTEGER default 0 not null
        primary key,
    account_id INTEGER           not null,
    bank_to    TEXT    not null,
    account_to INTEGER           not null,
    amount     REAL not null,
    k_symbol   TEXT    not null,
    foreign key (account_id) references account (account_id)
);

-- order column meanings:
--   order_id : identifying the unique order
--   account_id : id number of account
--   bank_to : bank of the recipient
--   account_to : account of the recipient; each bank has unique two-letter code
--   amount : debited amount
--   k_symbol : characterization of the payment; purpose of the payment; "POJISTNE" stands for insurance payment "SIPO" stands for household payment "LEASING" stands for leasing "UVER" stands for loan payment

CREATE TABLE trans
(
    trans_id   INTEGER default 0    not null
        primary key,
    account_id INTEGER default 0    not null,
    date       DATE             not null,
    type       TEXT       not null,
    operation  TEXT      null,
    amount     INTEGER              not null,
    balance    INTEGER             not null,
    k_symbol   TEXT      null,
    bank       TEXT       null,
    account    INTEGER          null,
    foreign key (account_id) references account (account_id)
);

-- trans column meanings:
--   trans_id : transaction id
--   date : date of transaction
--   type : +/- transaction; "PRIJEM" stands for credit "VYDAJ" stands for withdrawal
--   operation : mode of transaction; "VYBER KARTOU": credit card withdrawal "VKLAD": credit in cash "PREVOD Z UCTU" :collection from another bank "VYBER": withdrawal in cash "PREVOD NA UCET": remittance to another bank
--   amount : amount of money; Unit：USD
--   balance : balance after transaction; Unit：USD
--   k_symbol : characterization of the transaction; "POJISTNE": stands for insurrance payment "SLUZBY": stands for payment for statement "UROK": stands for interest credited "SANKC. UROK": sanction interest if negative balance "SIPO": stands for household "DUCHOD": stands for old-age pension "UVER": stands for loan payment
--   bank : bank of the partner; each bank has unique two-letter code
--   account : account of the partner
