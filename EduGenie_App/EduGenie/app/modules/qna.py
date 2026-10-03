"""Q&A: answer a student's question."""
from .. import gemini_client


def answer_question(question: str) -> str:
    prompt = (
        "Answer the student's question clearly and correctly in 3 to 5 sentences. "
        "If it is a maths or science question, show the key step or formula.\n\n"
        f"Question:\n{question}"
    )
    return gemini_client.generate(prompt, web_search=True)
