"""Testa o split inteligente de código e loja de agentes"""
import re

test_cases = [
    # (input, expected_codigo, expected_loja)
    ("07889486 0001", "07889486", "0001"),  # Com espaço - 4 dígitos
    ("10275242 0001", "10275242", "0001"),  # Com espaço - 4 dígitos
    ("IMPS000240001", "IMPS00024", "0001"),  # Sem espaço - 4 dígitos
    ("IMPS0001W0001", "IMPS0001W", "0001"),  # Sem espaço - 4 dígitos
    ("JS00000300001", "JS000003", "00001"),  # Sem espaço - 5 dígitos
    ("JS0000010001", "JS00001", "0001"),     # Sem espaço - 4 dígitos
    ("INPS000300001", "INPS00030", "0001"),  # Sem espaço - 4 dígitos
]

print("=" * 70)
print("TESTE DE SPLIT: Código e Loja de Agentes")
print("=" * 70)
print()

passed = 0
failed = 0

for codigo_resolvido, expected_codigo, expected_loja in test_cases:
    # Tenta primeiro com espaço (padrão mais comum)
    match_espaco = re.match(r'^(.+)\s+(\d{4,5})$', codigo_resolvido.strip())
    if match_espaco:
        codigo_agente = match_espaco.group(1)
        loja_agente = match_espaco.group(2)
        metodo = "COM ESPAÇO"
    else:
        # Sem espaço - tenta identificar últimos 4 dígitos como loja (padrão mais comum)
        # Usa greedy .+ para capturar o máximo possível no código
        match_sem_espaco = re.match(r'^(.+)(\d{4})$', codigo_resolvido.strip())
        if match_sem_espaco:
            codigo_agente = match_sem_espaco.group(1)
            loja_agente = match_sem_espaco.group(2)
            metodo = "SEM ESPAÇO (4 dígitos)"
        else:
            # Não conseguiu identificar padrão
            codigo_agente = codigo_resolvido
            loja_agente = "0001"
            metodo = "FALLBACK"
    
    # Verifica se passou
    if codigo_agente == expected_codigo and loja_agente == expected_loja:
        print(f"✅ PASSOU: '{codigo_resolvido}'")
        print(f"   Método: {metodo}")
        print(f"   Código: {codigo_agente} | Loja: {loja_agente}")
        passed += 1
    else:
        print(f"❌ FALHOU: '{codigo_resolvido}'")
        print(f"   Método: {metodo}")
        print(f"   Obtido:   codigo='{codigo_agente}', loja='{loja_agente}'")
        print(f"   Esperado: codigo='{expected_codigo}', loja='{expected_loja}'")
        failed += 1
    print()

print("=" * 70)
print(f"RESULTADO: {passed} passaram, {failed} falharam")
print("=" * 70)
