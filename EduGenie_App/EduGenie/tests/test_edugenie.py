"""Run with:  python -m unittest discover tests -v   (or: pytest)
These tests use a fake AI, so they need no internet and no API key."""
import json
import unittest
from types import SimpleNamespace
from unittest import mock

from app import gemini_client
from app.modules import explain, learning_path, qna, quiz, summary
from app.utils import AIError, UserInputError, clean_input, clean_json_block, parse_quiz

GOOD_QUIZ = json.dumps([
    {"question": f"Q{i}?", "options": ["a", "b", "c", "d"], "answer": "b", "explanation": "because"}
    for i in range(3)
])


class InputTests(unittest.TestCase):
    def test_empty_input_rejected(self):
        with self.assertRaises(UserInputError):
            clean_input("   ", 100)

    def test_too_long_rejected(self):
        with self.assertRaises(UserInputError):
            clean_input("x" * 101, 100)

    def test_input_is_trimmed(self):
        self.assertEqual(clean_input("  hello  ", 100), "hello")


class QuizParsingTests(unittest.TestCase):
    def test_markdown_fence_removed(self):
        self.assertEqual(clean_json_block("```json\n[1]\n```"), "[1]")

    def test_valid_quiz(self):
        self.assertEqual(len(parse_quiz(GOOD_QUIZ)), 3)

    def test_fenced_quiz(self):
        self.assertEqual(len(parse_quiz(f"```json\n{GOOD_QUIZ}\n```")), 3)

    def test_letter_answer_converted(self):
        raw = json.dumps([{"question": "Q?", "options": ["w", "x", "y", "z"], "answer": "C"}])
        self.assertEqual(parse_quiz(raw)[0]["answer"], "y")

    def test_wrapped_in_object(self):
        self.assertEqual(len(parse_quiz(json.dumps({"questions": json.loads(GOOD_QUIZ)}))), 3)

    def test_bad_json_raises(self):
        with self.assertRaises(AIError):
            parse_quiz("not json at all")

    def test_wrong_option_count_skipped(self):
        raw = json.dumps([{"question": "Q?", "options": ["a", "b"], "answer": "a"}])
        with self.assertRaises(AIError):
            parse_quiz(raw)


class ModuleTests(unittest.TestCase):
    """Each module should send a sensible prompt and return the AI's text."""

    def test_text_modules(self):
        with mock.patch.object(gemini_client, "generate", return_value="ok") as fake:
            self.assertEqual(qna.answer_question("Why?"), "ok")
            self.assertEqual(explain.explain_topic("Gravity"), "ok")
            self.assertEqual(summary.summarize_text("long text"), "ok")
            self.assertEqual(learning_path.get_learning_recommendations("SQL", "Beginner"), "ok")
            self.assertIn("Gravity", fake.call_args_list[1].args[0])
            self.assertTrue(fake.call_args_list[0].kwargs["web_search"])
            self.assertNotIn("web_search", fake.call_args_list[1].kwargs)

    def test_unknown_level_falls_back(self):
        with mock.patch.object(gemini_client, "generate", return_value="ok") as fake:
            learning_path.get_learning_recommendations("SQL", "Wizard")
            self.assertIn("Beginner learner", fake.call_args.args[0])

    def test_quiz_module(self):
        with mock.patch.object(gemini_client, "generate", return_value=GOOD_QUIZ):
            self.assertEqual(len(quiz.generate_quiz("Solar system")), 3)

    def test_quiz_retries_once_on_bad_json(self):
        replies = ["garbage", GOOD_QUIZ]
        with mock.patch.object(gemini_client, "generate", side_effect=replies) as fake:
            self.assertEqual(len(quiz.generate_quiz("Solar system")), 3)
            self.assertEqual(fake.call_count, 2)


class ClientTests(unittest.TestCase):
    def test_missing_api_key_gives_friendly_error(self):
        with mock.patch.object(gemini_client.settings, "GEMINI_API_KEY", ""):
            gemini_client._client = None
            with self.assertRaises(AIError) as ctx:
                gemini_client.generate("hi")
            self.assertIn("GEMINI_API_KEY", str(ctx.exception))

    def test_friendly_messages(self):
        self.assertIn("API key", gemini_client._friendly(Exception("403 API key invalid")))
        self.assertIn("Too many", gemini_client._friendly(Exception("429 quota exceeded")))
        self.assertIn("not available", gemini_client._friendly(Exception("404 model not found")))

    def test_web_search_is_enabled_and_sources_are_returned(self):
        web = SimpleNamespace(title="Example source", uri="https://example.com/article")
        metadata = SimpleNamespace(grounding_chunks=[SimpleNamespace(web=web)])
        response = SimpleNamespace(
            text="A current answer.",
            candidates=[SimpleNamespace(grounding_metadata=metadata)],
        )
        client = mock.Mock()
        client.models.generate_content.return_value = response

        with (
            mock.patch.object(gemini_client.settings, "GEMINI_API_KEY", "test-key"),
            mock.patch.object(gemini_client, "_client", client),
        ):
            result = gemini_client.generate("Search for this", web_search=True)

        config = client.models.generate_content.call_args.kwargs["config"]
        self.assertIsNotNone(config.tools[0].google_search)
        self.assertIn("A current answer.", result)
        self.assertIn("https://example.com/article", result)


if __name__ == "__main__":
    unittest.main()
