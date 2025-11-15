"""
Simple test script to verify the setup.
"""
import asyncio
from app.services.ai_service import ai_service


async def test_ai_service():
    """Test AI service."""
    print("Testing MCQ generation...")
    mcqs = await ai_service.generate_mcqs(
        text="Python is a high-level programming language.",
        num_questions=3,
        difficulty="easy"
    )
    print(f"Generated {len(mcqs)} MCQs")
    for i, mcq in enumerate(mcqs, 1):
        print(f"\nMCQ {i}:")
        print(f"Q: {mcq['question']}")
        print(f"A: {mcq['correct_answer']}")

    print("\n" + "="*50)
    print("Testing chat...")
    response = await ai_service.chat("What is Python?")
    print(f"Response: {response}")


if __name__ == "__main__":
    asyncio.run(test_ai_service())
