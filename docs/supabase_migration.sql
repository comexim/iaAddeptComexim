-- ============================================
-- SUPABASE MIGRATION - AGENTE COMEXIM IA
-- Atualiza tabela existente user_preferences
-- ============================================

-- Adiciona colunas faltantes (se não existirem)
DO $$
BEGIN
    -- Adiciona coluna email
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='email') THEN
        ALTER TABLE user_preferences ADD COLUMN email VARCHAR(255);
    END IF;

    -- Adiciona coluna nome (se não existir)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='nome') THEN
        ALTER TABLE user_preferences ADD COLUMN nome VARCHAR(255);
    END IF;

    -- Adiciona coluna nivel_detalhe
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='nivel_detalhe') THEN
        ALTER TABLE user_preferences ADD COLUMN nivel_detalhe VARCHAR(50) DEFAULT 'medio';
    END IF;

    -- Adiciona coluna tom_de_voz
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='tom_de_voz') THEN
        ALTER TABLE user_preferences ADD COLUMN tom_de_voz VARCHAR(50) DEFAULT 'profissional';
    END IF;

    -- Adiciona coluna formato_resposta
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='formato_resposta') THEN
        ALTER TABLE user_preferences ADD COLUMN formato_resposta VARCHAR(50) DEFAULT 'texto';
    END IF;

    -- Adiciona coluna formato_moeda
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='formato_moeda') THEN
        ALTER TABLE user_preferences ADD COLUMN formato_moeda VARCHAR(10) DEFAULT 'BRL';
    END IF;

    -- Adiciona coluna formato_data
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='formato_data') THEN
        ALTER TABLE user_preferences ADD COLUMN formato_data VARCHAR(20) DEFAULT 'DD/MM/YYYY';
    END IF;

    -- Adiciona coluna emojis_habilitados
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='emojis_habilitados') THEN
        ALTER TABLE user_preferences ADD COLUMN emojis_habilitados BOOLEAN DEFAULT TRUE;
    END IF;

    -- Adiciona coluna saudacao_customizada
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='saudacao_customizada') THEN
        ALTER TABLE user_preferences ADD COLUMN saudacao_customizada TEXT;
    END IF;

    -- Adiciona coluna assinatura_customizada
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='assinatura_customizada') THEN
        ALTER TABLE user_preferences ADD COLUMN assinatura_customizada TEXT;
    END IF;

    -- Adiciona coluna areas_interesse
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='areas_interesse') THEN
        ALTER TABLE user_preferences ADD COLUMN areas_interesse JSONB DEFAULT '[]'::JSONB;
    END IF;

    -- Adiciona coluna metricas_favoritas
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='metricas_favoritas') THEN
        ALTER TABLE user_preferences ADD COLUMN metricas_favoritas JSONB DEFAULT '[]'::JSONB;
    END IF;

    -- Adiciona coluna instrucoes_adicionais
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='instrucoes_adicionais') THEN
        ALTER TABLE user_preferences ADD COLUMN instrucoes_adicionais TEXT;
    END IF;

    -- Adiciona coluna learning_history
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='learning_history') THEN
        ALTER TABLE user_preferences ADD COLUMN learning_history JSONB DEFAULT '[]'::JSONB;
    END IF;

    -- Adiciona coluna confidence_score
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='confidence_score') THEN
        ALTER TABLE user_preferences ADD COLUMN confidence_score FLOAT DEFAULT 0.5;
    END IF;

    -- Adiciona coluna last_feedback_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='last_feedback_at') THEN
        ALTER TABLE user_preferences ADD COLUMN last_feedback_at TIMESTAMP;
    END IF;

    -- Adiciona coluna feedback_count
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='feedback_count') THEN
        ALTER TABLE user_preferences ADD COLUMN feedback_count INTEGER DEFAULT 0;
    END IF;

    -- Adiciona coluna created_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='created_at') THEN
        ALTER TABLE user_preferences ADD COLUMN created_at TIMESTAMP DEFAULT NOW();
    END IF;

    -- Adiciona coluna updated_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='user_preferences' AND column_name='updated_at') THEN
        ALTER TABLE user_preferences ADD COLUMN updated_at TIMESTAMP DEFAULT NOW();
    END IF;
END
$$;

-- ============================================
-- Tabela de Log: preference_learning_log
-- ============================================
CREATE TABLE IF NOT EXISTS preference_learning_log (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  telefone VARCHAR(20) NOT NULL,
  user_message TEXT NOT NULL,
  feedback_detected JSONB,
  preference_updated VARCHAR(100),
  old_value TEXT,
  new_value TEXT,
  confidence FLOAT,
  applied BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT NOW(),

  FOREIGN KEY (telefone) REFERENCES user_preferences(telefone) ON DELETE CASCADE
);

-- ============================================
-- Índices para Performance
-- ============================================
CREATE INDEX IF NOT EXISTS idx_user_prefs_telefone ON user_preferences(telefone);
CREATE INDEX IF NOT EXISTS idx_learning_log_telefone ON preference_learning_log(telefone);
CREATE INDEX IF NOT EXISTS idx_learning_log_created_at ON preference_learning_log(created_at DESC);

-- ============================================
-- Função: Atualizar updated_at automaticamente
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para atualizar updated_at
DROP TRIGGER IF EXISTS update_user_preferences_updated_at ON user_preferences;
CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Função: Registrar no learning_history ao atualizar
-- ============================================
CREATE OR REPLACE FUNCTION log_preference_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Adiciona mudança ao learning_history
    IF NEW.nivel_detalhe != OLD.nivel_detalhe OR
       NEW.tom_de_voz != OLD.tom_de_voz OR
       NEW.formato_resposta != OLD.formato_resposta OR
       NEW.emojis_habilitados != OLD.emojis_habilitados THEN

        NEW.learning_history = COALESCE(NEW.learning_history, '[]'::JSONB) ||
            jsonb_build_object(
                'timestamp', NOW(),
                'changes', jsonb_build_object(
                    'nivel_detalhe', CASE WHEN NEW.nivel_detalhe != OLD.nivel_detalhe THEN
                        jsonb_build_object('old', OLD.nivel_detalhe, 'new', NEW.nivel_detalhe) ELSE NULL END,
                    'tom_de_voz', CASE WHEN NEW.tom_de_voz != OLD.tom_de_voz THEN
                        jsonb_build_object('old', OLD.tom_de_voz, 'new', NEW.tom_de_voz) ELSE NULL END,
                    'formato_resposta', CASE WHEN NEW.formato_resposta != OLD.formato_resposta THEN
                        jsonb_build_object('old', OLD.formato_resposta, 'new', NEW.formato_resposta) ELSE NULL END,
                    'emojis_habilitados', CASE WHEN NEW.emojis_habilitados != OLD.emojis_habilitados THEN
                        jsonb_build_object('old', OLD.emojis_habilitados, 'new', NEW.emojis_habilitados) ELSE NULL END
                )
            );

        NEW.last_feedback_at = NOW();
        NEW.feedback_count = COALESCE(OLD.feedback_count, 0) + 1;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger para log automático
DROP TRIGGER IF EXISTS log_user_preference_changes ON user_preferences;
CREATE TRIGGER log_user_preference_changes
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION log_preference_change();

-- ============================================
-- Atualizar/Inserir Dados Iniciais
-- ============================================
INSERT INTO user_preferences (telefone, nome, email, nivel_detalhe, tom_de_voz, formato_resposta, emojis_habilitados)
VALUES
  ('11915901500', 'Marco Aurélio', 'marco.souza@comexim.com.br', 'detalhado', 'profissional', 'tabular', FALSE),
  ('13991386001', 'Renan Hazan', 'renan.hazan@comexim.com.br', 'resumido', 'casual', 'bullet_points', TRUE),
  ('35920000589', 'Lucas Oliveira', 'lucas.oliveira@comexim.com.br', 'medio', 'profissional', 'texto', TRUE),
  ('13991555279', 'Rodrigo Perez', 'rodrigo.perez@comexim.com.br', 'detalhado', 'tecnico', 'narrativo', FALSE),
  ('13988188810', 'Bruno Hazan', 'bruno@comexim.com.br', 'medio', 'profissional', 'texto', TRUE)
ON CONFLICT (telefone) DO UPDATE SET
  nome = EXCLUDED.nome,
  email = EXCLUDED.email,
  nivel_detalhe = EXCLUDED.nivel_detalhe,
  tom_de_voz = EXCLUDED.tom_de_voz,
  formato_resposta = EXCLUDED.formato_resposta,
  emojis_habilitados = EXCLUDED.emojis_habilitados;

-- ============================================
-- Views Úteis
-- ============================================

-- View: Resumo de preferências por usuário
CREATE OR REPLACE VIEW v_user_preferences_summary AS
SELECT
  telefone,
  nome,
  email,
  nivel_detalhe,
  tom_de_voz,
  formato_resposta,
  emojis_habilitados,
  confidence_score,
  feedback_count,
  last_feedback_at,
  created_at
FROM user_preferences
ORDER BY last_feedback_at DESC NULLS LAST;

-- View: Últimas mudanças de preferências
CREATE OR REPLACE VIEW v_recent_preference_changes AS
SELECT
  pl.telefone,
  up.nome,
  pl.user_message,
  pl.preference_updated,
  pl.old_value,
  pl.new_value,
  pl.confidence,
  pl.applied,
  pl.created_at
FROM preference_learning_log pl
JOIN user_preferences up ON pl.telefone = up.telefone
ORDER BY pl.created_at DESC
LIMIT 100;

-- ============================================
-- MIGRAÇÃO COMPLETA!
-- ============================================
-- Este script adiciona as colunas faltantes à tabela existente
-- Execute no Supabase SQL Editor
-- ============================================
