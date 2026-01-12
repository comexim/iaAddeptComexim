-- ============================================
-- SUPABASE SETUP - AGENTE COMEXIM IA
-- Sistema de Aprendizado de Preferências
-- ============================================

-- Habilita extensão UUID (se não estiver habilitada)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- Tabela Principal: user_preferences
-- ============================================
CREATE TABLE IF NOT EXISTS user_preferences (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  telefone VARCHAR(20) UNIQUE NOT NULL,
  nome VARCHAR(255),
  email VARCHAR(255),

  -- Preferências de Comunicação
  nivel_detalhe VARCHAR(50) DEFAULT 'medio',     -- resumido, medio, detalhado, muito_detalhado
  tom_de_voz VARCHAR(50) DEFAULT 'profissional', -- profissional, casual, tecnico, executivo
  formato_resposta VARCHAR(50) DEFAULT 'texto',  -- texto, bullet_points, tabular, narrativo

  -- Preferências de Formatação
  formato_moeda VARCHAR(10) DEFAULT 'BRL',       -- BRL, USD, EUR
  formato_data VARCHAR(20) DEFAULT 'DD/MM/YYYY', -- DD/MM/YYYY, MM/DD/YYYY
  emojis_habilitados BOOLEAN DEFAULT TRUE,

  -- Personalização de Mensagens
  saudacao_customizada TEXT,                     -- Ex: "Bom dia, Dr. Fulano"
  assinatura_customizada TEXT,                   -- Ex: "Att, Agente Comexim"

  -- Contexto de Negócio
  areas_interesse JSONB DEFAULT '[]'::JSONB,     -- ["Vendas", "Financeiro"]
  metricas_favoritas JSONB DEFAULT '[]'::JSONB,  -- ["faturamento", "saldo"]

  -- Preferências Avançadas
  instrucoes_adicionais TEXT,                    -- Campo livre para instruções

  -- Tracking de Aprendizado
  learning_history JSONB DEFAULT '[]'::JSONB,    -- Histórico de ajustes
  confidence_score FLOAT DEFAULT 0.5,             -- Confiança geral no perfil (0-1)
  last_feedback_at TIMESTAMP,
  feedback_count INTEGER DEFAULT 0,

  -- Metadata
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

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
-- Dados Iniciais (Usuários da planilha)
-- ============================================
INSERT INTO user_preferences (telefone, nome, email, nivel_detalhe, tom_de_voz, formato_resposta, emojis_habilitados)
VALUES
  ('11915901500', 'Marco Aurélio', 'marco.souza@comexim.com.br', 'detalhado', 'profissional', 'tabular', FALSE),
  ('13991386001', 'Renan Hazan', 'renan.hazan@comexim.com.br', 'resumido', 'casual', 'bullet_points', TRUE),
  ('35920000589', 'Lucas Oliveira', 'lucas.oliveira@comexim.com.br', 'medio', 'profissional', 'texto', TRUE),
  ('13991555279', 'Rodrigo Perez', 'rodrigo.perez@comexim.com.br', 'detalhado', 'tecnico', 'narrativo', FALSE),
  ('13988188810', 'Bruno Hazan', 'bruno@comexim.com.br', 'medio', 'profissional', 'texto', TRUE)
ON CONFLICT (telefone) DO NOTHING;

-- ============================================
-- Políticas RLS (Row Level Security) - OPCIONAL
-- ============================================
-- ALTER TABLE user_preferences ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE preference_learning_log ENABLE ROW LEVEL SECURITY;

-- Política: Service role tem acesso total
-- CREATE POLICY "Service role has full access" ON user_preferences
--   FOR ALL USING (auth.role() = 'service_role');

-- CREATE POLICY "Service role has full access" ON preference_learning_log
--   FOR ALL USING (auth.role() = 'service_role');

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
-- SETUP COMPLETO!
-- ============================================
-- Execute este script no Supabase SQL Editor
-- Dashboard > SQL Editor > New Query > Cole e Execute
-- ============================================
