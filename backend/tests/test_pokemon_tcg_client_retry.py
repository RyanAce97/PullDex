"""Unit tests for PokemonTCGClient retry behaviour.

All HTTP responses are mocked via httpx.MockTransport.
time.sleep is patched so tests run instantly.
"""

import json
from unittest.mock import MagicMock, call, patch

import httpx
import pytest

from app.services.api.pokemon_tcg_client import (
    _BACKOFF_BASE,
    _MAX_ATTEMPTS,
    _RETRYABLE_EXCEPTIONS,
    _RETRYABLE_STATUS_CODES,
    PokemonTCGClient,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _response(status_code: int, body: dict | None = None) -> httpx.Response:
    """Build a minimal httpx.Response for use inside a MockTransport."""
    content = json.dumps(body or {}).encode()
    return httpx.Response(
        status_code=status_code,
        headers={"Content-Type": "application/json"},
        content=content,
    )


def _client_with_responses(responses: list[httpx.Response]) -> PokemonTCGClient:
    """Return a PokemonTCGClient whose transport replays a fixed sequence of responses."""
    iterator = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return next(iterator)

    client = PokemonTCGClient()
    client._client = httpx.Client(
        base_url="https://api.pokemontcg.io/v2/",
        transport=httpx.MockTransport(handler),
    )
    return client


_OK_CARDS = {"data": [{"id": "sv1-1", "name": "Bulbasaur"}], "totalCount": 1}
_OK_SETS = {"data": [{"id": "sv1", "name": "Scarlet & Violet"}], "totalCount": 1}


# ---------------------------------------------------------------------------
# Retry constants
# ---------------------------------------------------------------------------

class TestRetryConstants:
    def test_max_attempts_is_five(self):
        assert _MAX_ATTEMPTS == 5

    def test_retryable_codes(self):
        assert _RETRYABLE_STATUS_CODES == frozenset({500, 502, 503, 504})

    def test_backoff_base_is_one_second(self):
        assert _BACKOFF_BASE == 1.0

    def test_retryable_exceptions_includes_timeout_and_network(self):
        assert httpx.ReadTimeout in _RETRYABLE_EXCEPTIONS
        assert httpx.ConnectTimeout in _RETRYABLE_EXCEPTIONS
        assert httpx.TimeoutException in _RETRYABLE_EXCEPTIONS
        assert httpx.NetworkError in _RETRYABLE_EXCEPTIONS

    def test_default_timeout_is_30_seconds(self):
        client = PokemonTCGClient()
        client.close()
        assert client._client.timeout.read == 30.0


# ---------------------------------------------------------------------------
# Success on first attempt
# ---------------------------------------------------------------------------

class TestSuccessOnFirstAttempt:
    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_get_cards_succeeds_immediately(self, mock_sleep):
        with _client_with_responses([_response(200, _OK_CARDS)]) as client:
            data = client.get_cards()

        assert data["data"][0]["id"] == "sv1-1"
        mock_sleep.assert_not_called()

    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_get_sets_succeeds_immediately(self, mock_sleep):
        with _client_with_responses([_response(200, _OK_SETS)]) as client:
            data = client.get_sets()

        assert data["data"][0]["id"] == "sv1"
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Retry on transient errors
# ---------------------------------------------------------------------------

class TestRetryOnTransientErrors:
    @pytest.mark.parametrize("status_code", [500, 502, 503, 504])
    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_retries_on_each_retryable_status(self, mock_sleep, status_code):
        """A single transient failure followed by success should succeed."""
        responses = [_response(status_code), _response(200, _OK_CARDS)]
        with _client_with_responses(responses) as client:
            data = client.get_cards()

        assert "data" in data
        mock_sleep.assert_called_once_with(1.0)  # 2^0 * base

    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_succeeds_after_multiple_transient_failures(self, mock_sleep):
        """Three 500s then a 200 — should succeed on the fourth attempt."""
        responses = [
            _response(500),
            _response(503),
            _response(502),
            _response(200, _OK_CARDS),
        ]
        with _client_with_responses(responses) as client:
            data = client.get_cards()

        assert "data" in data
        # Slept after attempt 0 (1s), 1 (2s), 2 (4s)
        assert mock_sleep.call_count == 3
        mock_sleep.assert_has_calls([call(1.0), call(2.0), call(4.0)])

    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_exponential_backoff_delays(self, mock_sleep):
        """Delays must follow the 1s, 2s, 4s, 8s sequence."""
        # Four failures then a success (5 attempts total).
        responses = [
            _response(500),
            _response(500),
            _response(500),
            _response(500),
            _response(200, _OK_SETS),
        ]
        with _client_with_responses(responses) as client:
            client.get_sets()

        assert mock_sleep.call_count == 4
        mock_sleep.assert_has_calls([
            call(1.0),   # after attempt 0
            call(2.0),   # after attempt 1
            call(4.0),   # after attempt 2
            call(8.0),   # after attempt 3
        ])

    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_no_sleep_after_final_attempt(self, mock_sleep):
        """Sleep must not be called after the last failed attempt."""
        responses = [_response(500)] * _MAX_ATTEMPTS
        with _client_with_responses(responses) as client:
            with pytest.raises(httpx.HTTPStatusError):
                client.get_cards()

        # Five attempts → four sleeps (not five).
        assert mock_sleep.call_count == _MAX_ATTEMPTS - 1


# ---------------------------------------------------------------------------
# Exhausted retries
# ---------------------------------------------------------------------------

class TestExhaustedRetries:
    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_raises_after_max_attempts_for_get_cards(self, mock_sleep):
        responses = [_response(500)] * _MAX_ATTEMPTS
        with _client_with_responses(responses) as client:
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                client.get_cards()

        assert exc_info.value.response.status_code == 500

    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_raises_after_max_attempts_for_get_sets(self, mock_sleep):
        responses = [_response(503)] * _MAX_ATTEMPTS
        with _client_with_responses(responses) as client:
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                client.get_sets()

        assert exc_info.value.response.status_code == 503

    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_total_attempts_does_not_exceed_max(self, mock_sleep):
        """Exactly _MAX_ATTEMPTS requests should be made before giving up."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return _response(500)

        client = PokemonTCGClient()
        client._client = httpx.Client(
            base_url="https://api.pokemontcg.io/v2/",
            transport=httpx.MockTransport(handler),
        )
        with client:
            with pytest.raises(httpx.HTTPStatusError):
                client.get_cards()

        assert call_count == _MAX_ATTEMPTS


# ---------------------------------------------------------------------------
# Non-retryable errors
# ---------------------------------------------------------------------------

class TestNonRetryableErrors:
    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_does_not_retry_client_errors(self, mock_sleep, status_code):
        """4xx errors should be raised immediately without any retry."""
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return _response(status_code)

        client = PokemonTCGClient()
        client._client = httpx.Client(
            base_url="https://api.pokemontcg.io/v2/",
            transport=httpx.MockTransport(handler),
        )
        with client:
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                client.get_cards()

        assert call_count == 1
        assert exc_info.value.response.status_code == status_code
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# Retry on network / timeout exceptions
# ---------------------------------------------------------------------------

class TestRetryOnNetworkExceptions:
    def _client_raising(self, exc_sequence: list) -> PokemonTCGClient:
        """Return a client whose transport raises items from exc_sequence in order,
        then returns a 200 on the next call."""
        responses = [_response(200, _OK_CARDS)]
        exc_iter = iter(exc_sequence)
        resp_iter = iter(responses)

        def handler(request: httpx.Request) -> httpx.Response:
            try:
                raise next(exc_iter)
            except StopIteration:
                return next(resp_iter)

        client = PokemonTCGClient()
        client._client = httpx.Client(
            base_url="https://api.pokemontcg.io/v2/",
            transport=httpx.MockTransport(handler),
        )
        return client

    @pytest.mark.parametrize("exc_class", [
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
        httpx.NetworkError,
    ])
    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_retries_on_network_exception(self, mock_sleep, exc_class):
        """A single network failure followed by success should succeed."""
        request = httpx.Request("GET", "https://api.pokemontcg.io/v2/cards")
        exc = exc_class("transient error", request=request)
        with self._client_raising([exc]) as client:
            data = client.get_cards()

        assert "data" in data
        mock_sleep.assert_called_once_with(1.0)

    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_raises_network_error_after_all_attempts_exhausted(self, mock_sleep):
        """All attempts failing with NetworkError should raise NetworkError."""
        request = httpx.Request("GET", "https://api.pokemontcg.io/v2/cards")

        def handler(req: httpx.Request) -> httpx.Response:
            raise httpx.NetworkError("connection refused", request=request)

        client = PokemonTCGClient()
        client._client = httpx.Client(
            base_url="https://api.pokemontcg.io/v2/",
            transport=httpx.MockTransport(handler),
        )
        with client:
            with pytest.raises(httpx.NetworkError):
                client.get_cards()

        assert mock_sleep.call_count == _MAX_ATTEMPTS - 1

    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_raises_timeout_after_all_attempts_exhausted(self, mock_sleep):
        """All attempts failing with ReadTimeout should raise ReadTimeout."""
        request = httpx.Request("GET", "https://api.pokemontcg.io/v2/cards")

        def handler(req: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out", request=request)

        client = PokemonTCGClient()
        client._client = httpx.Client(
            base_url="https://api.pokemontcg.io/v2/",
            transport=httpx.MockTransport(handler),
        )
        with client:
            with pytest.raises(httpx.ReadTimeout):
                client.get_sets()

        assert mock_sleep.call_count == _MAX_ATTEMPTS - 1

    @patch("app.services.api.pokemon_tcg_client.time.sleep")
    def test_mixed_http_and_network_failures_eventually_succeed(self, mock_sleep):
        """A mix of 500 and NetworkError failures should still succeed when
        a successful response arrives within the attempt budget."""
        request = httpx.Request("GET", "https://api.pokemontcg.io/v2/cards")
        call_count = 0

        def handler(req: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _response(500)
            if call_count == 2:
                raise httpx.NetworkError("blip", request=request)
            return _response(200, _OK_CARDS)

        client = PokemonTCGClient()
        client._client = httpx.Client(
            base_url="https://api.pokemontcg.io/v2/",
            transport=httpx.MockTransport(handler),
        )
        with client:
            data = client.get_cards()

        assert "data" in data
        assert call_count == 3
        assert mock_sleep.call_count == 2
