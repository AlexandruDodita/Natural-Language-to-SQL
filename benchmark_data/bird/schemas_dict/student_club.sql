CREATE TABLE "attendance"
(
    link_to_event  TEXT,
    link_to_member TEXT,
    primary key (link_to_event, link_to_member),
    foreign key (link_to_event) references event(event_id),
    foreign key (link_to_member) references member(member_id)
);

-- attendance column meanings:
--   link_to_event : link to event; The unique identifier of the event which was attended; References the Event table
--   link_to_member : link to member; The unique identifier of the member who attended the event; References the Member table

CREATE TABLE "budget"
(
    budget_id     TEXT
            primary key,
    category      TEXT,
    spent         REAL,
    remaining     REAL,
    amount        INTEGER,
    event_status  TEXT,
    link_to_event TEXT,
    foreign key (link_to_event) references event(event_id)
);

-- budget column meanings:
--   budget_id : budget id; A unique identifier for the budget entry
--   category : The area for which the amount is budgeted, such as, advertisement, food, parking
--   spent : The total amount spent in the budgeted category for an event.; the unit is dollar. This is summarized from the Expense table
--   remaining : A value calculated as the amount budgeted minus the amount spent; the unit is dollar commonsense evidence: If the remaining < 0, it means that the cost has exceeded the budget.
--   amount : The amount budgeted for the specified category and event; the unit is dollar commonsense evidence: some computation like: amount = spent + remaining
--   event_status : event status; the status of the event; Closed / Open/ Planning commonsense evidence: • Closed: It means that the event is closed. The spent and the remaining won't change anymore. • Open: It means that the event is already opened. The spent and the remaining will change with new expenses. • Planning: The event is not started yet but is planning. The spent and the remaining won't change at this stage.
--   link_to_event : link to event; The unique identifier of the event to which the budget line applies.; References the Event table

CREATE TABLE event
(
    event_id   TEXT
        constraint event_pk
            primary key,
    event_name TEXT,
    event_date TEXT,
    type       TEXT,
    notes      TEXT,
    location   TEXT,
    status     TEXT
);

-- event column meanings:
--   event_id : event id; A unique identifier for the event
--   event_name : event name
--   event_date : event date; The date the event took place or is scheduled to take place; e.g. 2020-03-10T12:00:00
--   type : The kind of event, such as game, social, election
--   notes : A free text field for any notes about the event
--   location : Address where the event was held or is to be held or the name of such a location
--   status : One of three values indicating if the event is in planning, is opened, or is closed; Open/ Closed/ Planning

CREATE TABLE "expense"
(
    expense_id          TEXT
            primary key,
    expense_description TEXT,
    expense_date        TEXT,
    cost                REAL,
    approved            TEXT,
    link_to_member      TEXT,
    link_to_budget      TEXT,
    foreign key (link_to_budget) references budget(budget_id),
    foreign key (link_to_member) references member(member_id)
);

-- expense column meanings:
--   expense_id : expense id; unique id of income
--   expense_description : expense description; A textual description of what the money was spend for
--   expense_date : expense date; The date the expense was incurred; e.g. YYYY-MM-DD
--   cost : The dollar amount of the expense; the unit is dollar
--   approved : A true or false value indicating if the expense was approved; true/ false
--   link_to_member : link to member; The member who incurred the expense
--   link_to_budget : link to budget; The unique identifier of the record in the Budget table that indicates the expected total expenditure for a given category and event.; References the Budget table

CREATE TABLE "income"
(
    income_id      TEXT
        constraint income_pk
            primary key,
    date_received  TEXT,
    amount         INTEGER,
    source         TEXT,
    notes          TEXT,
    link_to_member TEXT,
    foreign key (link_to_member) references member(member_id)
);

-- income column meanings:
--   income_id : income id; A unique identifier for each record of income
--   date_received : date received; the date that the fund received
--   amount : amount of funds; the unit is dollar
--   source : A value indicating where the funds come from such as dues, or the annual university allocation
--   notes : A free-text value giving any needed details about the receipt of funds
--   link_to_member : link to member

CREATE TABLE major
(
    major_id   TEXT
        constraint major_pk
            primary key,
    major_name TEXT,
    department TEXT,
    college    TEXT
);

-- major column meanings:
--   major_id : major id; A unique identifier for each major
--   major_name : major name
--   department : The name of the department that offers the major
--   college : The name college that houses the department that offers the major

CREATE TABLE "member"
(
    member_id     TEXT
        constraint member_pk
            primary key,
    first_name    TEXT,
    last_name     TEXT,
    email         TEXT,
    position      TEXT,
    t_shirt_size  TEXT,
    phone         TEXT,
    zip           INTEGER,
    link_to_major TEXT,
    foreign key (link_to_major) references major(major_id),
    foreign key (zip) references zip_code(zip_code)
);

-- member column meanings:
--   member_id : member id; unique id of member
--   first_name : first name; member's first name
--   last_name : last name; member's last name; commonsense evidence: full name is first_name + last_name. e.g. A member's first name is Angela and last name is Sanders. Thus, his/her full name is Angela Sanders.
--   email : member's email
--   position : The position the member holds in the club
--   t_shirt_size : The size of tee shirt that member wants when shirts are ordered; commonsense evidence: usually the student ordered t-shirt with lager size has bigger body shape
--   phone : The best telephone at which to contact the member
--   zip : the zip code of the member's hometown
--   link_to_major : link to major; The unique identifier of the major of the member. References the Major table

CREATE TABLE zip_code
(
    zip_code    INTEGER
        constraint zip_code_pk
            primary key,
    type        TEXT,
    city        TEXT,
    county      TEXT,
    state       TEXT,
    short_state TEXT
);

-- zip_code column meanings:
--   zip_code : zip code; The ZIP code itself. A five-digit number identifying a US post office.
--   type : The kind of ZIP code; commonsense evidence: � Standard: the normal codes with which most people are familiar � PO Box: zip codes have post office boxes � Unique: zip codes that are assigned to individual organizations.
--   city : The city to which the ZIP pertains
--   county : The county to which the ZIP pertains
--   state : The name of the state to which the ZIP pertains
--   short_state : short state; The abbreviation of the state to which the ZIP pertains
