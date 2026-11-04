from unittest.mock import Mock, call, patch

from django.test import SimpleTestCase, override_settings

from news.exceptions import AIServiceError
from news.services.llm import (
    chat_completion,
    is_llm_enabled,
    llm_cache_identity,
    llm_provider_label,
    reset_llm_provider_trace,
)


def make_response(status_code=200, content="Test response", error=None, headers=None):
    response = Mock()
    response.status_code = status_code
    response.headers = headers or {"x-request-id": "req-test"}
    if error is not None:
        response.json.return_value = {"error": error}
    else:
        response.json.return_value = {
            "choices": [{"message": {"content": content}}]
        }
    return response


class MultiProviderLLMTests(SimpleTestCase):
    def setUp(self):
        reset_llm_provider_trace()

    @override_settings(NEWSHUB={
        "GEMINI_API_KEY": "gemini-test-key",
        "GEMINI_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai",
        "GEMINI_MODEL": "gemini-3.8-flash",
        "GEMINI_TIMEOUT": 18,
        "GROQ_API_KEY": "groq-test-key",
        "GROQ_BASE_URL": "https://api.groq.com/openai/v1",
        "GROQ_MODEL": "openai/gpt-oss-20b",
        "GROQ_TIMEOUT": 18,
        "LLM_API_KEY": "",
    })
    @patch("news.services.llm.requests.post")
    def test_gemini_is_primary_and_reports_provider(self, post):
        post.return_value = make_response(content="Gemini summary")
        result = chat_completion([{"role": "user", "content": "Summarize this."}], max_tokens=120)

        self.assertEqual(result, "Gemini summary")
        self.assertEqual(post.call_count, 1)
        self.assertEqual(
            post.call_args.args[0],
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        )
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "gemini-3.8-flash")
        self.assertEqual(payload["max_tokens"], 120)
        self.assertEqual(llm_provider_label(), "gemini:gemini-3.8-flash")

    @override_settings(NEWSHUB={
        "GEMINI_API_KEY": "gemini-test-key",
        "GEMINI_BASE_URL": "https://generativelanguage.googleapis.com/v1beta/openai",
        "GEMINI_MODEL": "gemini-3.8-flash",
        "GEMINI_TIMEOUT": 18,
        "GROQ_API_KEY": "groq-test-key",
        "GROQ_BASE_URL": "https://api.groq.com/openai/v1",
        "GROQ_MODEL": "openai/gpt-oss-20b",
        "GROQ_TIMEOUT": 18,
        "LLM_API_KEY": "",
    })
    @patch("news.services.llm.requests.post")
    def test_groq_is_used_when_gemini_fails(self, post):
        post.side_effect = [
            make_response(
                status_code=429,
                error={"code": "RESOURCE_EXHAUSTED", "message": "rate limit"},
            ),
            make_response(content="Groq fallback summary"),
        ]
        result = chat_completion([{"role": "user", "content": "Summarize this."}], max_tokens=140)

        self.assertEqual(result, "Groq fallback summary")
        self.assertEqual(post.call_count, 2)
        self.assertIn("generativelanguage.googleapis.com", post.call_args_list[0].args[0])
        self.assertEqual(
            post.call_args_list[1].args[0],
            "https://api.groq.com/openai/v1/chat/completions",
        )
        groq_payload = post.call_args_list[1].kwargs["json"]
        self.assertEqual(groq_payload["model"], "openai/gpt-oss-20b")
        self.assertEqual(groq_payload["max_completion_tokens"], 140)
        self.assertEqual(llm_provider_label(), "groq:openai/gpt-oss-20b")

    @override_settings(NEWSHUB={
        "GEMINI_API_KEY": "",
        "GROQ_API_KEY": "",
        "LLM_API_KEY": "legacy-test-key",
        "LLM_BASE_URL": "https://api.openai.com/v1",
        "LLM_MODEL": "gpt-4o-mini",
        "LLM_TIMEOUT": 10,
        "LLM_ENABLE_LEGACY_FALLBACK": False,
    })
    @patch("news.services.llm.requests.post")
    def test_legacy_provider_still_works_when_no_new_keys_are_configured(self, post):
        post.return_value = make_response(content="Legacy response")
        result = chat_completion([{"role": "user", "content": "Test"}])
        self.assertEqual(result, "Legacy response")
        self.assertEqual(post.call_args.args[0], "https://api.openai.com/v1/chat/completions")

    @override_settings(NEWSHUB={"GEMINI_API_KEY": "", "GROQ_API_KEY": "", "LLM_API_KEY": ""})
    def test_no_provider_is_reported_as_disabled(self):
        self.assertFalse(is_llm_enabled())
        with self.assertRaisesRegex(AIServiceError, "No AI provider is configured"):
            chat_completion([{"role": "user", "content": "Test"}])

    @override_settings(NEWSHUB={
        "GEMINI_API_KEY": "gemini-test-key",
        "GEMINI_MODEL": "gemini-3.8-flash",
        "GROQ_API_KEY": "groq-test-key",
        "GROQ_MODEL": "openai/gpt-oss-20b",
    })
    def test_cache_identity_contains_both_provider_models(self):
        identity = llm_cache_identity()
        self.assertIn("gemini:gemini-3.8-flash", identity)
        self.assertIn("groq:openai/gpt-oss-20b", identity)
