"""
Scheduler de relatórios agendados
Roda a cada hora e executa relatórios com next_run <= agora
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.supabase_client import supabase_client

logger = logging.getLogger(__name__)

TZ = pytz.timezone("America/Sao_Paulo")

# Mapeamento: dia da semana em texto → número (0=segunda, 6=domingo)
DIAS_SEMANA = {
    "segunda": 0, "segunda-feira": 0,
    "terca": 1, "terça": 1, "terca-feira": 1, "terça-feira": 1,
    "quarta": 2, "quarta-feira": 2,
    "quinta": 3, "quinta-feira": 3,
    "sexta": 4, "sexta-feira": 4,
    "sabado": 5, "sábado": 5,
    "domingo": 6,
}


def calcular_next_run(
    frequencia: str,
    horario: str,
    dia_semana: Optional[int] = None,
    dia_mes: Optional[int] = None,
    a_partir_de: Optional[datetime] = None,
) -> datetime:
    """
    Calcula a próxima execução de um relatório agendado.

    Args:
        frequencia: 'diario', 'semanal' ou 'mensal'
        horario: Horário no formato 'HH:MM'
        dia_semana: 0=segunda ... 6=domingo (para semanal)
        dia_mes: 1-31 (para mensal)
        a_partir_de: datetime de referência (default: agora em SP)

    Returns:
        datetime com a próxima execução (timezone-aware, America/Sao_Paulo)
    """
    agora = a_partir_de or datetime.now(TZ)
    hora, minuto = map(int, horario.split(":"))

    if frequencia == "diario":
        candidato = agora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
        if candidato <= agora:
            candidato += timedelta(days=1)
        return candidato

    elif frequencia == "semanal":
        # dia_semana: 0=segunda, 6=domingo
        dias_ate = (dia_semana - agora.weekday()) % 7
        candidato = (agora + timedelta(days=dias_ate)).replace(
            hour=hora, minute=minuto, second=0, microsecond=0
        )
        if candidato <= agora:
            candidato += timedelta(weeks=1)
        return candidato

    elif frequencia == "mensal":
        try:
            candidato = agora.replace(day=dia_mes, hour=hora, minute=minuto, second=0, microsecond=0)
        except ValueError:
            # Dia inválido para o mês (ex: 31 em fevereiro) → último dia do mês
            import calendar
            ultimo_dia = calendar.monthrange(agora.year, agora.month)[1]
            candidato = agora.replace(day=ultimo_dia, hour=hora, minute=minuto, second=0, microsecond=0)
        if candidato <= agora:
            # Avança para o próximo mês
            if agora.month == 12:
                candidato = candidato.replace(year=agora.year + 1, month=1)
            else:
                candidato = candidato.replace(month=agora.month + 1)
        return candidato

    raise ValueError(f"Frequência desconhecida: {frequencia}")


async def _executar_relatorio(relatorio: dict) -> None:
    """Executa um único relatório e envia via WhatsApp."""
    from app.services.auth import AuthService
    from app.agents.orchestrator import AgentOrchestrator
    from app.services.whatsapp import WhatsAppService
    from app.services.formatter import response_formatter

    telefone = relatorio["telefone"]
    descricao = relatorio["descricao"]
    relatorio_id = relatorio["id"]
    horario = relatorio.get("horario", "08:00")
    frequencia = relatorio["frequencia"]
    dia_semana = relatorio.get("dia_semana")
    dia_mes = relatorio.get("dia_mes")

    logger.info(f"[SCHEDULER] Executando relatório '{descricao}' para {telefone}")

    try:
        # Autentica usuário
        auth_service = AuthService()
        user = await auth_service.authenticate_user(telefone)
        if not user:
            logger.warning(f"[SCHEDULER] Usuário {telefone} não autenticado, pulando relatório")
            return

        # Monta a mensagem que a IA vai receber
        mensagem = f"[RELATÓRIO AUTOMÁTICO AGENDADO] {descricao}"

        # Invoca o agente
        orchestrator = AgentOrchestrator(user=user, session_id=telefone)
        resposta = await orchestrator.process_message(mensagem)

        # Formata e envia via WhatsApp
        from app.services.formatter import response_formatter
        whatsapp = WhatsAppService()
        partes = await response_formatter.format_response(resposta)
        await whatsapp.send_multiple_messages(telefone, partes)

        logger.info(f"[SCHEDULER] Relatório '{descricao}' enviado com sucesso para {telefone}")

    except Exception as e:
        logger.error(f"[SCHEDULER] Erro ao executar relatório '{descricao}' para {telefone}: {e}")
        return

    # Atualiza last_run e next_run no Supabase
    agora = datetime.now(TZ)
    next_run = calcular_next_run(frequencia, horario, dia_semana, dia_mes, a_partir_de=agora)
    await supabase_client.atualizar_next_run(
        relatorio_id=relatorio_id,
        next_run=next_run.isoformat(),
        last_run=agora.isoformat(),
    )
    logger.info(f"[SCHEDULER] Próxima execução de '{descricao}': {next_run.strftime('%d/%m/%Y %H:%M')}")


async def verificar_e_executar_relatorios() -> None:
    """Job horário: busca relatórios com next_run <= agora e executa."""
    logger.info("[SCHEDULER] Verificando relatórios pendentes...")
    relatorios = await supabase_client.buscar_relatorios_pendentes()

    if not relatorios:
        logger.info("[SCHEDULER] Nenhum relatório pendente.")
        return

    logger.info(f"[SCHEDULER] {len(relatorios)} relatório(s) para executar.")
    for relatorio in relatorios:
        await _executar_relatorio(relatorio)


def criar_scheduler() -> AsyncIOScheduler:
    """Cria e configura o scheduler."""
    scheduler = AsyncIOScheduler(timezone=TZ)
    scheduler.add_job(
        verificar_e_executar_relatorios,
        trigger=CronTrigger(minute=0, timezone=TZ),  # Roda no início de cada hora
        id="verificar_relatorios",
        replace_existing=True,
        misfire_grace_time=300,  # 5 min de tolerância se o servidor estava down
    )
    return scheduler
