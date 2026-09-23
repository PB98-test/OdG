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
