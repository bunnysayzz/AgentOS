"""Unit tests for pure service-layer logic (no database required).

Covers the deterministic business rules that the API layer builds on:
- API key generation format & hashing
- Agent execution state machine transitions
- Workflow DAG validation (cycles, dangling edges, duplicates)
- Secret (Fernet) and provider key (XOR) encryption round-trips
- Prompt template variable extraction
- MCP cost calculation and provider fallback chain
"""

import hashlib

import pytest

from app.services import api_key_service, agent_service, workflow_service
from app.services.provider_metadata import get_fallback_chain, is_rate_limit_error
from app.services.mcp_service import calculate_cost
from app.services.prompt_service import _extract_variables
from app.services.secret_service import encrypt_value, decrypt_value
from app.services.provider_service import _encrypt_key, _decrypt_key
from app.models.agent import ExecutionStatus


# ─── API Keys ────────────────────────────────────────


class TestApiKeyGeneration:
    def test_format_and_hash(self):
        full_key, key_prefix, key_hash = api_key_service.generate_api_key()
        assert full_key.startswith("agos_")
        assert key_prefix.startswith("agos_")
        assert full_key.startswith(f"{key_prefix}_")
        assert len(full_key) > len(key_prefix)
        # Hash must match the full key (never stored in plaintext)
        assert key_hash == hashlib.sha256(full_key.encode()).hexdigest()
        # Stored hash must not leak the key
        assert full_key not in key_hash

    def test_keys_are_unique(self):
        keys = {api_key_service.generate_api_key()[0] for _ in range(50)}
        assert len(keys) == 50

    def test_prefix_is_stable_identifier(self):
        _, prefix_a, _ = api_key_service.generate_api_key()
        _, prefix_b, _ = api_key_service.generate_api_key()
        assert prefix_a != prefix_b


# ─── Agent Execution State Machine ───────────────────


class TestAgentStateMachine:
    def test_valid_transitions_exist(self):
        transitions = agent_service.EXECUTION_TRANSITIONS
        assert ExecutionStatus.RUNNING in transitions[ExecutionStatus.PENDING]
        assert ExecutionStatus.CANCELLED in transitions[ExecutionStatus.PENDING]
        assert ExecutionStatus.PAUSED in transitions[ExecutionStatus.RUNNING]
        assert ExecutionStatus.COMPLETED in transitions[ExecutionStatus.RUNNING]
        assert ExecutionStatus.FAILED in transitions[ExecutionStatus.RUNNING]
        assert ExecutionStatus.RUNNING in transitions[ExecutionStatus.PAUSED]

    def test_invalid_transition_raises(self):
        with pytest.raises(agent_service.InvalidTransitionError):
            agent_service.validate_transition(ExecutionStatus.PENDING, ExecutionStatus.COMPLETED)
        with pytest.raises(agent_service.InvalidTransitionError):
            agent_service.validate_transition(ExecutionStatus.COMPLETED, ExecutionStatus.RUNNING)

    def test_terminal_states_are_final(self):
        for state in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
            assert agent_service.EXECUTION_TRANSITIONS[state] == set()

    def test_pause_pending_is_invalid(self):
        with pytest.raises(agent_service.InvalidTransitionError):
            agent_service.validate_transition(ExecutionStatus.PENDING, ExecutionStatus.PAUSED)


# ─── Workflow DAG Validation ─────────────────────────


class TestDAGValidation:
    def test_valid_dag_passes(self):
        dag = {
            "nodes": [{"id": "a", "type": "agent"}, {"id": "b", "type": "tool"}],
            "edges": [{"source": "a", "target": "b"}],
        }
        assert workflow_service.validate_dag(dag) == []

    def test_single_node_without_edges_is_valid(self):
        dag = {"nodes": [{"id": "a", "type": "agent"}], "edges": []}
        assert workflow_service.validate_dag(dag) == []

    def test_missing_nodes(self):
        errors = workflow_service.validate_dag({"nodes": [], "edges": []})
        assert any("at least one node" in e for e in errors)

    def test_duplicate_node_ids(self):
        dag = {"nodes": [{"id": "a", "type": "x"}, {"id": "a", "type": "y"}], "edges": []}
        errors = workflow_service.validate_dag(dag)
        assert any("Duplicate node id" in e for e in errors)

    def test_missing_type(self):
        dag = {"nodes": [{"id": "a"}], "edges": []}
        errors = workflow_service.validate_dag(dag)
        assert any("missing a 'type'" in e for e in errors)

    def test_edge_to_missing_node(self):
        dag = {
            "nodes": [{"id": "a", "type": "x"}],
            "edges": [{"source": "a", "target": "ghost"}],
        }
        errors = workflow_service.validate_dag(dag)
        assert any("target 'ghost' not found" in e for e in errors)

    def test_cycle_detected(self):
        dag = {
            "nodes": [{"id": "a", "type": "x"}, {"id": "b", "type": "y"}, {"id": "c", "type": "z"}],
            "edges": [
                {"source": "a", "target": "b"},
                {"source": "b", "target": "c"},
                {"source": "c", "target": "a"},
            ],
        }
        errors = workflow_service.validate_dag(dag)
        assert any("cycle" in e.lower() for e in errors)

    def test_partially_disconnected_node_reported(self):
        dag = {
            "nodes": [{"id": "a", "type": "x"}, {"id": "b", "type": "y"}, {"id": "orphan", "type": "z"}],
            "edges": [{"source": "a", "target": "b"}],
        }
        errors = workflow_service.validate_dag(dag)
        assert any("disconnected" in e and "orphan" in e for e in errors)


# ─── Secret Encryption (Fernet) ──────────────────────


class TestSecretEncryption:
    def test_roundtrip(self):
        value = "super-secret-value-123!@#"
        encrypted = encrypt_value(value)
        assert encrypted != value
        assert decrypt_value(encrypted) == value

    def test_encryption_is_non_deterministic(self):
        """Fernet embeds an IV, so two encryptions of the same value differ."""
        value = "same-value"
        assert encrypt_value(value) != encrypt_value(value)

    def test_wrong_key_fails_to_decrypt(self, monkeypatch):
        encrypted = encrypt_value("payload")
        from app.core.config import settings
        monkeypatch.setattr(settings, "ENCRYPTION_KEY", "a-completely-different-key-value!!")
        with pytest.raises(Exception):
            decrypt_value(encrypted)


# ─── Provider Key Encryption (XOR + base85) ──────────


class TestProviderKeyEncryption:
    def test_roundtrip(self):
        key = "sk-abcdef1234567890XYZ"
        encrypted = _encrypt_key(key)
        assert encrypted != key
        assert _decrypt_key(encrypted) == key

    def test_stored_value_is_obfuscated(self):
        key = "sk-secret-42"
        assert key not in _encrypt_key(key)


# ─── Prompt Template Helpers ─────────────────────────


class TestPromptHelpers:
    def test_extract_variables(self):
        template = "Hi {{name}}, you are {role} and your id is {{ user_id }}"
        assert set(_extract_variables(template)) == {"name", "role", "user_id"}

    def test_no_variables(self):
        assert _extract_variables("plain text, no placeholders") == []


# ─── MCP Cost Calculation ────────────────────────────


class TestCostCalculation:
    def test_gpt4o_mini(self):
        # (1000/1000)*0.00015 + (500/1000)*0.0006 = 0.00015 + 0.0003
        assert calculate_cost("gpt-4o-mini", 1000, 500) == pytest.approx(0.00045, abs=1e-9)

    def test_zero_tokens_is_free(self):
        assert calculate_cost("gpt-4o", 0, 0) == pytest.approx(0.0)

    def test_unknown_model_uses_default_pricing(self):
        # Default fallback: input 0.01/1k, output 0.03/1k
        assert calculate_cost("mystery-model", 1000, 1000) == pytest.approx(0.04, abs=1e-9)


# ─── Provider Fallback Chain ─────────────────────────


class TestFallbackChain:
    def test_primary_detected_from_model(self):
        configured = ["openai", "anthropic", "groq", "deepseek"]
        chain = get_fallback_chain(configured, model_name="gpt-4o")
        assert chain[0] == "openai"
        # Remaining providers follow fallback priority (anthropic=2, groq=6, deepseek=26)
        assert chain == ["openai", "anthropic", "groq", "deepseek"]

    def test_unconfigured_primary_is_skipped(self):
        chain = get_fallback_chain(["groq", "deepseek"], model_name="gpt-4o")
        assert "openai" not in chain
        assert chain[0] == "groq"

    def test_rate_limit_detection(self):
        assert is_rate_limit_error("Rate limit exceeded for model")
        assert is_rate_limit_error("429 Too Many Requests")
        assert is_rate_limit_error("quota exhausted for org")
        assert is_rate_limit_error("insufficient_quota")
        assert is_rate_limit_error("Insufficient balance: payment required")
        assert not is_rate_limit_error("Server error: 500 internal")
