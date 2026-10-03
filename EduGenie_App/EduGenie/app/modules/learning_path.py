"""Learning path: a Beginner -> Advanced plan for any topic."""
from .. import gemini_client

LEVELS = ("Beginner", "Intermediate", "Advanced")


def get_learning_recommendations(topic: str, level: str = "Beginner") -> str:
    if level not in LEVELS:
        level = "Beginner"
    prompt = (
        f'Create a learning path for "{topic}" for a {level} learner.\n'
        "Organise it in three stages: Beginner, Intermediate, Advanced. "
        "Use a '## ' heading for each stage. For each stage give:\n"
        "- the key topics to learn (bullet list starting with '- ')\n"
        "- an estimated time\n"
        "- one or two free resources (videos, articles or books)\n"
        "Finish with 3 short study tips."
    )
    return gemini_client.generate(prompt)
