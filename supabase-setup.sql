-- ============================================================
-- MELDPUNT AMBTENAREN — Supabase Database Setup
-- ============================================================
-- Draai dit in de Supabase SQL Editor (https://supabase.com/dashboard)
-- Na het aanmaken van een gratis project.
-- ============================================================

-- ============ TABELLEN ============

-- Meldingen (uitbreiding van bestaand model)
CREATE TABLE IF NOT EXISTS meldingen (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id),
    claim_code VARCHAR(10) UNIQUE DEFAULT ('MLD-' || upper(substr(md5(random()::text), 1, 6))),
    titel TEXT,
    verhaal TEXT,
    instantie VARCHAR(200),
    plaats VARCHAR(200),
    namen JSONB DEFAULT '[]'::jsonb,
    feiten JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(20) DEFAULT 'review',
    anoniem BOOLEAN DEFAULT true,
    melder_naam TEXT,
    melder_email TEXT,
    linked_to UUID,
    link_relatie VARCHAR(20),
    views INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Documenten (uploads van gedupeerden)
CREATE TABLE IF NOT EXISTS documenten (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    melding_id UUID REFERENCES meldingen(id) ON DELETE CASCADE,
    dossier_id UUID,  -- FK wordt later toegevoegd
    user_id UUID REFERENCES auth.users(id),
    bestandsnaam VARCHAR(255),
    storage_path VARCHAR(500),
    mime_type VARCHAR(100),
    grootte INTEGER,
    geanonimiseerd BOOLEAN DEFAULT false,
    publiek BOOLEAN DEFAULT false,
    uploaded_at TIMESTAMPTZ DEFAULT now()
);

-- Dossiers (slachtoffers bouwen hun eigen dossier)
CREATE TABLE IF NOT EXISTS dossiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) NOT NULL,
    titel TEXT DEFAULT 'Mijn dossier',
    samenvatting TEXT,
    instanties JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(20) DEFAULT 'concept',
    melding_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- FK voor documenten → dossiers (nu dossiers tabel bestaat)
ALTER TABLE documenten ADD CONSTRAINT fk_documenten_dossier
    FOREIGN KEY (dossier_id) REFERENCES dossiers(id) ON DELETE SET NULL;

-- EHRM procedures (Europees Hof voor de Rechten van de Mens)
CREATE TABLE IF NOT EXISTS ehrm_procedures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) NOT NULL,
    dossier_id UUID REFERENCES dossiers(id),
    stap VARCHAR(50) DEFAULT 'intake',
    geschonden_artikelen JSONB DEFAULT '[]'::jsonb,
    feiten_samenvatting TEXT,
    nationale_procedures TEXT,
    uitkomst_nationaal TEXT,
    documenten_ids UUID[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============ INDEXES ============

CREATE INDEX IF NOT EXISTS idx_meldingen_user ON meldingen(user_id);
CREATE INDEX IF NOT EXISTS idx_meldingen_status ON meldingen(status);
CREATE INDEX IF NOT EXISTS idx_meldingen_claim ON meldingen(claim_code);
CREATE INDEX IF NOT EXISTS idx_documenten_user ON documenten(user_id);
CREATE INDEX IF NOT EXISTS idx_documenten_dossier ON documenten(dossier_id);
CREATE INDEX IF NOT EXISTS idx_dossiers_user ON dossiers(user_id);
CREATE INDEX IF NOT EXISTS idx_ehrm_user ON ehrm_procedures(user_id);
CREATE INDEX IF NOT EXISTS idx_ehrm_dossier ON ehrm_procedures(dossier_id);

-- ============ ROW LEVEL SECURITY ============

ALTER TABLE meldingen ENABLE ROW LEVEL SECURITY;
ALTER TABLE documenten ENABLE ROW LEVEL SECURITY;
ALTER TABLE dossiers ENABLE ROW LEVEL SECURITY;
ALTER TABLE ehrm_procedures ENABLE ROW LEVEL SECURITY;

-- MELDINGEN POLICIES
-- Iedereen kan gepubliceerde meldingen lezen
CREATE POLICY "Publiek leest live meldingen"
    ON meldingen FOR SELECT TO anon
    USING (status = 'live');

-- Ingelogde users lezen eigen + gepubliceerde meldingen
CREATE POLICY "Users lezen eigen en live meldingen"
    ON meldingen FOR SELECT TO authenticated
    USING (user_id = auth.uid() OR status = 'live');

-- Ingelogde users maken meldingen (gekoppeld aan account)
CREATE POLICY "Users maken meldingen"
    ON meldingen FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

-- Anonieme bezoekers mogen ook melden (user_id = NULL)
CREATE POLICY "Anoniem melding maken"
    ON meldingen FOR INSERT TO anon
    WITH CHECK (user_id IS NULL);

-- Eigen meldingen updaten
CREATE POLICY "Users updaten eigen meldingen"
    ON meldingen FOR UPDATE TO authenticated
    USING (user_id = auth.uid());

-- DOCUMENTEN POLICIES
CREATE POLICY "Users lezen eigen documenten"
    ON documenten FOR SELECT TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "Users uploaden documenten"
    ON documenten FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users updaten eigen documenten"
    ON documenten FOR UPDATE TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "Users verwijderen eigen documenten"
    ON documenten FOR DELETE TO authenticated
    USING (user_id = auth.uid());

-- DOSSIERS POLICIES
CREATE POLICY "Users lezen eigen dossiers"
    ON dossiers FOR SELECT TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "Users maken dossiers"
    ON dossiers FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users updaten eigen dossiers"
    ON dossiers FOR UPDATE TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "Users verwijderen eigen dossiers"
    ON dossiers FOR DELETE TO authenticated
    USING (user_id = auth.uid());

-- EHRM PROCEDURES POLICIES
CREATE POLICY "Users lezen eigen procedures"
    ON ehrm_procedures FOR SELECT TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "Users maken procedures"
    ON ehrm_procedures FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users updaten eigen procedures"
    ON ehrm_procedures FOR UPDATE TO authenticated
    USING (user_id = auth.uid());

-- ============ STORAGE ============

-- Maak storage bucket voor documenten (privé)
INSERT INTO storage.buckets (id, name, public)
VALUES ('documenten', 'documenten', false)
ON CONFLICT (id) DO NOTHING;

-- Storage policies: users uploaden naar eigen map
CREATE POLICY "Users uploaden naar eigen map"
    ON storage.objects FOR INSERT TO authenticated
    WITH CHECK (
        bucket_id = 'documenten'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );

CREATE POLICY "Users lezen eigen bestanden"
    ON storage.objects FOR SELECT TO authenticated
    USING (
        bucket_id = 'documenten'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );

CREATE POLICY "Users verwijderen eigen bestanden"
    ON storage.objects FOR DELETE TO authenticated
    USING (
        bucket_id = 'documenten'
        AND (storage.foldername(name))[1] = auth.uid()::text
    );

-- ============ KLAAR ============
-- Nu moet je nog:
-- 1. Auth → Email provider aanzetten in Supabase dashboard
-- 2. URL + anon key kopiëren naar index.html (SUPABASE_URL en SUPABASE_KEY)
