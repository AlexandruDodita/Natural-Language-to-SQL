CREATE TABLE Examination
(
    ID                 INTEGER          null,
    `Examination Date` DATE         null,
    `aCL IgG`          REAL        null,
    `aCL IgM`          REAL        null,
    ANA                INTEGER          null,
    `ANA Pattern`      TEXT null,
    `aCL IgA`          INTEGER          null,
    Diagnosis          TEXT null,
    KCT                TEXT null,
    RVVT              TEXT null,
    LAC                TEXT null,
    Symptoms           TEXT null,
    Thrombosis         INTEGER          null,
    foreign key (ID) references Patient (ID)
            on update cascade on delete cascade
);

-- Examination column meanings:
--   ID : identification of the patient
--   aCL IgG : anti-Cardiolipin antibody (IgG); anti-Cardiolipin antibody (IgG) concentration
--   aCL IgM : anti-Cardiolipin antibody (IgM); anti-Cardiolipin antibody (IgM) concentration
--   ANA : anti-nucleus antibody; anti-nucleus antibody concentration
--   ANA Pattern : pattern observed in the sheet of ANA examination
--   aCL IgA : anti-Cardiolipin antibody (IgA) concentration
--   Diagnosis : disease names
--   KCT : measure of degree of coagulation; +: positive -: negative
--   RVVT : measure of degree of coagulation; +: positive -: negative
--   LAC : measure of degree of coagulation; +: positive -: negative
--   Symptoms : other symptoms observed
--   Thrombosis : degree of thrombosis; 0: negative (no thrombosis) 1: positive (the most serious) 2: positive (severe)3: positive (mild)

CREATE TABLE Laboratory
(
    ID        INTEGER  default 0            not null,
    Date      DATE default '0000-00-00' not null,
    GOT       INTEGER                       null,
    GPT       INTEGER                        null,
    LDH       INTEGER                        null,
    ALP       INTEGER                        null,
    TP        REAL             null,
    ALB       REAL             null,
    UA        REAL             null,
    UN        INTEGER                       null,
    CRE       REAL             null,
    `T-BIL`   REAL             null,
    `T-CHO`   INTEGER                       null,
    TG        INTEGER                       null,
    CPK       INTEGER                       null,
    GLU       INTEGER                       null,
    WBC       REAL             null,
    RBC       REAL             null,
    HGB       REAL             null,
    HCT       REAL             null,
    PLT       INTEGER                       null,
    PT        REAL             null,
    APTT      INTEGER                       null,
    FG        REAL             null,
    PIC       INTEGER                       null,
    TAT       INTEGER                       null,
    TAT2      INTEGER                       null,
    `U-PRO`   TEXT              null,
    IGG       INTEGER                       null,
    IGA       INTEGER                       null,
    IGM       INTEGER                       null,
    CRP       TEXT              null,
    RA        TEXT              null,
    RF        TEXT              null,
    C3        INTEGER                       null,
    C4        INTEGER                       null,
    RNP       TEXT              null,
    SM        TEXT              null,
    SC170     TEXT              null,
    SSA       TEXT              null,
    SSB       TEXT              null,
    CENTROMEA TEXT              null,
    DNA       TEXT              null,
    `DNA-II`  INTEGER                       null,
    primary key (ID, Date),
        foreign key (ID) references Patient (ID)
            on update cascade on delete cascade
);

-- Laboratory column meanings:
--   ID : identification of the patient
--   Date : Date of the laboratory tests (YYMMDD)
--   GOT : AST glutamic oxaloacetic transaminase; Commonsense evidence: Normal range: N < 60
--   GPT : ALT glutamic pyruvic transaminase; Commonsense evidence: Normal range: N < 60
--   LDH : lactate dehydrogenase; Commonsense evidence: Normal range: N < 500
--   ALP : alkaliphophatase; Commonsense evidence: Normal range: N < 300
--   TP : total protein; Commonsense evidence: Normal range: 6.0 < N < 8.5
--   ALB : albumin; Commonsense evidence: Normal range: 3.5 < N < 5.5
--   UA : uric acid; Commonsense evidence: Normal range: N > 8.0 (Male)N > 6.5 (Female)
--   UN : urea nitrogen; Commonsense evidence: Normal range: N < 30
--   CRE : creatinine; Commonsense evidence: Normal range: N < 1.5
--   T-BIL : total bilirubin; Commonsense evidence: Normal range: N < 2.0
--   T-CHO : total cholesterol; Commonsense evidence: Normal range: N < 250
--   TG : triglyceride; Commonsense evidence: Normal range: N < 200
--   CPK : creatinine phosphokinase; Commonsense evidence: Normal range: N < 250
--   GLU : blood glucose; Commonsense evidence: Normal range: N < 180
--   WBC : White blood cell; Commonsense evidence: Normal range: 3.5 < N < 9.0
--   RBC : Red blood cell; Commonsense evidence: Normal range: 3.5 < N < 6.0
--   HGB : Hemoglobin; Commonsense evidence: Normal range: 10 < N < 17
--   HCT : Hematoclit; Commonsense evidence: Normal range: 29 < N < 52
--   PLT : platelet; Commonsense evidence: Normal range: 100 < N < 400
--   PT : prothrombin time; Commonsense evidence: Normal range: N < 14
--   APTT : activated partial prothrombin time; Commonsense evidence: Normal range: N < 45
--   FG : fibrinogen; Commonsense evidence: Normal range: 150 < N < 450
--   U-PRO : proteinuria; Commonsense evidence: Normal range: 0 < N < 30
--   IGG : Ig G; Commonsense evidence: Normal range: 900 < N < 2000
--   IGA : Ig A; Commonsense evidence: Normal range: 80 < N < 500
--   IGM : Ig M; Commonsense evidence: Normal range: 40 < N < 400
--   CRP : C-reactive protein; Commonsense evidence: Normal range: N= -, +-, or N < 1.0
--   RA : Rhuematoid Factor; Commonsense evidence: Normal range: N= -, +-
--   RF : RAHA; Commonsense evidence: Normal range: N < 20
--   C3 : complement 3; Commonsense evidence: Normal range: N > 35
--   C4 : complement 4; Commonsense evidence: Normal range: N > 10
--   RNP : anti-ribonuclear protein; Commonsense evidence: Normal range: N= -, +-
--   SM : anti-SM; Commonsense evidence: Normal range: N= -, +-
--   SC170 : anti-scl70; Commonsense evidence: Normal range: N= -, +-
--   SSA : anti-SSA; Commonsense evidence: Normal range: N= -, +-
--   SSB : anti-SSB; Commonsense evidence: Normal range: N= -, +-
--   CENTROMEA : anti-centromere; Commonsense evidence: Normal range: N= -, +-
--   DNA : anti-DNA; Commonsense evidence: Normal range: N < 8
--   DNA-II : anti-DNA; Commonsense evidence: Normal range: N < 8

CREATE TABLE Patient
(
    ID           INTEGER default 0 not null
        primary key,
    SEX          TEXT  null,
    Birthday     DATE          null,
    Description  DATE          null,
    `First Date` DATE          null,
    Admission    TEXT  null,
    Diagnosis    TEXT  null
);

-- Patient column meanings:
--   ID : identification of the patient
--   SEX : F: female; M: male
--   Description : the first date when a patient data was recorded; null or empty: not recorded
--   First Date : the date when a patient came to the hospital
--   Admission : patient was admitted to the hospital (+) or followed at the outpatient clinic (-)
--   Diagnosis : disease names
