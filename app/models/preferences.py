"""
Modelos de preferências do usuário
"""
from pydantic import BaseModel
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime


# Tipos literais para validação
NivelDetalhe = Literal["resumido", "medio", "detalhado", "muito_detalhado"]
TomDeVoz = Literal["profissional", "casual", "tecnico", "executivo"]
FormatoResposta = Literal["texto", "bullet_points", "tabular", "narrativo"]
FormatoMoeda = Literal["BRL", "USD", "EUR"]
FormatoData = Literal["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"]


class UserPreferences(BaseModel):
    """Modelo de preferências do usuário"""

    # Identificação
    telefone: str
    nome: Optional[str] = None
    email: Optional[str] = None

    # Preferências de Comunicação
    nivel_detalhe: NivelDetalhe = "medio"
    tom_de_voz: TomDeVoz = "profissional"
    formato_resposta: FormatoResposta = "texto"

    # Preferências de Formatação
    formato_moeda: FormatoMoeda = "BRL"
    formato_data: FormatoData = "DD/MM/YYYY"
    emojis_habilitados: bool = True

    # Personalização de Mensagens
    saudacao_customizada: Optional[str] = None
    assinatura_customizada: Optional[str] = None

    # Contexto de Negócio
    areas_interesse: List[str] = []
    metricas_favoritas: List[str] = []

    # Preferências Avançadas
    instrucoes_adicionais: Optional[str] = None

    # Metadata de Aprendizado
    learning_history: List[Dict[str, Any]] = []
    confidence_score: float = 0.5
    feedback_count: int = 0
    last_feedback_at: Optional[datetime] = None

    def get_custom_instructions(self) -> str:
        """
        Gera instruções customizadas para injetar no prompt

        Returns:
            String com instruções formatadas
        """
        instructions = []

        # Tom de voz
        tom_mapping = {
            "profissional": "Use tom formal, profissional e executivo. Seja preciso e direto.",
            "casual": "Use tom casual, amigável e direto. Seja objetivo sem formalidades excessivas.",
            "tecnico": "Use linguagem técnica e detalhada. Inclua metodologias e análises aprofundadas.",
            "executivo": "Seja extremamente conciso e focado em insights estratégicos. Priorize decisões."
        }
        instructions.append(tom_mapping.get(self.tom_de_voz, ""))

        # Nível de detalhe
        detalhe_mapping = {
            "resumido": "Respostas MUITO breves (máximo 3 linhas). Apenas números-chave e insights principais.",
            "medio": "Respostas moderadas (5-8 linhas). Balance entre dados e contexto.",
            "detalhado": "Respostas completas (10-15 linhas). Inclua contexto, análises e comparativos.",
            "muito_detalhado": "Respostas extensas e profundas. Inclua todas as nuances, metodologias e insights."
        }
        instructions.append(detalhe_mapping.get(self.nivel_detalhe, ""))

        # Formato de resposta
        formato_mapping = {
            "texto": "Apresente em formato de texto corrido, bem estruturado.",
            "bullet_points": "SEMPRE use bullet points (•) e tópicos para organizar informações.",
            "tabular": "Organize dados em formato tabular quando possível. Use alinhamento claro.",
            "narrativo": "Use narrativa fluida e storytelling. Conecte dados com contexto de negócio."
        }
        instructions.append(formato_mapping.get(self.formato_resposta, ""))

        # Emojis
        if self.emojis_habilitados:
            instructions.append("Use emojis moderadamente para tornar resposta mais amigável (máximo 2-3 por mensagem).")
        else:
            instructions.append("NÃO use emojis. Mantenha linguagem totalmente profissional e formal.")

        # Saudação
        if self.saudacao_customizada:
            instructions.append(f"Sempre inicie respostas com: '{self.saudacao_customizada}'")

        # Instruções adicionais
        if self.instrucoes_adicionais:
            instructions.append(f"Instruções especiais: {self.instrucoes_adicionais}")

        return "\n\n".join(instructions)

    def get_summary(self) -> str:
        """Retorna resumo das preferências"""
        return f"""Preferências atuais:
- Tom: {self.tom_de_voz}
- Detalhamento: {self.nivel_detalhe}
- Formato: {self.formato_resposta}
- Emojis: {'Sim' if self.emojis_habilitados else 'Não'}
- Aprendizados: {self.feedback_count} ajustes
- Confiança: {self.confidence_score:.0%}"""


class FeedbackDetection(BaseModel):
    """Resultado da detecção de feedback"""
    tipo: str  # nivel_detalhe, tom_de_voz, formato_resposta, emojis_habilitados
    valor: str  # novo valor
    confianca: float  # 0-1
    deve_aplicar: bool
    pattern_matched: Optional[str] = None
    explicacao: Optional[str] = None
    reprocess_last: bool = False  # Se deve reprocessar última resposta
