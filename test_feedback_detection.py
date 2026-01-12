import asyncio
from app.services.preference_learning import PreferenceLearningSystem

async def test_feedback():
    service = PreferenceLearningSystem()

    test_cases = [
        ("diminua a mensagem", "nivel_detalhe", "resumido"),
        ("seja mais formal", "tom_de_voz", "profissional"),
        ("pode usar emojis", "emojis_habilitados", True),
        ("prefiro em bullet points", "formato_resposta", "bullet_points"),
    ]

    print("[INFO] Testando detecao de feedback...\n")

    for message, expected_field, expected_value in test_cases:
        feedbacks = await service.detect_feedback(message, "5511999999999")

        if feedbacks and feedbacks[0].tipo == expected_field:
            print(f"[OK] '{message}' -> {expected_field} = {expected_value}")
        else:
            print(f"[ERRO] '{message}' nao detectou {expected_field}")
            if feedbacks:
                print(f"      Detectou: {feedbacks[0].tipo} = {feedbacks[0].valor}")

    print("\n[OK] Teste de feedback concluido!")

if __name__ == "__main__":
    asyncio.run(test_feedback())
