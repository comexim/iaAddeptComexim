"""
Cliente SQL Server para consultas no banco de dados Protheus
"""
import pyodbc
import logging
from typing import List, Dict, Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class SQLServerClient:
    """Cliente para executar stored functions no SQL Server"""

    def __init__(self):
        self.connection_string = settings.sql_server_connection_string

    def _get_connection(self) -> pyodbc.Connection:
        """Cria uma NOVA conexão para cada query (evita problemas de concorrência)"""
        try:
            logger.debug("Criando nova conexão com SQL Server...")
            connection = pyodbc.connect(
                self.connection_string,
                timeout=30
            )
            logger.debug("Conexão estabelecida com sucesso")
            return connection
        except pyodbc.Error as e:
            logger.error(f"Erro ao conectar no SQL Server: {e}")
            raise

    def execute_function(
        self,
        function_name: str,
        filters: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Executa stored function e retorna resultados

        Args:
            function_name: Nome da função (ex: IA_Vendas)
            filters: Parâmetros da função OU filtros WHERE
                    - Se a chave começar com @ ou for um parâmetro conhecido, passa como parâmetro da função
                    - Caso contrário, usa como filtro WHERE no resultado
            timeout: Timeout em segundos

        Returns:
            Lista de dicionários com resultados
        """
        # Parâmetros que devem ser passados PARA a função (não como WHERE)
        FUNCTION_PARAMETERS = {
            "IA_Vendas": [],  # Vendas NÃO aceita parâmetros, mesEmbarque vai no WHERE
            "IA_Compras": [],  # Compras NÃO aceita parâmetros, emissao vai no WHERE
            "IA_ContasPagas": [],  # Contas Pagas NÃO aceita parâmetros, emissao vai no WHERE
            "IA_ContasAPagar": [],  # Contas a Pagar NÃO aceita parâmetros, vencimento vai no WHERE
            "IA_ContasAReceber": [],  # Contas a Receber NÃO aceita parâmetros, vencimentoReal vai no WHERE
            "IA_Orcamento": [],  # Orçamento NÃO aceita parâmetros, ano/mes vão no WHERE
            "IA_Cotacao": [],  # Cotação NÃO aceita parâmetros
            "IA_DespesaVenda": []  # Despesa Venda NÃO aceita parâmetros, contrato vai no WHERE
        }

        # Campos que devem usar >= ao invés de =
        FIELDS_USING_GTE = ["emissao", "vencimento", "vencimentoReal"]

        function_params = []
        where_filters = {}

        if filters:
            known_params = FUNCTION_PARAMETERS.get(function_name, [])

            for key, value in filters.items():
                if value is None:
                    continue

                # Se for parâmetro conhecido da função, adiciona aos parâmetros
                if key in known_params or key.startswith("@"):
                    if isinstance(value, str):
                        escaped_value = value.replace("'", "''")
                        function_params.append(f"'{escaped_value}'")
                    elif isinstance(value, (int, float)):
                        function_params.append(str(value))
                    else:
                        function_params.append(f"'{value}'")
                else:
                    # Caso contrário, usa como filtro WHERE
                    where_filters[key] = value

        # Monta query com parâmetros na função (posicionais, sem nomes)
        if function_params:
            query = f"SELECT * FROM {function_name}({', '.join(function_params)})"
        else:
            query = f"SELECT * FROM {function_name}()"

        # Adiciona cláusula WHERE se houver filtros adicionais
        if where_filters:
            where_clauses = []
            for key, value in where_filters.items():
                # TRATAMENTO ESPECIAL: Lista de valores (trimestres/semestres)
                if isinstance(value, list):
                    # Para listas, usa IN (...) ao invés de =
                    if all(isinstance(v, str) for v in value):
                        # Lista de strings (meses)
                        escaped_values = [v.replace("'", "''") for v in value]
                        values_str = ", ".join([f"'{v}'" for v in escaped_values])
                        where_clauses.append(f"{key} IN ({values_str})")
                    else:
                        # Lista de números
                        values_str = ", ".join([str(v) for v in value])
                        where_clauses.append(f"{key} IN ({values_str})")
                    logger.debug(f"Filtro com lista: {key} IN ({values_str})")

                # TRATAMENTO ESPECIAL: Se termina com _fim, cria filtro <=
                elif key.endswith("_fim"):
                    # Remove sufixo _fim para pegar nome real do campo
                    field_name = key[:-4]  # Remove '_fim'
                    operator = "<="

                    if isinstance(value, str):
                        escaped_value = value.replace("'", "''")
                        where_clauses.append(f"{field_name} {operator} '{escaped_value}'")
                    elif isinstance(value, (int, float)):
                        where_clauses.append(f"{field_name} {operator} {value}")
                    else:
                        where_clauses.append(f"{field_name} {operator} '{value}'")
                else:
                    # Determina o operador: >= para campos de data, = para outros
                    operator = ">=" if key in FIELDS_USING_GTE else "="

                    if isinstance(value, str):
                        escaped_value = value.replace("'", "''")
                        where_clauses.append(f"{key} {operator} '{escaped_value}'")
                    elif isinstance(value, (int, float)):
                        where_clauses.append(f"{key} {operator} {value}")
                    else:
                        where_clauses.append(f"{key} {operator} '{value}'")

            if where_clauses:
                query += " WHERE " + " AND ".join(where_clauses)

        logger.info(f"Executando query: {query}")

        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(query)

            # Obtém nomes das colunas
            columns = [column[0] for column in cursor.description]

            # Converte resultados para lista de dicionários
            results = []
            for row in cursor.fetchall():
                row_dict = {}
                for i, column in enumerate(columns):
                    value = row[i]
                    # Converte tipos específicos para JSON-serializáveis
                    if hasattr(value, 'isoformat'):  # datetime/date
                        value = value.isoformat()
                    row_dict[column] = value
                results.append(row_dict)

            logger.info(f"Query executada com sucesso. {len(results)} registros retornados.")
            return results

        except pyodbc.Error as e:
            logger.error(f"Erro ao executar query: {e}")
            logger.error(f"Query: {query}")
            raise Exception(f"Erro ao consultar banco de dados: {str(e)}")

        finally:
            # CRÍTICO: Fechar cursor e conexão para evitar "Connection is busy"
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                    logger.debug("Conexão fechada")
                except:
                    pass

    def test_connection(self) -> bool:
        """Testa conexão com o banco"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            logger.info("Teste de conexão bem-sucedido")
            return True
        except Exception as e:
            logger.error(f"Teste de conexão falhou: {e}")
            return False
        finally:
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass

    def close(self):
        """
        Método mantido para compatibilidade, mas não faz nada.
        Agora cada query cria e fecha sua própria conexão automaticamente.
        """
        pass


# Instância global do cliente
sql_client = SQLServerClient()
