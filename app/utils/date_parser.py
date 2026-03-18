"""
Parser de datas em linguagem natural para formatos SQL
"""
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pytz
import re
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)

# Timezone São Paulo
TZ_SP = pytz.timezone("America/Sao_Paulo")


class DateParser:
    """Parser de datas em linguagem natural"""

    @staticmethod
    def get_current_date() -> datetime:
        """Retorna data atual em São Paulo"""
        return datetime.now(TZ_SP)

    @staticmethod
    def format_yyyymmdd(date: datetime) -> str:
        """Formato: 20251215"""
        return date.strftime("%Y%m%d")

    @staticmethod
    def format_yyyy_mm(date: datetime) -> str:
        """Formato: 2025/12"""
        return date.strftime("%Y/%m")

    @staticmethod
    def parse_natural_date(text: str) -> Optional[Dict[str, str]]:
        """
        Converte linguagem natural em datas SQL

        Args:
            text: Texto em linguagem natural ou formato YYYYMMDD

        Returns:
            Dict com chaves: data_inicio, data_fim, mes_embarque, ano, mes
        """
        # Converte para string se não for (pode vir como int do LLM)
        if not isinstance(text, str):
            logger.debug(f"[DEBUG] Convertendo {type(text)} para string: {text}")
            text = str(text)

        text = text.lower().strip()
        now = DateParser.get_current_date()
        result = {}

        # Formato direto: YYYYMMDD (8 dígitos sem separador)
        # Exemplo: 20251220, 20251219
        if re.match(r'^\d{8}$', text):
            try:
                target_date = datetime.strptime(text, "%Y%m%d").replace(tzinfo=TZ_SP)
                result["data_inicio"] = DateParser.format_yyyymmdd(target_date)
                result["data_fim"] = DateParser.format_yyyymmdd(target_date)
                result["mes_embarque"] = DateParser.format_yyyy_mm(target_date)
                result["ano"] = str(target_date.year)
                result["mes"] = str(target_date.month).zfill(2)
                logger.debug(f"Parseado YYYYMMDD '{text}': {result['data_inicio']}")
                return result
            except ValueError:
                logger.warning(f"Formato YYYYMMDD inválido: {text}")
                return None

        # Hoje
        if "hoje" in text:
            result["data_inicio"] = DateParser.format_yyyymmdd(now)
            result["data_fim"] = DateParser.format_yyyymmdd(now)
            logger.debug(f"Parseado 'hoje': {result['data_inicio']}")
            return result

        # Ontem
        if "ontem" in text:
            yesterday = now - timedelta(days=1)
            result["data_inicio"] = DateParser.format_yyyymmdd(yesterday)
            result["data_fim"] = DateParser.format_yyyymmdd(yesterday)
            logger.debug(f"Parseado 'ontem': {result['data_inicio']}")
            return result

        # Amanhã
        if "amanh" in text:  # cobre "amanhã" e "amanha"
            tomorrow = now + timedelta(days=1)
            result["data_inicio"] = DateParser.format_yyyymmdd(tomorrow)
            result["data_fim"] = DateParser.format_yyyymmdd(tomorrow)
            logger.debug(f"Parseado 'amanhã': {result['data_inicio']}")
            return result

        # Vencidas / Vencidos (todas as contas com vencimento até ontem)
        if "vencid" in text:
            yesterday = now - timedelta(days=1)
            # Data muito antiga como início (19000101) para pegar todos os vencimentos antigos
            result["data_inicio"] = "19000101"
            result["data_fim"] = DateParser.format_yyyymmdd(yesterday)
            logger.debug(f"Parseado 'vencidas': até {result['data_fim']}")
            return result

        # Dias da semana passados (segunda-feira passada, terça passada, etc.)
        dias_semana = {
            "domingo": 6, "segunda": 0, "segunda-feira": 0, "segunda feira": 0,
            "terça": 1, "terca": 1, "terça-feira": 1, "terca-feira": 1, "terça feira": 1, "terca feira": 1,
            "quarta": 2, "quarta-feira": 2, "quarta feira": 2,
            "quinta": 3, "quinta-feira": 3, "quinta feira": 3,
            "sexta": 4, "sexta-feira": 4, "sexta feira": 4,
            "sábado": 5, "sabado": 5, "sábado-feira": 5, "sabado-feira": 5
        }

        # Verifica se tem "passada" ou "passado" no texto
        if "passad" in text:
            for dia_nome, dia_num in dias_semana.items():
                if dia_nome in text:
                    # Dia da semana atual (0=segunda, 1=terça, ..., 6=domingo)
                    current_weekday = now.weekday()

                    # Calcula quantos dias voltar
                    # Se hoje é sábado (5) e quer sexta (4): 1 dia atrás
                    # Se hoje é segunda (0) e quer sexta (4): 3 dias atrás (segunda->domingo->sábado->sexta)
                    days_back = (current_weekday - dia_num) % 7

                    # Se for 0 (mesmo dia da semana), volta 7 dias (semana passada)
                    if days_back == 0:
                        days_back = 7

                    target_date = now - timedelta(days=days_back)
                    result["data_inicio"] = DateParser.format_yyyymmdd(target_date)
                    result["data_fim"] = DateParser.format_yyyymmdd(target_date)
                    logger.debug(f"Parseado '{dia_nome} passada': {result['data_inicio']} (voltou {days_back} dias)")
                    return result

        # Esta semana / essa semana (segunda a domingo da semana atual)
        if "esta semana" in text or "essa semana" in text or "desta semana" in text or "nessa semana" in text:
            current_weekday = now.weekday()  # 0=segunda, 6=domingo
            # Segunda-feira desta semana
            this_monday = now - timedelta(days=current_weekday)
            # Domingo desta semana
            this_sunday = this_monday + timedelta(days=6)
            result["data_inicio"] = DateParser.format_yyyymmdd(this_monday)
            result["data_fim"] = DateParser.format_yyyymmdd(this_sunday)
            logger.debug(f"Parseado 'esta semana': {result['data_inicio']} - {result['data_fim']}")
            return result

        # Próxima semana (segunda a domingo da próxima semana)
        if "próxima semana" in text or "proxima semana" in text:
            current_weekday = now.weekday()
            # Segunda-feira da próxima semana
            next_monday = now + timedelta(days=(7 - current_weekday))
            # Domingo da próxima semana
            next_sunday = next_monday + timedelta(days=6)
            result["data_inicio"] = DateParser.format_yyyymmdd(next_monday)
            result["data_fim"] = DateParser.format_yyyymmdd(next_sunday)
            logger.debug(f"Parseado 'próxima semana': {result['data_inicio']} - {result['data_fim']}")
            return result

        # Semana passada (toda a semana, de segunda a domingo)
        if "semana passada" in text:
            # Hoje é que dia da semana? (0=segunda, 6=domingo)
            current_weekday = now.weekday()

            # Quantos dias voltar até a segunda-feira passada?
            # Se hoje é quarta (2), volta 9 dias para pegar a segunda da semana passada
            # Se hoje é segunda (0), volta 7 dias
            days_to_last_monday = current_weekday + 7

            # Segunda-feira da semana passada
            last_monday = now - timedelta(days=days_to_last_monday)

            # Domingo da semana passada (segunda + 6 dias)
            last_sunday = last_monday + timedelta(days=6)

            result["data_inicio"] = DateParser.format_yyyymmdd(last_monday)
            result["data_fim"] = DateParser.format_yyyymmdd(last_sunday)
            logger.debug(f"Parseado 'semana passada': {result['data_inicio']} - {result['data_fim']}")
            return result

        # Últimos X dias (com ou sem acento)
        match = re.search(r'[úu]ltimos?\s+(\d+)\s+dias?', text)
        if match:
            days = int(match.group(1))
            start_date = now - timedelta(days=days - 1)
            result["data_inicio"] = DateParser.format_yyyymmdd(start_date)
            result["data_fim"] = DateParser.format_yyyymmdd(now)
            result["mes_embarque"] = DateParser.format_yyyy_mm(now)  # Usa o mês atual
            logger.debug(f"Parseado 'últimos {days} dias': {result['data_inicio']} - {result['data_fim']}, mes_embarque={result['mes_embarque']}")
            return result

        # Próximos X dias (com ou sem acento)
        match = re.search(r'pr[óo]ximos?\s+(\d+)\s+dias?', text)
        if match:
            days = int(match.group(1))
            end_date = now + timedelta(days=days - 1)
            result["data_inicio"] = DateParser.format_yyyymmdd(now)
            result["data_fim"] = DateParser.format_yyyymmdd(end_date)
            logger.debug(f"Parseado 'próximos {days} dias': {result['data_inicio']} - {result['data_fim']}")
            return result

        # Este mês (com ou sem acento)
        if "este mês" in text or "esse mês" in text or "este mes" in text or "esse mes" in text:
            first_day = now.replace(day=1)
            # Último dia do mês atual
            last_day = now.replace(day=1) + relativedelta(months=1) - timedelta(days=1)
            result["data_inicio"] = DateParser.format_yyyymmdd(first_day)
            result["data_fim"] = DateParser.format_yyyymmdd(last_day)
            result["mes_embarque"] = DateParser.format_yyyy_mm(now)
            result["ano"] = str(now.year)
            result["mes"] = str(now.month).zfill(2)
            logger.debug(f"Parseado 'este mês': {result}")
            return result

        # Mês passado
        if "mês passado" in text or "mes passado" in text:
            last_month = now - relativedelta(months=1)
            first_day = last_month.replace(day=1)
            last_day = now.replace(day=1) - timedelta(days=1)
            result["data_inicio"] = DateParser.format_yyyymmdd(first_day)
            result["data_fim"] = DateParser.format_yyyymmdd(last_day)
            result["mes_embarque"] = DateParser.format_yyyy_mm(last_month)
            result["ano"] = str(last_month.year)
            result["mes"] = str(last_month.month).zfill(2)
            logger.debug(f"Parseado 'mês passado': {result}")
            return result

        # Meses específicos (janeiro, fevereiro, etc)
        meses = {
            "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3,
            "abril": 4, "maio": 5, "junho": 6,
            "julho": 7, "agosto": 8, "setembro": 9,
            "outubro": 10, "novembro": 11, "dezembro": 12
        }

        for mes_nome, mes_num in meses.items():
            if mes_nome in text:
                # Tenta extrair ano do texto
                match_year = re.search(r'(20\d{2})', text)
                year = int(match_year.group(1)) if match_year else now.year

                target_date = datetime(year, mes_num, 1, tzinfo=TZ_SP)
                result["mes_embarque"] = DateParser.format_yyyy_mm(target_date)
                result["ano"] = str(year)
                result["mes"] = str(mes_num).zfill(2)

                # Primeiro e último dia do mês
                first_day = target_date
                last_day = target_date + relativedelta(months=1) - timedelta(days=1)
                result["data_inicio"] = DateParser.format_yyyymmdd(first_day)
                result["data_fim"] = DateParser.format_yyyymmdd(last_day)

                logger.debug(f"Parseado '{mes_nome} {year}': {result}")
                return result

        # Formato: YYYYMMDD-YYYYMMDD (range, com ou sem espaços)
        match = re.search(r'(\d{8})\s*-\s*(\d{8})', text)
        if match:
            start_str, end_str = match.groups()
            start_date = datetime.strptime(start_str, "%Y%m%d").replace(tzinfo=TZ_SP)
            end_date = datetime.strptime(end_str, "%Y%m%d").replace(tzinfo=TZ_SP)
            result["data_inicio"] = DateParser.format_yyyymmdd(start_date)
            result["data_fim"] = DateParser.format_yyyymmdd(end_date)
            logger.debug(f"Parseado range '{start_str}-{end_str}': {result['data_inicio']} - {result['data_fim']}")
            return result

        # "Desde" + data (a partir de, sem limite superior)
        # Exemplo: "desde 12/12/2025", "desde 20251212"
        if re.search(r'\bdesde\b', text):
            # Remove "desde" e tenta parsear a data
            text_sem_desde = re.sub(r'\bdesde\b', '', text).strip()

            # Tenta DD/MM/YYYY
            match = re.search(r'(\d{2})/(\d{2})/(\d{4})', text_sem_desde)
            if match:
                day, month, year = match.groups()
                target_date = datetime(int(year), int(month), int(day), tzinfo=TZ_SP)
                result["data_inicio"] = DateParser.format_yyyymmdd(target_date)
                # NÃO define data_fim - significa "a partir de"
                logger.debug(f"Parseado 'desde {day}/{month}/{year}': {result['data_inicio']} (sem limite superior)")
                return result

            # Tenta YYYYMMDD
            match = re.search(r'(\d{8})', text_sem_desde)
            if match:
                date_str = match.group(1)
                target_date = datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=TZ_SP)
                result["data_inicio"] = DateParser.format_yyyymmdd(target_date)
                # NÃO define data_fim - significa "a partir de"
                logger.debug(f"Parseado 'desde {date_str}': {result['data_inicio']} (sem limite superior)")
                return result

        # Formato direto: DD/MM/YYYY
        match = re.search(r'(\d{2})/(\d{2})/(\d{4})', text)
        if match:
            day, month, year = match.groups()
            target_date = datetime(int(year), int(month), int(day), tzinfo=TZ_SP)
            result["data_inicio"] = DateParser.format_yyyymmdd(target_date)
            result["data_fim"] = DateParser.format_yyyymmdd(target_date)
            logger.debug(f"Parseado '{day}/{month}/{year}': {result['data_inicio']}")
            return result

        # Formato: YYYY/MM
        match = re.search(r'(20\d{2})/(\d{1,2})', text)
        if match:
            year, month = match.groups()
            target_date = datetime(int(year), int(month.zfill(2)), 1, tzinfo=TZ_SP)
            result["mes_embarque"] = DateParser.format_yyyy_mm(target_date)
            result["ano"] = year
            result["mes"] = month.zfill(2)
            logger.debug(f"Parseado '{year}/{month}': {result}")
            return result

        # Formato: MM/YYYY (ex: 11/2025, 12/2024)
        match = re.search(r'(\d{1,2})/(20\d{2})', text)
        if match:
            month, year = match.groups()
            target_date = datetime(int(year), int(month), 1, tzinfo=TZ_SP)
            result["mes_embarque"] = DateParser.format_yyyy_mm(target_date)
            result["ano"] = year
            result["mes"] = month.zfill(2)
            logger.debug(f"Parseado MM/YYYY '{month}/{year}': {result}")
            return result

        # Trimestres (1TRIM, 2TRIM, Q1, Q2, etc.)
        # Padrões: "1TRIM", "2trim", "Q1", "q2", "primeiro trimestre", "1º trimestre", etc.
        trimestre_patterns = [
            (r'([1-4])\s*[tT][rR][iI][mM]', 'numeric'),  # 1TRIM, 2trim
            (r'[qQ]([1-4])', 'numeric'),  # Q1, q2
            (r'([1-4])[ºo°]\s*trimestre', 'numeric'),  # 1º trimestre, 2o trimestre
            (r'(primeiro|segundo|terceiro|quarto)\s*trimestre', 'word'),  # primeiro trimestre
        ]

        trimestre_map = {
            'primeiro': 1, 'segundo': 2, 'terceiro': 3, 'quarto': 4
        }

        for pattern, match_type in trimestre_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match_type == 'numeric':
                    trimestre = int(match.group(1))
                else:  # word
                    trimestre_word = match.group(1).lower()
                    trimestre = trimestre_map.get(trimestre_word)

                if trimestre:
                    # Tenta extrair ano do texto
                    match_year = re.search(r'(20\d{2})', text)
                    year = int(match_year.group(1)) if match_year else now.year

                    # Mapeia trimestre para meses
                    meses_trimestre = {
                        1: ['01', '02', '03'],
                        2: ['04', '05', '06'],
                        3: ['07', '08', '09'],
                        4: ['10', '11', '12']
                    }

                    meses = meses_trimestre[trimestre]
                    result["ano"] = str(year)
                    result["meses"] = meses  # Lista de meses do trimestre
                    result["trimestre"] = trimestre

                    # Calcula data_inicio e data_fim do trimestre
                    primeiro_mes = int(meses[0])
                    ultimo_mes = int(meses[-1])

                    data_inicio = datetime(year, primeiro_mes, 1, tzinfo=TZ_SP)
                    data_fim_temp = datetime(year, ultimo_mes, 1, tzinfo=TZ_SP)
                    data_fim = data_fim_temp + relativedelta(months=1) - timedelta(days=1)

                    result["data_inicio"] = DateParser.format_yyyymmdd(data_inicio)
                    result["data_fim"] = DateParser.format_yyyymmdd(data_fim)

                    logger.debug(f"Parseado trimestre {trimestre}/{year}: meses={meses}, data_inicio={result['data_inicio']}, data_fim={result['data_fim']}")
                    return result

        # Ano completo (2025, 2025 completo, ano 2025, ano completo, etc.)
        # Deve vir ANTES de semestres para não conflitar
        ano_patterns = [
            r'(20\d{2})\s*(completo|inteiro)',  # 2025 completo, 2025 inteiro
            r'ano\s*(20\d{2})',  # ano 2025
            r'ano\s*(completo|inteiro)',  # ano completo (usa ano atual)
            r'^(20\d{2})$',  # apenas 2025 (mas só se for exatamente isso)
        ]

        for pattern in ano_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                # Tenta extrair o ano
                year_match = re.search(r'(20\d{2})', text)
                year = int(year_match.group(1)) if year_match else now.year

                # Todos os 12 meses do ano
                meses = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12']

                result["ano"] = str(year)
                result["meses"] = meses
                result["ano_completo"] = True

                # Calcula data_inicio e data_fim do ano
                data_inicio = datetime(year, 1, 1, tzinfo=TZ_SP)
                data_fim = datetime(year, 12, 31, tzinfo=TZ_SP)

                result["data_inicio"] = DateParser.format_yyyymmdd(data_inicio)
                result["data_fim"] = DateParser.format_yyyymmdd(data_fim)

                logger.debug(f"Parseado ano completo {year}: meses={meses}, data_inicio={result['data_inicio']}, data_fim={result['data_fim']}")
                return result

        # Semestres (1SEM, 2SEM, primeiro semestre, etc.)
        semestre_patterns = [
            (r'([1-2])\s*[sS][eE][mM]', 'numeric'),  # 1SEM, 2sem
            (r'([1-2])[ºo°]\s*semestre', 'numeric'),  # 1º semestre
            (r'(primeiro|segundo)\s*semestre', 'word'),  # primeiro semestre
        ]

        semestre_map = {
            'primeiro': 1, 'segundo': 2
        }

        for pattern, match_type in semestre_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match_type == 'numeric':
                    semestre = int(match.group(1))
                else:  # word
                    semestre_word = match.group(1).lower()
                    semestre = semestre_map.get(semestre_word)

                if semestre:
                    # Tenta extrair ano do texto
                    match_year = re.search(r'(20\d{2})', text)
                    year = int(match_year.group(1)) if match_year else now.year

                    # Mapeia semestre para meses
                    meses_semestre = {
                        1: ['01', '02', '03', '04', '05', '06'],
                        2: ['07', '08', '09', '10', '11', '12']
                    }

                    meses = meses_semestre[semestre]
                    result["ano"] = str(year)
                    result["meses"] = meses  # Lista de meses do semestre
                    result["semestre"] = semestre

                    # Calcula data_inicio e data_fim do semestre
                    primeiro_mes = int(meses[0])
                    ultimo_mes = int(meses[-1])

                    data_inicio = datetime(year, primeiro_mes, 1, tzinfo=TZ_SP)
                    data_fim_temp = datetime(year, ultimo_mes, 1, tzinfo=TZ_SP)
                    data_fim = data_fim_temp + relativedelta(months=1) - timedelta(days=1)

                    result["data_inicio"] = DateParser.format_yyyymmdd(data_inicio)
                    result["data_fim"] = DateParser.format_yyyymmdd(data_fim)

                    logger.debug(f"Parseado semestre {semestre}/{year}: meses={meses}, data_inicio={result['data_inicio']}, data_fim={result['data_fim']}")
                    return result

        logger.warning(f"Não foi possível parsear data: {text}")
        return None


# Instância global
date_parser = DateParser()
