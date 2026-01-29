"""
Validar resposta: Quantos contratos NÃO foram embarcados e NÃO têm BL em janeiro de 2026?
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.agents.sql_tools import SQLTools
from app.models.user import UserPermissions
from dotenv import load_dotenv
import json
import re

load_dotenv()

# Criar usuário com permissões
user = UserPermissions(
    telefone="teste",
    nome="Teste",
    email="teste@teste.com",
    direitos=["Vendas"],
    acesso_ia_vendas=True,
    acesso_ia_compras=True,
    acesso_ia_orcamento=True,
    acesso_ia_contas_a_pagar=True,
    acesso_ia_contas_a_receber=True,
    acesso_ia_saldo_bancario=True,
    acesso_ia_despesa_venda=True
)

# Criar tools
sql_tools = SQLTools(user)

print("=" * 80)
print("VALIDAÇÃO: Contratos NÃO embarcados e SEM BL em janeiro de 2026")
print("=" * 80)
print()

# Simular query original (para filtros)
query_original = "Quantos contratos não foram embarcados e não têm BL?"
sql_tools.user_query = query_original
sql_tools.user_query_original = query_original

print(f"Query: '{query_original}'")
print(f"Período: janeiro de 2026")
print()
print("=" * 80)
print()

# Chamar a tool
resultado = sql_tools._pesquisa_vendas(periodo="janeiro de 2026")

# Salvar resultado
with open("resultado_nao_embarcados_sem_bl.txt", "w", encoding="utf-8") as f:
    f.write(resultado)

print(f"Resultado salvo em: resultado_nao_embarcados_sem_bl.txt")
print()

# Analisar resultado
print("=" * 80)
print("ANÁLISE DOS DADOS:")
print("=" * 80)
print()

# Tentar extrair dados JSON
try:
    # Procurar por dados JSON no resultado
    if '"contrato":' in resultado or '"numeroContrato":' in resultado:
        # Formato não agregado (lista de contratos)
        # Extrair cada contrato
        contratos = []

        # Dividir por linhas e processar
        lines = resultado.split('\n')
        current_contract = {}

        for line in lines:
            if '"contrato":' in line or '"numeroContrato":' in line:
                if current_contract:
                    contratos.append(current_contract)
                    current_contract = {}

                # Extrair número do contrato
                match = re.search(r'"(?:contrato|numeroContrato)":\s*"([^"]+)"', line)
                if match:
                    current_contract['contrato'] = match.group(1)

            if '"cliente":' in line:
                match = re.search(r'"cliente":\s*"([^"]+)"', line)
                if match:
                    current_contract['cliente'] = match.group(1)

            if '"saidaNavio":' in line:
                match = re.search(r'"saidaNavio":\s*"([^"]*)"', line)
                if match:
                    current_contract['saidaNavio'] = match.group(1) if match.group(1) else None

            if '"numeroBL":' in line:
                match = re.search(r'"numeroBL":\s*"([^"]*)"', line)
                if match:
                    current_contract['numeroBL'] = match.group(1) if match.group(1) else None

        if current_contract:
            contratos.append(current_contract)

        print(f"Total de contratos retornados: {len(contratos)}")
        print()

        # Classificar contratos
        nao_embarcados_sem_bl = []
        nao_embarcados_com_bl = []
        embarcados_sem_bl = []
        embarcados_com_bl = []

        for c in contratos:
            tem_saida = c.get('saidaNavio') and str(c.get('saidaNavio')).strip() != ""
            tem_bl = c.get('numeroBL') and str(c.get('numeroBL')).strip() != ""

            if not tem_saida and not tem_bl:
                nao_embarcados_sem_bl.append(c)
            elif not tem_saida and tem_bl:
                nao_embarcados_com_bl.append(c)
            elif tem_saida and not tem_bl:
                embarcados_sem_bl.append(c)
            else:
                embarcados_com_bl.append(c)

        print("CLASSIFICAÇÃO DOS CONTRATOS:")
        print()
        print(f"1. NÃO embarcados e SEM BL: {len(nao_embarcados_sem_bl)} contratos")
        if nao_embarcados_sem_bl:
            print("   Primeiros 5:")
            for i, c in enumerate(nao_embarcados_sem_bl[:5], 1):
                print(f"      {i}. {c.get('contrato', 'N/A')} ({c.get('cliente', 'N/A')})")
        print()

        print(f"2. NÃO embarcados mas COM BL: {len(nao_embarcados_com_bl)} contratos")
        if nao_embarcados_com_bl:
            print("   Primeiros 5:")
            for i, c in enumerate(nao_embarcados_com_bl[:5], 1):
                print(f"      {i}. {c.get('contrato', 'N/A')} ({c.get('cliente', 'N/A')})")
        print()

        print(f"3. EMBARCADOS mas SEM BL: {len(embarcados_sem_bl)} contratos")
        if embarcados_sem_bl:
            print("   Primeiros 5:")
            for i, c in enumerate(embarcados_sem_bl[:5], 1):
                print(f"      {i}. {c.get('contrato', 'N/A')} ({c.get('cliente', 'N/A')})")
        print()

        print(f"4. EMBARCADOS e COM BL: {len(embarcados_com_bl)} contratos")
        print()

        # Comparar com resposta da IA
        print("=" * 80)
        print("COMPARAÇÃO COM RESPOSTA DA IA:")
        print("=" * 80)
        print()
        print("IA respondeu: '7 contratos que foram embarcados, mas não possuem BL'")
        print()

        if len(embarcados_sem_bl) == 7:
            print("[X] A IA contou EMBARCADOS sem BL")
            print(f"    Valor: {len(embarcados_sem_bl)} contratos")
            print()
            print("MAS a pergunta foi sobre NÃO EMBARCADOS sem BL!")
            print()
            if len(nao_embarcados_sem_bl) > 0:
                print(f"[ERRO] Valor CORRETO deveria ser: {len(nao_embarcados_sem_bl)} contratos")
                print()
                print("Primeiros 5 contratos CORRETOS:")
                for i, c in enumerate(nao_embarcados_sem_bl[:5], 1):
                    print(f"  {i}. {c.get('contrato', 'N/A')} ({c.get('cliente', 'N/A')})")
            else:
                print("[OK] Não há contratos NÃO embarcados sem BL")
        else:
            print(f"[?] IA respondeu 7, mas encontramos {len(embarcados_sem_bl)} embarcados sem BL")

        print()
        print("=" * 80)
        print("DIAGNÓSTICO:")
        print("=" * 80)
        print()

        # Verificar se houve inversão de lógica
        pergunta_lower = query_original.lower()
        if "não foram embarcados" in pergunta_lower or "nao foram embarcados" in pergunta_lower:
            print("[DETECTADO] Pergunta contém 'NÃO foram embarcados'")
            print()
            if len(embarcados_sem_bl) == 7:
                print("[ERRO CRÍTICO] IA inverteu a lógica!")
                print("   Perguntado: NÃO embarcados sem BL")
                print("   Respondeu: EMBARCADOS sem BL")
                print()
                print(f"   Valor CORRETO: {len(nao_embarcados_sem_bl)} contratos (NÃO embarcados sem BL)")
                print(f"   Valor ERRADO:  7 contratos (EMBARCADOS sem BL)")
            else:
                print("[OK] Resposta parece estar correta")

    else:
        print("[X] Não consegui extrair dados estruturados do resultado")
        print("Resultado:")
        print(resultado[:500])

except Exception as e:
    print(f"[ERRO] Erro ao processar resultado: {e}")
    import traceback
    traceback.print_exc()
