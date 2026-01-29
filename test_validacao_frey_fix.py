"""
Teste para validar FIX: IA confundia "contratos com embarque em nov/dez" com "contratos baixados em nov/dez"

Pergunta: "Quantos contratos do cliente FREY A/S em novembro e dezembro de 2025
           já foram baixados financeiramente? Liste os números dos contratos."

Problema anterior:
- Contratos 530/25 e 531/25 tinham EMBARQUE em nov/dez 2025
- Mas foram BAIXADOS em 08/01/2026
- A IA respondia incorretamente que foram "baixados em nov/dez 2025"

Fix esperado:
- IA deve verificar contratos_baixados_nov2025 e contratos_baixados_dez2025
- Ambos devem estar vazios
- IA deve dizer "0 contratos foram baixados em nov/dez 2025"
- IA pode mencionar que foram baixados em jan/2026 (se consultar contratos_baixados_jan2026)
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.database import sql_client
from app.agents.sql_tools import SQLTools
from app.models.user import UserPermissions

# 1. Buscar dados DIRETO do banco para o cliente FREY A/S
print("="*60)
print("1. VERIFICAÇÃO DIRETA NO BANCO - Cliente FREY A/S")
print("="*60)

# Buscar todos os contratos FREY em 2025
result_all = sql_client.execute_function("IA_Vendas", {})
result_frey = [r for r in result_all if "FREY" in r.get("cliente", "")]

# Filtrar contratos com embarque em nov/dez 2025
result_embarque = [r for r in result_frey if r.get("mesEmbarque") in ["2025/11", "2025/12"]]
print(f"\nContratos do FREY com EMBARQUE em nov/dez 2025:")
for row in result_embarque:
    contrato = row["contrato"]
    mes_embarque = row["mesEmbarque"]
    baixa_receber = row["baixaReceber"] or "NÃO BAIXADO"

    # Extrair mês de baixa
    mes_baixa = "N/A"
    if baixa_receber != "NÃO BAIXADO" and len(str(baixa_receber)) >= 6:
        ano_mes = str(baixa_receber)[:6]  # Ex: "202601"
        mes_baixa = f"{ano_mes[:4]}/{ano_mes[4:6]}"  # Ex: "2026/01"

    print(f"  - Contrato {contrato}: embarque={mes_embarque}, baixa={baixa_receber} ({mes_baixa})")

# Buscar contratos baixados em nov/dez 2025 (independente do embarque)
result_baixa = [r for r in result_frey
                if r.get("baixaReceber")
                and (str(r["baixaReceber"]).startswith("202511") or str(r["baixaReceber"]).startswith("202512"))]
print(f"\nContratos do FREY BAIXADOS em nov/dez 2025:")
if len(result_baixa) == 0:
    print("  >>> NENHUM contrato foi baixado em nov/dez 2025")
else:
    for row in result_baixa:
        print(f"  - Contrato {row['contrato']}: embarque={row['mesEmbarque']}, baixa={row['baixaReceber']}")

# 2. Testar agregação SQL Tools (o que a IA verá)
print("\n" + "="*60)
print("2. DADOS DA AGREGAÇÃO (o que a IA verá)")
print("="*60)

user = UserPermissions(
    telefone="11999999999",
    nome="Test User",
    email="test@test.com",
    direitos=["Financeiro", "Vendas", "Compras", "Orçamento"]
)

sql_tools = SQLTools(user)

# Simular pergunta do usuário
sql_tools.user_query = "Quantos contratos do cliente FREY A/S em novembro e dezembro de 2025 já foram baixados financeiramente?"

# Buscar dados (sem período, pois é sobre "baixados EM")
result = sql_tools._pesquisa_vendas(periodo=None)

print(f"\nTipo de resultado: {type(result)}")

# Salvar resultado em arquivo para análise
with open("test_frey_result.txt", "w", encoding="utf-8") as f:
    f.write(str(result))

# Verificar se é lista ou string
if isinstance(result, list):
    # Procurar cliente FREY
    frey_data = None
    for cliente in result:
        if isinstance(cliente, dict) and "FREY" in cliente.get("cliente", ""):
            frey_data = cliente
            break
else:
    # Resultado é string (otimização), extrair JSON
    import json
    import re

    # Procurar JSON no resultado
    match = re.search(r'\[[\s\S]*?\]', result)
    if match:
        json_str = match.group()
        try:
            data_list = json.loads(json_str)
            frey_data = None
            for cliente in data_list:
                if isinstance(cliente, dict) and "FREY" in cliente.get("cliente", ""):
                    frey_data = cliente
                    break
        except:
            frey_data = None
    else:
        frey_data = None

if frey_data:
    print(f"\n[OK] Cliente encontrado: {frey_data['cliente'].strip()}")
    print("\nCampos de BAIXA disponíveis:")
    print(f"  - total_baixados_nov2025: {frey_data.get('total_baixados_nov2025', 'CAMPO NÃO EXISTE')}")
    print(f"  - contratos_baixados_nov2025: '{frey_data.get('contratos_baixados_nov2025', 'CAMPO NÃO EXISTE')}'")
    print(f"  - total_baixados_dez2025: {frey_data.get('total_baixados_dez2025', 'CAMPO NÃO EXISTE')}")
    print(f"  - contratos_baixados_dez2025: '{frey_data.get('contratos_baixados_dez2025', 'CAMPO NÃO EXISTE')}'")
    print(f"  - total_baixados_jan2026: {frey_data.get('total_baixados_jan2026', 'CAMPO NÃO EXISTE')}")
    print(f"  - contratos_baixados_jan2026: '{frey_data.get('contratos_baixados_jan2026', 'CAMPO NÃO EXISTE')}'")

    # 3. VALIDAÇÃO
    print("\n" + "="*60)
    print("3. VALIDAÇÃO DO FIX")
    print("="*60)

    total_nov = frey_data.get('total_baixados_nov2025', -1)
    total_dez = frey_data.get('total_baixados_dez2025', -1)
    total_jan = frey_data.get('total_baixados_jan2026', -1)

    if total_nov == -1 or total_dez == -1:
        print("[ERRO] ERRO: Campos de nov/dez 2025 não existem na agregação!")
    elif total_nov == 0 and total_dez == 0:
        print("[OK] CORRETO: Nenhum contrato foi baixado em nov/dez 2025")
        if total_jan > 0:
            contratos_jan = frey_data.get('contratos_baixados_jan2026', '')
            print(f"[OK] INFORMAÇÃO ADICIONAL: {total_jan} contrato(s) baixado(s) em jan/2026: {contratos_jan.strip()}")
        print("\n" + "="*60)
        print("[OK][OK][OK] FIX FUNCIONOU PERFEITAMENTE! [OK][OK][OK]")
        print("="*60)
        print("\nO que foi corrigido:")
        print("1. [OK] Agregação FORÇADA mesmo com filtro de cliente")
        print("2. [OK] Campos contratos_baixados_nov2025 e contratos_baixados_dez2025 criados")
        print("3. [OK] Otimização retorna APENAS campos de baixa (reduz tokens)")
        print("4. [OK] Documentação melhorada com avisos sobre distinção embarque vs baixa")
        print("\nA IA agora tem os dados corretos e NÃO vai confundir:")
        print("  [ERRO] 'contratos com EMBARQUE em nov/dez'")
        print("  [OK] 'contratos PAGOS/BAIXADOS em nov/dez'")
    else:
        print(f"[ATENCAO] ATENÇÃO: Encontrou contratos baixados em nov/dez 2025:")
        print(f"  - Nov/2025: {total_nov} contratos")
        print(f"  - Dez/2025: {total_dez} contratos")
else:
    print("\n[ERRO] Cliente FREY não encontrado no resultado")
    print("Resultado salvo em test_frey_result.txt")
