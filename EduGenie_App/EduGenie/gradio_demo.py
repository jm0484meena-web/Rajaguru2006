"""OPTIONAL: quick Gradio page to test the AI modules and your prompts.
Install:  pip install gradio      Run:  python gradio_demo.py
Great for trying prompts before you touch the main web page."""
import gradio as gr

from app.modules.explain import explain_topic
from app.modules.learning_path import LEVELS, get_learning_recommendations
from app.modules.qna import answer_question
from app.modules.quiz import generate_quiz
from app.modules.summary import summarize_text
from app.utils import AIError


def safe(fn):
    def wrapper(*args):
        try:
            return fn(*args)
        except (AIError, ValueError) as error:
            return f"⚠️ {error}"
    return wrapper


def quiz_text(topic: str) -> str:
    lines = []
    for i, q in enumerate(generate_quiz(topic), 1):
        lines.append(f"Q{i}. {q['question']}")
        lines += [f"   - {o}" for o in q["options"]]
        lines.append(f"   Answer: {q['answer']}  ({q['explanation']})\n")
    return "\n".join(lines)


with gr.Blocks(title="EduGenie – module tester") as demo:
    gr.Markdown("# EduGenie 🧠 – module tester")
    for name, fn, label in [
        ("Ask", answer_question, "Question"),
        ("Explain", explain_topic, "Topic"),
        ("Summarize", summarize_text, "Text"),
        ("Quiz", quiz_text, "Topic"),
    ]:
        with gr.Tab(name):
            box = gr.Textbox(label=label, lines=3)
            out = gr.Textbox(label="Result", lines=10)
            gr.Button(name).click(safe(fn), box, out)
    with gr.Tab("Learning path"):
        topic = gr.Textbox(label="Topic")
        level = gr.Dropdown(list(LEVELS), value="Beginner", label="Level")
        out = gr.Textbox(label="Result", lines=14)
        gr.Button("Get path").click(safe(get_learning_recommendations), [topic, level], out)

if __name__ == "__main__":
    demo.launch()
