CREATE TABLE `atom` (
  `atom_id` TEXT NOT NULL,
  `molecule_id` TEXT DEFAULT NULL,
  `element` TEXT DEFAULT NULL,
  PRIMARY KEY (`atom_id`),
  FOREIGN KEY (`molecule_id`) REFERENCES `molecule` (`molecule_id`)
);

-- atom column meanings:
--   atom_id : atom id; the unique id of atoms
--   molecule_id : molecule id; identifying the molecule to which the atom belongs; commonsense evidence: TRXXX_i represents ith atom of molecule TRXXX
--   element : the element of the toxicology;  cl: chlorine  c: carbon  h: hydrogen  o: oxygen  s: sulfur  n: nitrogen  p: phosphorus  na: sodium  br: bromine  f: fluorine  i: iodine  sn: Tin  pb: lead  te: tellurium  ca: Calcium

CREATE TABLE `bond` (
  `bond_id` TEXT NOT NULL,
  `molecule_id` TEXT DEFAULT NULL,
  `bond_type` TEXT DEFAULT NULL,
  PRIMARY KEY (`bond_id`),
  FOREIGN KEY (`molecule_id`) REFERENCES `molecule` (`molecule_id`)
);

-- bond column meanings:
--   bond_id : unique id representing bonds; TRxxx_A1_A2: TRXXX refers to which molecule A1 and A2 refers to which atom
--   molecule_id : identifying the molecule in which the bond appears
--   bond_type : type of the bond; commonsense evidence: -: single bond '=': double bond '#': triple bond

CREATE TABLE `connected` (
  `atom_id` TEXT NOT NULL,
  `atom_id2` TEXT NOT NULL,
  `bond_id` TEXT DEFAULT NULL,
  PRIMARY KEY (`atom_id`,`atom_id2`),
  FOREIGN KEY (`atom_id`) REFERENCES `atom` (`atom_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY (`atom_id2`) REFERENCES `atom` (`atom_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY (`bond_id`) REFERENCES `bond` (`bond_id`) ON DELETE CASCADE ON UPDATE CASCADE
);

-- connected column meanings:
--   atom_id : atom id; id of the first atom
--   atom_id2 : atom id 2; id of the second atom
--   bond_id : bond id; bond id representing bond between two atoms

CREATE TABLE `molecule` (
  `molecule_id` TEXT NOT NULL,
  `label` TEXT DEFAULT NULL,
  PRIMARY KEY (`molecule_id`)
);

-- molecule column meanings:
--   molecule_id : molecule id; unique id of molecule; "+" --> this molecule / compound is carcinogenic '-' this molecule is not / compound carcinogenic
--   label : whether this molecule is carcinogenic or not
