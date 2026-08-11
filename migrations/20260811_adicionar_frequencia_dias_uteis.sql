-- Permite agendamentos recorrentes somente de segunda a sexta-feira.
-- Execute no SQL Editor do projeto Supabase usado pela aplicação.

ALTER TABLE public.relatorios_agendados
    DROP CONSTRAINT IF EXISTS relatorios_agendados_frequencia_check;

ALTER TABLE public.relatorios_agendados
    ADD CONSTRAINT relatorios_agendados_frequencia_check
    CHECK (frequencia IN ('unico', 'diario', 'dias_uteis', 'semanal', 'mensal'));

