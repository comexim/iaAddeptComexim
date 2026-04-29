# 🔍 Resolução Automática de Campos (Descrição → Código)

## 📋 **Visão Geral**

Esta funcionalidade permite que o usuário informe **descrições** em vez de **códigos**, e o sistema automaticamente converte para o código correto consultando a API F3.

**Exemplo:**
- ❌ **Antes**: Usuário precisava saber que "pallet com alpha bag" = código `00304`
- ✅ **Agora**: Usuário diz "pallet com alpha bag" e o sistema encontra o código automaticamente

---

## 🔄 **Como Funciona**

### **1. Usuário Informa Descrição**
```
👤 "Embalagem de pallet com 2 alpha bag gramatura 190gr"
```

### **2. Sistema Detecta que Não é Código**
O sistema verifica se o valor parece ser um código:
- Só números? → É código
- Curto (< 10 chars) sem espaços? → Provavelmente código
- Texto descritivo? → Precisa resolver

### **3. Sistema Consulta API F3**
```http
GET http://200.221.173.187:8085/rest/ia/api/wsgetF3/v1/consulta
Authorization: Bearer <token>
Content-Type: application/json

{
  "consulta": "codigoEmbalagem",
  "filtro": ""
}
```

**Resposta:**
```json
{
  "code": "201",
  "message": "Consulta realizada com sucesso.",
  "registros": [
    {
      "codigo": "00304",
      "descricao": "1 PALLET + 2 ALPHA BAG COM GRAMATURA 190GR"
    },
    {
      "codigo": "00345",
      "descricao": "1 PALLET + 2 ALPHA BAG COM GRAMATURA 190GR -59 KG"
    }
  ]
}
```

### **4. Sistema Faz Matching Fuzzy**
Usa algoritmo de similaridade (`rapidfuzz`) para encontrar a descrição mais parecida:
- Compara "pallet com 2 alpha bag gramatura 190gr"
- Com cada descrição do banco
- Calcula score de similaridade (0-100%)
- Aceita se score >= 70%

**Resultado:**
```
✅ Match encontrado: "1 PALLET + 2 ALPHA BAG COM GRAMATURA 190GR"
   Score: 92.5%
   Código: 00304
```

### **5. Sistema Usa Código no Contrato**
O código `00304` é usado automaticamente no campo `codigoEmbalagem` do contrato.

---

## 📁 **Arquivos Modificados/Criados**

### **1. `app/core/ada_api_client.py`**
**Adicionado método:**
```python
async def consultar_campo(self, nome_campo: str, filtro: str = "") -> Dict[str, Any]:
    """Consulta valores possíveis para um campo via API F3"""
    # GET /rest/ia/api/wsgetF3/v1/consulta
    # Retorna: {"code": "201", "registros": [...]}
```

### **2. `app/utils/field_resolver.py` (NOVO)**
**Classe principal:**
```python
class FieldResolver:
    # Mapeamento de campos Python → API
    FIELD_MAPPING = {
        "codigo_embalagem": "codigoEmbalagem",
        "codigo_cliente": "codigoCliente",
        "padrao_qualidade": "padraoQualidade",
        ...
    }
    
    async def resolve_field(field_name: str, user_input: str) -> str:
        """Resolve descrição para código"""
        # 1. Verifica se já é código
        # 2. Consulta API F3
        # 3. Faz matching fuzzy
        # 4. Retorna código ou valor original
```

**Recursos:**
- ✅ Cache de consultas (evita chamadas repetidas)
- ✅ Matching fuzzy com score configurável
- ✅ Fallback para valor original se não encontrar match
- ✅ Detecção automática de códigos (não consulta se já for código)

### **3. `app/agents/ada_tools.py`**
**Modificado:**
- Adicionado import: `from app.utils.field_resolver import field_resolver`
- Adicionada seção de resolução de campos antes das validações:

```python
# 2.5. RESOLUÇÃO DE CAMPOS - converte descrições em códigos via API F3
if current and not esta_confirmando_explicito:
    campos_para_resolver = [
        "codigo_embalagem",
        "codigo_cliente", 
        "padrao_qualidade",
        "modalidade_pagamento",
        "condicao_entrega",
        "moeda_fixacao",
        "tipo_contrato",
        "condicao_peso"
    ]
    
    for campo in campos_para_resolver:
        if campo in current:
            valor_resolvido = await field_resolver.resolve_field(campo, str(current[campo]))
            if valor_resolvido != current[campo]:
                current[campo] = valor_resolvido  # Substitui pela versão resolvida
```

### **4. `requirements.txt`**
**Adicionado:**
```txt
rapidfuzz>=3.0.0,<4.0.0  # Biblioteca de fuzzy matching rápida
```

### **5. `test_field_resolver.py` (NOVO)**
Testes automatizados da funcionalidade:
- Teste de conexão
- Teste de consulta
- Teste de matching
- Teste de fluxo completo

---

## 🎯 **Campos Suportados**

Os seguintes campos são automaticamente resolvidos:

| Campo Python | Campo API | Exemplo de Entrada |
|--------------|-----------|-------------------|
| `codigo_embalagem` | `codigoEmbalagem` | "pallet com alpha bag" |
| `codigo_cliente` | `codigoCliente` | "Nestlé" |
| `padrao_qualidade` | `padraoQualidade` | "premium" |
| `modalidade_pagamento` | `modalidadePagamento` | "à vista" |
| `condicao_entrega` | `condicaoEntrega` | "FOB" |
| `moeda_fixacao` | `moedaFixacao` | "dólar" |
| `tipo_contrato` | `tipoContrato` | "exportação" |
| `condicao_peso` | `condicaoPeso` | "net weight" |

---

## 🔧 **Como Usar**

### **Instalação**
```bash
# Instalar nova dependência
pip install rapidfuzz

# Ou instalar todas
pip install -r requirements.txt
```

### **Teste Manual**
```bash
# Executar testes
python test_field_resolver.py
```

### **Teste no Fluxo Real**
```python
# Usuário conversa com o agente
👤 "Quero criar um contrato"
🤖 "Qual a embalagem?"
👤 "Pallet com 2 alpha bag de 190 gramas"
🤖 [Sistema resolve automaticamente para código 00304]
    "Embalagem registrada! Qual a quantidade em KG?"
```

---

## ⚙️ **Configuração**

### **Threshold de Similaridade**
Por padrão, aceita match com score >= 70%. Para ajustar:

```python
# Em field_resolver.py
await field_resolver.resolve_field(
    field_name="codigo_embalagem",
    user_input="pallet alpha bag",
    threshold=80  # Mais restritivo (padrão: 70)
)
```

### **Cache**
O cache é automático e dura enquanto o processo estiver rodando. Para limpar:

```python
from app.utils.field_resolver import field_resolver

# Limpa cache manualmente
field_resolver.clear_cache()
```

---

## 🚀 **Melhorias Futuras**

- [ ] Suporte a filtros específicos na consulta
- [ ] Múltiplas opções quando score é similar (perguntar ao usuário)
- [ ] Logs detalhados de conversões para auditoria
- [ ] API de feedback para melhorar matching
- [ ] Suporte a sinônimos personalizados

---

## 📊 **Exemplo de Log**

```
[ADA TOOL] 🔍 Iniciando resolução de campos (conversão descrição → código)...
[RESOLVER] Resolvendo 'codigo_embalagem': 'pallet com 2 alpha bag gramatura 190gr'
[ADA API] Consultando campo 'codigoEmbalagem' com filtro ''...
[ADA API] ✅ Consulta realizada: 45 registro(s) encontrado(s)
[RESOLVER] ✅ Match encontrado: '1 PALLET + 2 ALPHA BAG COM GRAMATURA 190GR' (score: 92.5%) → código: 00304
[ADA TOOL] ✅ Campo 'codigo_embalagem' resolvido: 'pallet com 2 alpha bag gramatura 190gr' → '00304'
```

---

## 🐛 **Troubleshooting**

### **Erro: "Nenhum match encontrado"**
- Verifique se a descrição está correta
- Tente abaixar o threshold (padrão: 70%)
- Consulte manualmente a API para ver as opções disponíveis

### **Erro: "Erro ao consultar API"**
- Verifique se o token OAuth2 está válido
- Verifique conectividade com a API
- Veja logs detalhados em `[ADA API]`

### **Campo não está sendo resolvido**
- Verifique se o campo está em `FIELD_MAPPING` em `field_resolver.py`
- Adicione o campo se necessário

---

## ✅ **Conclusão**

A funcionalidade de resolução automática torna o sistema muito mais user-friendly, permitindo que usuários usem linguagem natural sem precisar memorizar códigos técnicos.

**Benefícios:**
- ✅ Usuário não precisa saber códigos
- ✅ Menos erros de digitação
- ✅ Experiência mais natural
- ✅ Validação automática contra base de dados
