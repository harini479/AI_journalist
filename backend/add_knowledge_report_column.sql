-- Run this in your Supabase SQL Editor
-- Navigate to: Supabase Dashboard > SQL Editor > New Query

-- Create dedicated table for tacit knowledge reports
CREATE TABLE IF NOT EXISTS tacit_knowledge_reports (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    session_id TEXT NOT NULL,
    report_title TEXT,
    expert_domain TEXT,
    interview_depth_score INTEGER,
    total_insights_extracted INTEGER,
    summary TEXT,
    tacit_insights JSONB DEFAULT '[]'::jsonb,
    mental_models JSONB DEFAULT '[]'::jsonb,
    pattern_breaks JSONB DEFAULT '[]'::jsonb,
    war_stories JSONB DEFAULT '[]'::jsonb,
    actionable_playbooks JSONB DEFAULT '[]'::jsonb,
    knowledge_gaps JSONB DEFAULT '[]'::jsonb,
    messages_analyzed INTEGER,
    questions_completed INTEGER,
    total_questions INTEGER,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Index for fast lookups by session
CREATE INDEX IF NOT EXISTS idx_tkr_session_id ON tacit_knowledge_reports(session_id);

-- Verify the table was created
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'tacit_knowledge_reports'
ORDER BY ordinal_position;
