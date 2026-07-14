from types import SimpleNamespace

from agent.conversation_loop import _ollama_context_limit_error


def _agent(*, num_ctx: int, tools: int = 3):
    return SimpleNamespace(
        tools=[{}] * tools,
        _ollama_num_ctx=num_ctx,
        model="gemma4:12b",
        base_url="http://127.0.0.1:11434/v1",
        provider="custom",
        session_id="test-session",
    )


def test_preflight_rejects_request_that_leaves_no_generation_room():
    error = _ollama_context_limit_error(_agent(num_ctx=16384), 16000)

    assert error is not None
    assert "leaving fewer than 256 tokens" in error
    assert "model.ollama_num_ctx: 65536" in error


def test_preflight_allows_request_with_useful_output_room():
    assert _ollama_context_limit_error(_agent(num_ctx=16384), 10000) is None

