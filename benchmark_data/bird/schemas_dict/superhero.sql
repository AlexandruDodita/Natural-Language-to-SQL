CREATE TABLE alignment
(
    id        INTEGER not null
            primary key,
    alignment TEXT default NULL
);

-- alignment column meanings:
--   id : the unique identifier of the alignment
--   alignment : the alignment of the superhero; commonsense evidence: Alignment refers to a character's moral and ethical stance and can be used to describe the overall attitude or behavior of a superhero. Some common alignments for superheroes include: Good: These superheroes are typically kind, selfless, and dedicated to protecting others and upholding justice. Examples of good alignments include Superman, Wonder Woman, and Spider-Man. Neutral: These superheroes may not always prioritize the greater good, but they are not necessarily evil either. They may act in their own self-interest or make decisions based on their own moral code. Examples of neutral alignments include the Hulk and Deadpool.  Bad: These superheroes are typically selfish, manipulative, and willing to harm others in pursuit of their own goals. Examples of evil alignments include Lex Luthor and the Joker.

CREATE TABLE attribute
(
    id             INTEGER not null
            primary key,
    attribute_name TEXT default NULL
);

-- attribute column meanings:
--   id : the unique identifier of the attribute
--   attribute_name : attribute name; the attribute; commonsense evidence: A superhero's attribute is a characteristic or quality that defines who they are and what they are capable of. This could be a physical trait, such as superhuman strength or the ability to fly, or a personal trait, such as extraordinary intelligence or exceptional bravery.

CREATE TABLE colour
(
    id     INTEGER not null
            primary key,
    colour TEXT default NULL
);

-- colour column meanings:
--   id : the unique identifier of the color
--   colour : the color of the superhero's skin/eye/hair/etc

CREATE TABLE gender
(
    id     INTEGER not null
            primary key,
    gender TEXT default NULL
);

-- gender column meanings:
--   id : the unique identifier of the gender
--   gender : the gender of the superhero

CREATE TABLE hero_attribute
(
    hero_id         INTEGER default NULL,
    attribute_id    INTEGER default NULL,
    attribute_value INTEGER default NULL,
    foreign key (attribute_id) references attribute(id),
    foreign key (hero_id) references superhero(id)
);

-- hero_attribute column meanings:
--   hero_id : hero id; the id of the hero Maps to superhero(id)
--   attribute_id : attribute id; the id of the attribute Maps to attribute(id)
--   attribute_value : attribute value; the attribute value; commonsense evidence: If a superhero has a higher attribute value on a particular attribute, it means that they are more skilled or powerful in that area compared to other superheroes. For example, if a superhero has a higher attribute value for strength, they may be able to lift heavier objects or deliver more powerful punches than other superheroes.

CREATE TABLE hero_power
(
    hero_id  INTEGER default NULL,
    power_id INTEGER default NULL,
    foreign key (hero_id) references superhero(id),
    foreign key (power_id) references superpower(id)
);

-- hero_power column meanings:
--   hero_id : hero id; the id of the hero Maps to superhero(id)
--   power_id : power id; the id of the power Maps to superpower(id); commonsense evidence: In general, a superhero's attributes provide the foundation for their abilities and help to define who they are, while their powers are the specific abilities that they use to fight crime and protect others.

CREATE TABLE publisher
(
    id             INTEGER not null
            primary key,
    publisher_name TEXT default NULL
);

-- publisher column meanings:
--   id : the unique identifier of the publisher
--   publisher_name : the name of the publisher

CREATE TABLE race
(
    id   INTEGER not null
            primary key,
    race TEXT default NULL
);

-- race column meanings:
--   id : the unique identifier of the race
--   race : the race of the superhero; commonsense evidence: In the context of superheroes, a superhero's race would refer to the particular group of people that the superhero belongs to base on these physical characteristics

CREATE TABLE superhero
(
    id             INTEGER not null
            primary key,
    superhero_name TEXT default NULL,
    full_name      TEXT default NULL,
    gender_id      INTEGER          default NULL,
    eye_colour_id  INTEGER          default NULL,
    hair_colour_id INTEGER          default NULL,
    skin_colour_id INTEGER          default NULL,
    race_id        INTEGER          default NULL,
    publisher_id   INTEGER          default NULL,
    alignment_id   INTEGER          default NULL,
    height_cm      INTEGER          default NULL,
    weight_kg      INTEGER          default NULL,
    foreign key (alignment_id) references alignment(id),
    foreign key (eye_colour_id) references colour(id),
    foreign key (gender_id) references gender(id),
    foreign key (hair_colour_id) references colour(id),
    foreign key (publisher_id) references publisher(id),
    foreign key (race_id) references race(id),
    foreign key (skin_colour_id) references colour(id)
);

-- superhero column meanings:
--   id : the unique identifier of the superhero
--   superhero_name : superhero name; the name of the superhero
--   full_name : full name; the full name of the superhero; commonsense evidence: The full name of a person typically consists of their given name, also known as their first name or personal name, and their surname, also known as their last name or family name. For example, if someone's given name is "John" and their surname is "Smith," their full name would be "John Smith."
--   gender_id : gender id; the id of the superhero's gender
--   eye_colour_id : eye colour id; the id of the superhero's eye color
--   hair_colour_id : hair colour id; the id of the superhero's hair color
--   skin_colour_id : skin colour id; the id of the superhero's skin color
--   race_id : race id; the id of the superhero's race
--   publisher_id : publisher id; the id of the publisher
--   alignment_id : alignment id; the id of the superhero's alignment
--   height_cm : height cm; the height of the superhero; commonsense evidence: The unit of height is centimeter. If the height_cm is NULL or 0, it means the height of the superhero is missing.
--   weight_kg : weight kg; the weight of the superhero; commonsense evidence: The unit of weight is kilogram. If the weight_kg is NULL or 0, it means the weight of the superhero is missing.

CREATE TABLE superpower
(
    id         INTEGER not null
            primary key,
    power_name TEXT default NULL
);

-- superpower column meanings:
--   id : the unique identifier of the superpower
--   power_name : power name; the superpower name
