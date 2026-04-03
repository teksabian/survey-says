#!/usr/bin/env python3
"""
Tests for Extended Thinking Toggle Feature
==========================================
Tests the extended thinking settings, API kwargs builder,
response text extraction, and route handlers.

Run with: python tests/test_extended_thinking.py
"""

import unittest
import os
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
import ai


class TestBuildClaudeApiKwargs(unittest.TestCase):
    """Test the build_claude_api_kwargs helper function"""

    @patch('ai.get_setting')
    def test_thinking_disabled_returns_temperature(self, mock_get_setting):
        """When thinking is disabled, should include temperature=0 and given max_tokens"""
        mock_get_setting.return_value = 'false'
        result = ai.build_claude_api_kwargs(max_tokens_default=1024)
        self.assertEqual(result['max_tokens'], 1024)
        self.assertEqual(result['temperature'], 0)
        self.assertNotIn('thinking', result)

    @patch('ai.get_setting')
    def test_thinking_enabled_returns_thinking_param(self, mock_get_setting):
        """When thinking is enabled, should include thinking dict and no temperature"""
        def side_effect(key, default=''):
            if key == 'extended_thinking_enabled':
                return 'true'
            if key == 'thinking_budget_tokens':
                return '10000'
            return default
        mock_get_setting.side_effect = side_effect

        result = ai.build_claude_api_kwargs(max_tokens_default=1024)
        self.assertNotIn('temperature', result)
        self.assertIn('thinking', result)
        self.assertEqual(result['thinking']['type'], 'enabled')
        self.assertEqual(result['thinking']['budget_tokens'], 10000)
        # max_tokens should be budget + default
        self.assertEqual(result['max_tokens'], 11024)

    @patch('ai.get_setting')
    def test_thinking_budget_minimum_enforced(self, mock_get_setting):
        """Budget below 1024 should be clamped to 1024"""
        def side_effect(key, default=''):
            if key == 'extended_thinking_enabled':
                return 'true'
            if key == 'thinking_budget_tokens':
                return '500'
            return default
        mock_get_setting.side_effect = side_effect

        result = ai.build_claude_api_kwargs(max_tokens_default=1024)
        self.assertEqual(result['thinking']['budget_tokens'], 1024)
        self.assertEqual(result['max_tokens'], 2048)

    @patch('ai.get_setting')
    def test_thinking_disabled_photo_scan_max_tokens(self, mock_get_setting):
        """Photo scan uses max_tokens=2048 when thinking is off"""
        mock_get_setting.return_value = 'false'
        result = ai.build_claude_api_kwargs(max_tokens_default=2048)
        self.assertEqual(result['max_tokens'], 2048)
        self.assertEqual(result['temperature'], 0)

    @patch('ai.get_setting')
    def test_thinking_enabled_photo_scan_max_tokens(self, mock_get_setting):
        """Photo scan max_tokens should be budget + 2048 when thinking is on"""
        def side_effect(key, default=''):
            if key == 'extended_thinking_enabled':
                return 'true'
            if key == 'thinking_budget_tokens':
                return '5000'
            return default
        mock_get_setting.side_effect = side_effect

        result = ai.build_claude_api_kwargs(max_tokens_default=2048)
        self.assertEqual(result['max_tokens'], 7048)
        self.assertEqual(result['thinking']['budget_tokens'], 5000)


class TestExtractResponseText(unittest.TestCase):
    """Test the extract_response_text helper function"""

    def test_simple_text_response(self):
        """Standard response with just a text block"""
        message = MagicMock()
        text_block = MagicMock()
        text_block.type = 'text'
        text_block.text = '{"matches": [1, 3]}'
        message.content = [text_block]

        result = ai.extract_response_text(message)
        self.assertEqual(result, '{"matches": [1, 3]}')

    def test_thinking_plus_text_response(self):
        """Response with thinking block followed by text block"""
        message = MagicMock()
        thinking_block = MagicMock()
        thinking_block.type = 'thinking'
        text_block = MagicMock()
        text_block.type = 'text'
        text_block.text = '{"matches": [2]}'
        message.content = [thinking_block, text_block]

        result = ai.extract_response_text(message)
        self.assertEqual(result, '{"matches": [2]}')

    def test_fallback_when_no_text_block(self):
        """Edge case: no text block found, falls back to index 0"""
        message = MagicMock()
        block = MagicMock()
        block.type = 'unknown'
        block.text = 'fallback content'
        message.content = [block]

        result = ai.extract_response_text(message)
        self.assertEqual(result, 'fallback content')


class TestExtendedThinkingRoutes(unittest.TestCase):
    """Test the toggle and budget routes via Flask test client"""

    def setUp(self):
        """Set up Flask test client"""
        app.app.config['TESTING'] = True
        app.app.config['SECRET_KEY'] = 'test-secret'
        self.client = app.app.test_client()
        # Simulate host session
        with self.client.session_transaction() as sess:
            sess['host_authenticated'] = True

    @patch('routes.host.dashboard.set_setting')
    @patch('routes.host.dashboard.get_setting')
    def test_toggle_thinking_on(self, mock_get, mock_set):
        """Toggle extended_thinking_enabled from false to true"""
        mock_get.return_value = 'false'
        response = self.client.post('/host/toggle-setting',
                                     data={'setting_key': 'extended_thinking_enabled'},
                                     follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        mock_set.assert_any_call('extended_thinking_enabled', 'true', '')

    @patch('routes.host.dashboard.set_setting')
    @patch('routes.host.dashboard.get_setting')
    def test_toggle_thinking_off(self, mock_get, mock_set):
        """Toggle extended_thinking_enabled from true to false"""
        mock_get.return_value = 'true'
        response = self.client.post('/host/toggle-setting',
                                     data={'setting_key': 'extended_thinking_enabled'},
                                     follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        mock_set.assert_any_call('extended_thinking_enabled', 'false', '')

    @patch('routes.host.dashboard.set_setting')
    def test_set_valid_budget(self, mock_set):
        """Setting a valid budget should succeed"""
        response = self.client.post('/host/set-thinking-budget',
                                     data={'thinking_budget': '20000'},
                                     follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        mock_set.assert_called_with('thinking_budget_tokens', '20000',
                                     'Token budget for extended thinking')

    def test_set_budget_below_minimum(self):
        """Budget below 1024 should be rejected"""
        response = self.client.post('/host/set-thinking-budget',
                                     data={'thinking_budget': '512'},
                                     follow_redirects=True)
        self.assertIn(b'at least', response.data)

    def test_set_budget_invalid_string(self):
        """Non-numeric budget should be rejected"""
        response = self.client.post('/host/set-thinking-budget',
                                     data={'thinking_budget': 'abc'},
                                     follow_redirects=True)
        self.assertIn(b'Invalid', response.data)

    def test_set_budget_above_maximum(self):
        """Budget above 128000 should be rejected"""
        response = self.client.post('/host/set-thinking-budget',
                                     data={'thinking_budget': '200000'},
                                     follow_redirects=True)
        self.assertIn(b'cannot exceed', response.data)

    @patch('routes.host.dashboard.set_setting')
    def test_set_minimum_budget(self, mock_set):
        """Setting exact minimum budget (1024) should succeed"""
        response = self.client.post('/host/set-thinking-budget',
                                     data={'thinking_budget': '1024'},
                                     follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        mock_set.assert_called_with('thinking_budget_tokens', '1024',
                                     'Token budget for extended thinking')

    @patch('routes.host.dashboard.set_setting')
    def test_set_maximum_budget(self, mock_set):
        """Setting exact maximum budget (128000) should succeed"""
        response = self.client.post('/host/set-thinking-budget',
                                     data={'thinking_budget': '128000'},
                                     follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        mock_set.assert_called_with('thinking_budget_tokens', '128000',
                                     'Token budget for extended thinking')


class TestCallClaudeApi(unittest.TestCase):
    """Test the call_claude_api helper with streaming threshold logic"""

    def test_non_streaming_without_thinking(self):
        """Without thinking, should use client.messages.create regardless of max_tokens"""
        client = MagicMock()
        expected_message = MagicMock()
        client.messages.create.return_value = expected_message

        api_kwargs = {'max_tokens': 1024, 'temperature': 0}
        result = ai.call_claude_api(client, 'claude-sonnet-4-20250514',
                                      [{'role': 'user', 'content': 'test'}], api_kwargs)
        client.messages.create.assert_called_once()
        client.messages.stream.assert_not_called()
        self.assertEqual(result, expected_message)

    def test_non_streaming_thinking_below_threshold(self):
        """With thinking but max_tokens below threshold, should use create"""
        client = MagicMock()
        expected_message = MagicMock()
        client.messages.create.return_value = expected_message

        api_kwargs = {'max_tokens': 11024, 'thinking': {'type': 'enabled', 'budget_tokens': 10000}}
        result = ai.call_claude_api(client, 'claude-opus-4-20250514',
                                      [{'role': 'user', 'content': 'test'}], api_kwargs)
        client.messages.create.assert_called_once()
        client.messages.stream.assert_not_called()
        self.assertEqual(result, expected_message)

    def test_streaming_thinking_above_threshold(self):
        """With thinking and max_tokens above threshold, should use stream"""
        client = MagicMock()
        expected_message = MagicMock()
        stream_ctx = MagicMock()
        stream_ctx.__enter__ = MagicMock(return_value=stream_ctx)
        stream_ctx.__exit__ = MagicMock(return_value=False)
        stream_ctx.get_final_message.return_value = expected_message
        client.messages.stream.return_value = stream_ctx

        api_kwargs = {'max_tokens': 52048, 'thinking': {'type': 'enabled', 'budget_tokens': 50000}}
        result = ai.call_claude_api(client, 'claude-opus-4-20250514',
                                      [{'role': 'user', 'content': 'test'}], api_kwargs)
        client.messages.create.assert_not_called()
        client.messages.stream.assert_called_once()
        stream_ctx.get_final_message.assert_called_once()
        self.assertEqual(result, expected_message)

    def test_threshold_boundary_exactly_at_limit(self):
        """At exactly the threshold, should NOT stream (only above)"""
        client = MagicMock()
        expected_message = MagicMock()
        client.messages.create.return_value = expected_message

        api_kwargs = {'max_tokens': ai.STREAMING_THRESHOLD, 'thinking': {'type': 'enabled', 'budget_tokens': 20000}}
        result = ai.call_claude_api(client, 'claude-opus-4-20250514',
                                      [{'role': 'user', 'content': 'test'}], api_kwargs)
        client.messages.create.assert_called_once()
        client.messages.stream.assert_not_called()


if __name__ == '__main__':
    print("=" * 70)
    print("SURVEY SAYS - EXTENDED THINKING TESTS")
    print("=" * 70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python: {sys.version.split()[0]}")
    print("=" * 70 + "\n")
    unittest.main(verbosity=2)
