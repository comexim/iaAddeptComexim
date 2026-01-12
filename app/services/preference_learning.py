"""
Sistema de aprendizado adaptativo de preferências do usuário
"""
from typing import Optional, Dict, List
import re
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import settings
from app.core.supabase_client import supabase_client
from app.models.preferences import UserPreferences, FeedbackDetection


# Padrões de feedback detectáveis via regex (alta confiança)
FEEDBACK_PATTERNS = {
    "nivel_detalhe": [
        # Pedir menos detalhes
        (r"(diminua|reduza|encurta|resume|seja mais breve|mensagem menor)", "resumido", 0.9),
        (r"(muito (grande|longa?|extens[oa])|detalhes? demais)", "resumido", 0.85),

        # Pedir mais detalhes
        (r"(aument[ae]|expanda|detalhe mais|seja mais completo|mais informa)", "detalhado", 0.9),
        (r"(muito (curto|breve|resumid[oa])|faltou (detalhe|informa))", "detalhado", 0.85),

        # Médio (reset)
        (r"(m[eé]dio|normal|padr[aã]o|como antes)", "medio", 0.8),
    ],

    "tom_de_voz": [
        # Profissional/Formal
        (r"(seja mais (formal|profissional|s[eé]rio)|linguagem formal)", "profissional", 0.9),
        (r"(menos (informal|casual)|tire (emoji|smile))", "profissional", 0.85),

        # Casual
        (r"(seja mais (casual|informal|descontra[íi]d[oa])|menos formal)", "casual", 0.9),
        (r"(pode (relaxar|ser informal))", "casual", 0.85),

        # Técnico
        (r"(t[eé]cnic[oa]|metodologia|an[aá]lise (profunda|t[eé]cnica))", "tecnico", 0.9),

        # Executivo
        (r"(executiv[oa]|direto ao ponto|s[oó] o essencial|insight)", "executivo", 0.9),
    ],

    "formato_resposta": [
        # Bullet points
        (r"(bullet|t[oó]picos?|lista|pontua[dç][aã]o)", "bullet_points", 0.9),
        (r"(organiza em (itens|lista)|use (•|-))", "bullet_points", 0.85),

        # Tabular
        (r"(tabela|tabular|coluna)", "tabular", 0.9),

        # Narrativo
        (r"(narrativ[oa]|hist[oó]ria|contexto|storytelling)", "narrativo", 0.9),

        # Texto corrido
        (r"(texto corrido|par[aá]grafo|sem (bullet|t[oó]pico))", "texto", 0.85),
    ],

    "emojis_habilitados": [
        # Desabilitar emojis
        (r"(sem emoji|tire (os? )?emoji|n[aã]o (use|quero) emoji)", False, 0.95),
        (r"(mais formal|profissional)", False, 0.7),  # Inferência

        # Habilitar emojis
        (r"(com emoji|use emoji|pode usar emoji|coloca emoji)", True, 0.95),
        (r"(mais (descontra[íi]d[oa]|casual))", True, 0.7),  # Inferência
    ],
}


class PreferenceLearningSystem:
    """Sistema de aprendizado de preferências via detecção de feedback"""

    def __init__(self):
        """Inicializa sistema com LLM para detecções complexas"""
        if settings.llm_provider == "openai":
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",  # Modelo rápido para classificação
                temperature=0.0,
                api_key=settings.openai_api_key
            )
        else:
            self.llm = ChatAnthropic(
                model="claude-3-5-haiku-20241022",  # Modelo rápido
                temperature=0.0,
                api_key=settings.anthropic_api_key
            )

    async def detect_feedback(
        self,
        user_message: str,
        telefone: str
    ) -> List[FeedbackDetection]:
        """
        Detecta feedback sobre preferências na mensagem do usuário

        Args:
            user_message: Mensagem do usuário
            telefone: Telefone do usuário

        Returns:
            Lista de feedbacks detectados
        """
        feedbacks = []

        # 1. Detecção via regex (alta confiança, rápida)
        regex_feedbacks = self._detect_via_regex(user_message)
        feedbacks.extend(regex_feedbacks)

        # 2. Se regex não detectou nada OU confiança < 0.8, usa LLM
        if not feedbacks or max(f.confianca for f in feedbacks) < 0.8:
            llm_feedbacks = await self._detect_via_llm(user_message)
            feedbacks.extend(llm_feedbacks)

        # 3. Remove duplicatas (mantém maior confiança)
        feedbacks = self._deduplicate_feedbacks(feedbacks)

        return feedbacks

    def _detect_via_regex(self, message: str) -> List[FeedbackDetection]:
        """Detecta feedback usando padrões regex"""
        feedbacks = []
        message_lower = message.lower()

        for tipo, patterns in FEEDBACK_PATTERNS.items():
            for pattern, valor, confianca in patterns:
                if re.search(pattern, message_lower):
                    feedback = FeedbackDetection(
                        tipo=tipo,
                        valor=str(valor),
                        confianca=confianca,
                        deve_aplicar=confianca >= 0.8,
                        pattern_matched=pattern,
                        explicacao=f"Padrão regex detectado: {pattern}"
                    )
                    feedbacks.append(feedback)
                    break  # Usa apenas primeiro match por tipo

        return feedbacks

    async def _detect_via_llm(self, message: str) -> List[FeedbackDetection]:
        """Detecta feedback usando LLM (para casos ambíguos)"""

        prompt = f"""Analise se a mensagem do usuário contém FEEDBACK sobre preferências de comunicação.

Mensagem: "{message}"

Possíveis preferências detectáveis:
1. nivel_detalhe: "resumido", "medio", "detalhado", "muito_detalhado"
2. tom_de_voz: "profissional", "casual", "tecnico", "executivo"
3. formato_resposta: "texto", "bullet_points", "tabular", "narrativo"
4. emojis_habilitados: true, false

Retorne APENAS um JSON (sem markdown) com formato:
{{
  "feedbacks": [
    {{"tipo": "nivel_detalhe", "valor": "resumido", "confianca": 0.9, "explicacao": "..."}}
  ]
}}

Se NÃO houver feedback sobre preferências, retorne: {{"feedbacks": []}}

IMPORTANTE: Só detecte feedback EXPLÍCITO. Perguntas normais sobre dados NÃO são feedback."""

        try:
            response = await self.llm.ainvoke([
                SystemMessage(content="Você é um classificador de feedback sobre preferências de comunicação."),
                HumanMessage(content=prompt)
            ])

            import json
            result = json.loads(response.content.strip())

            feedbacks = []
            for fb in result.get("feedbacks", []):
                feedback = FeedbackDetection(
                    tipo=fb["tipo"],
                    valor=fb["valor"],
                    confianca=fb["confianca"],
                    deve_aplicar=fb["confianca"] >= 0.8,
                    pattern_matched="llm_detection",
                    explicacao=fb.get("explicacao", "Detectado via LLM")
                )
                feedbacks.append(feedback)

            return feedbacks

        except Exception as e:
            print(f"[ERRO] Falha ao detectar via LLM: {e}")
            return []

    def _deduplicate_feedbacks(
        self,
        feedbacks: List[FeedbackDetection]
    ) -> List[FeedbackDetection]:
        """Remove duplicatas mantendo maior confiança"""
        best_feedbacks: Dict[str, FeedbackDetection] = {}

        for fb in feedbacks:
            if fb.tipo not in best_feedbacks or fb.confianca > best_feedbacks[fb.tipo].confianca:
                best_feedbacks[fb.tipo] = fb

        return list(best_feedbacks.values())

    async def apply_feedback(
        self,
        telefone: str,
        feedback: FeedbackDetection
    ) -> bool:
        """
        Aplica feedback detectado atualizando preferências

        Args:
            telefone: Telefone do usuário
            feedback: Feedback detectado

        Returns:
            True se aplicado com sucesso
        """
        if not feedback.deve_aplicar:
            print(f"[INFO] Feedback com confiança baixa ({feedback.confianca:.0%}), não aplicado")
            return False

        try:
            # Converte string para tipo correto
            valor = feedback.valor
            if feedback.tipo == "emojis_habilitados":
                valor = valor.lower() == "true"

            # Atualiza no Supabase
            success = await supabase_client.update_user_preference(
                telefone=telefone,
                field=feedback.tipo,
                value=valor,
                learned_from="user_feedback",
                confidence=feedback.confianca
            )

            if success:
                # Loga no histórico de aprendizado
                await supabase_client.log_feedback(
                    telefone=telefone,
                    feedback_type="preference_update",
                    detected_pattern=feedback.pattern_matched or "unknown",
                    confidence_score=feedback.confianca,
                    applied=True,
                    details={
                        "tipo": feedback.tipo,
                        "valor": valor,
                        "explicacao": feedback.explicacao
                    }
                )

                print(f"[APRENDIZADO] {telefone}: {feedback.tipo} = {valor} (confiança: {feedback.confianca:.0%})")
                return True

            return False

        except Exception as e:
            print(f"[ERRO] Falha ao aplicar feedback: {e}")
            return False

    async def process_user_message(
        self,
        user_message: str,
        telefone: str
    ) -> tuple[List[FeedbackDetection], bool]:
        """
        Processa mensagem do usuário detectando e aplicando feedbacks

        Args:
            user_message: Mensagem do usuário
            telefone: Telefone do usuário

        Returns:
            Tuple (lista de feedbacks detectados, se algum foi aplicado)
        """
        if not settings.enable_preference_learning:
            return [], False

        # Detecta feedbacks
        feedbacks = await self.detect_feedback(user_message, telefone)

        if not feedbacks:
            return [], False

        # Aplica feedbacks com confiança >= 0.8
        applied_any = False
        for feedback in feedbacks:
            if await self.apply_feedback(telefone, feedback):
                applied_any = True

        return feedbacks, applied_any


# Instância global
preference_learning = PreferenceLearningSystem()
