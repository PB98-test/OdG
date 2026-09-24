-- Struttura del database di OdG.
-- Ogni tabella usa "IF NOT EXISTS": lo schema viene rieseguito a ogni avvio
-- e crea solo quello che manca. Così, quando nelle prossime tappe aggiungeremo
-- tabelle nuove (persone, ruoli, proposte...), basterà scriverle qui sotto:
-- il database esistente le riceverà senza perdere nulla.

-- Un "tipo di riunione": Équipe Giovani, Consiglio diocesano...
CREATE TABLE IF NOT EXISTS tipi_riunione (
    id              INTEGER PRIMARY KEY,
    codice          TEXT NOT NULL UNIQUE,      -- parte casuale del link: /t/<codice>
    nome            TEXT NOT NULL,             -- "Équipe Giovani"
    sottotitolo     TEXT,                      -- "Settore Giovani" (riga gialla sopra il nome)
    luogo_abituale  TEXT,                      -- proposto quando si crea una riunione
    ora_abituale    TEXT,                      -- "21:00"
    durata_abituale INTEGER NOT NULL DEFAULT 90,   -- minuti
    archiviato      INTEGER NOT NULL DEFAULT 0,    -- 1 = non compare più in Home
    creato_il       TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Una singola riunione di un tipo.
CREATE TABLE IF NOT EXISTS riunioni (
    id          INTEGER PRIMARY KEY,
    tipo_id     INTEGER NOT NULL REFERENCES tipi_riunione(id) ON DELETE CASCADE,
    codice      TEXT NOT NULL UNIQUE,          -- parte casuale del link: /r/<codice>
    data        TEXT NOT NULL,                 -- "2026-10-08"
    ora_inizio  TEXT NOT NULL,                 -- "21:00"
    ora_fine    TEXT,                          -- facoltativa: se manca si usa la durata del tipo
    luogo       TEXT,
    link_online TEXT,                          -- es. Meet/Zoom, se la riunione è (anche) online
    note        TEXT,                          -- avvisi brevi: "portare il bilancio stampato"
    stato       TEXT NOT NULL DEFAULT 'in_programma'
                CHECK (stato IN ('in_programma', 'in_corso', 'conclusa')),
    -- Cambia a ogni modifica: finisce nel link dell'immagine di anteprima,
    -- così chi condivide dopo una modifica non riceve l'immagine vecchia.
    modificata_il TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_riunioni_tipo_data ON riunioni(tipo_id, data);

-- Un punto dell'ordine del giorno.
CREATE TABLE IF NOT EXISTS punti (
    id           INTEGER PRIMARY KEY,
    riunione_id  INTEGER NOT NULL REFERENCES riunioni(id) ON DELETE CASCADE,
    ordine       INTEGER NOT NULL,             -- posizione nell'elenco (1, 2, 3...)
    titolo       TEXT NOT NULL,
    minuti       INTEGER NOT NULL DEFAULT 10,  -- durata prevista
    -- Colonne già pronte per le tappe successive (spunte, timer, verbale,
    -- spostamento alla riunione dopo): per ora restano vuote.
    spuntato_il  TEXT,
    minuti_effettivi INTEGER,
    decisioni    TEXT,
    spostato_da  INTEGER REFERENCES punti(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_punti_riunione ON punti(riunione_id, ordine);
-- (La colonna punti.proposto_da, aggiunta nella tappa 3, la crea database.py:
--  "CREATE TABLE IF NOT EXISTS" non aggiunge colonne a una tabella che esiste già.)


-- ======================================================== tappa 3: persone e ruoli

-- Un ruolo e i suoi permessi (1 = concesso). Proporre, spuntare e usare il
-- timer sono aperti a tutti, quindi non compaiono qui.
CREATE TABLE IF NOT EXISTS ruoli (
    id            INTEGER PRIMARY KEY,
    nome          TEXT NOT NULL,
    perm_riunioni INTEGER NOT NULL DEFAULT 0,  -- crea e modifica riunioni e tipi
    perm_odg      INTEGER NOT NULL DEFAULT 0,  -- modifica l'OdG direttamente, approva le proposte
    perm_conclude INTEGER NOT NULL DEFAULT 0,  -- conclude la riunione (tappa 4)
    perm_verbale  INTEGER NOT NULL DEFAULT 0,  -- scrive il verbale (tappa 4)
    perm_persone  INTEGER NOT NULL DEFAULT 0,  -- gestisce persone e ruoli
    di_base       INTEGER NOT NULL DEFAULT 0   -- 1 = non si può eliminare
);
-- I due ruoli di partenza. "OR IGNORE": se esistono già (anche rinominati) non si toccano.
INSERT OR IGNORE INTO ruoli (id, nome, perm_riunioni, perm_odg, perm_conclude, perm_verbale, perm_persone, di_base)
VALUES (1, 'Amministratore', 1, 1, 1, 1, 1, 1),
       (2, 'Partecipante',   0, 0, 0, 0, 0, 1);

CREATE TABLE IF NOT EXISTS persone (
    id        INTEGER PRIMARY KEY,
    nome      TEXT NOT NULL,                   -- "Anna B." (nome + iniziale del cognome)
    colore    TEXT NOT NULL,                   -- colore delle sue proposte e spunte
    ruolo_id  INTEGER NOT NULL DEFAULT 2 REFERENCES ruoli(id),
    creata_il TEXT NOT NULL DEFAULT (datetime('now'))
);

-- I dispositivi (telefono, PC...) con cui una persona usa OdG. Il browser tiene
-- un "gettone" casuale in un cookie; qui se ne salva solo l'impronta (hash):
-- anche chi leggesse il database non potrebbe spacciarsi per qualcuno.
CREATE TABLE IF NOT EXISTS dispositivi (
    id          INTEGER PRIMARY KEY,
    persona_id  INTEGER NOT NULL REFERENCES persone(id) ON DELETE CASCADE,
    impronta    TEXT NOT NULL UNIQUE,
    creato_il   TEXT NOT NULL DEFAULT (datetime('now')),
    ultimo_uso  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Link monouso: "usa OdG su un altro dispositivo" (15 minuti) e link di
-- attivazione mandati da un amministratore (7 giorni).
CREATE TABLE IF NOT EXISTS inviti (
    id          INTEGER PRIMARY KEY,
    persona_id  INTEGER NOT NULL REFERENCES persone(id) ON DELETE CASCADE,
    impronta    TEXT NOT NULL UNIQUE,
    scade_il    TEXT NOT NULL,
    usato_il    TEXT
);

-- Proposte di modifica all'OdG, da approvare.
CREATE TABLE IF NOT EXISTS proposte (
    id          INTEGER PRIMARY KEY,
    riunione_id INTEGER NOT NULL REFERENCES riunioni(id) ON DELETE CASCADE,
    persona_id  INTEGER NOT NULL REFERENCES persone(id) ON DELETE CASCADE,
    tipo        TEXT NOT NULL CHECK (tipo IN ('aggiungi', 'modifica', 'togli')),
    punto_id    INTEGER REFERENCES punti(id) ON DELETE CASCADE,  -- per modifica e togli
    titolo      TEXT,
    minuti      INTEGER,
    stato       TEXT NOT NULL DEFAULT 'in_attesa'
                CHECK (stato IN ('in_attesa', 'approvata', 'rifiutata', 'ritirata')),
    creata_il   TEXT NOT NULL DEFAULT (datetime('now')),
    decisa_da   INTEGER REFERENCES persone(id) ON DELETE SET NULL,
    decisa_il   TEXT
);
CREATE INDEX IF NOT EXISTS idx_proposte_riunione ON proposte(riunione_id, stato);


-- ======================================================== tappa 4: la riunione
-- (Colonne nuove su punti e riunioni: vedi COLONNE_AGGIUNTE in database.py.)

-- Le "Varie": ogni OdG ha come ultimo punto fisso un contenitore in cui
-- chiunque aggiunge direttamente le sue voci, senza proposta né approvazione.
CREATE TABLE IF NOT EXISTS voci_varie (
    id          INTEGER PRIMARY KEY,
    riunione_id INTEGER NOT NULL REFERENCES riunioni(id) ON DELETE CASCADE,
    persona_id  INTEGER REFERENCES persone(id) ON DELETE SET NULL,
    testo       TEXT NOT NULL,
    creata_il   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Compiti decisi in riunione: "chi fa cosa". Chi li ha assegnati li ritrova
-- nel profilo e in cima alla riunione successiva dello stesso tipo.
CREATE TABLE IF NOT EXISTS compiti (
    id          INTEGER PRIMARY KEY,
    riunione_id INTEGER NOT NULL REFERENCES riunioni(id) ON DELETE CASCADE,
    punto_id    INTEGER REFERENCES punti(id) ON DELETE SET NULL,
    testo       TEXT NOT NULL,
    persona_id  INTEGER REFERENCES persone(id) ON DELETE SET NULL,   -- a chi è assegnato
    creato_da   INTEGER REFERENCES persone(id) ON DELETE SET NULL,
    creato_il   TEXT NOT NULL DEFAULT (datetime('now')),
    fatto_il    TEXT,
    fatto_da    INTEGER REFERENCES persone(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_compiti_persona ON compiti(persona_id, fatto_il);

-- Punti non trattati in attesa di una riunione successiva ancora da fissare:
-- entrano da soli nell'OdG della prossima riunione di quel tipo appena creata.
CREATE TABLE IF NOT EXISTS da_riportare (
    id          INTEGER PRIMARY KEY,
    tipo_id     INTEGER NOT NULL REFERENCES tipi_riunione(id) ON DELETE CASCADE,
    punto_id    INTEGER REFERENCES punti(id) ON DELETE SET NULL,     -- il punto d'origine
    titolo      TEXT NOT NULL,
    minuti      INTEGER NOT NULL,
    proposto_da INTEGER REFERENCES persone(id) ON DELETE SET NULL
);

-- Chi era presente a una riunione. Si scelgono tra le persone già note;
-- chi non c'è ancora si aggiunge al volo (con il ruolo di Partecipante).
CREATE TABLE IF NOT EXISTS presenze (
    riunione_id INTEGER NOT NULL REFERENCES riunioni(id) ON DELETE CASCADE,
    persona_id  INTEGER NOT NULL REFERENCES persone(id) ON DELETE CASCADE,
    segnato_da  INTEGER REFERENCES persone(id) ON DELETE SET NULL,
    PRIMARY KEY (riunione_id, persona_id)
);

-- Modifiche ai dati da fare una volta sola (es. dare un permesso a un ruolo
-- esistente): qui si segna quali sono già state fatte. Vedi database.py.
CREATE TABLE IF NOT EXISTS migrazioni (
    nome      TEXT PRIMARY KEY,
    fatta_il  TEXT NOT NULL DEFAULT (datetime('now'))
);
