#!/usr/bin/env python3
"""
Tests for Photo Capture with Editable Review feature.
Tests the extract, review, and submit flow for single-team scorecard scanning.
"""

import unittest
import sqlite3
import os
import sys
import json
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app
import ai
from config import PHOTO_SCAN_SINGLE_PROMPT


class TestPhotoScanSinglePrompt(unittest.TestCase):
    """Test that the single-team extraction prompt is properly defined"""

    def test_single_prompt_exists(self):
        """PHOTO_SCAN_SINGLE_PROMPT should be defined"""
        self.assertIn('SINGLE', PHOTO_SCAN_SINGLE_PROMPT.upper())

    def test_single_prompt_returns_flat_json(self):
        """Single prompt should request flat JSON (not nested under 'teams')"""
        prompt = PHOTO_SCAN_SINGLE_PROMPT
        self.assertIn('"code"', prompt)
        self.assertIn('"team_name"', prompt)
        self.assertIn('"answers"', prompt)
        self.assertIn('"tiebreaker"', prompt)
        self.assertIn('"low_confidence_fields"', prompt)
        # Should NOT ask for a 'teams' array wrapper
        self.assertNotIn('"teams"', prompt)

    def test_single_prompt_asks_for_blank_on_unreadable(self):
        """Prompt should instruct AI to leave unreadable fields blank"""
        prompt = PHOTO_SCAN_SINGLE_PROMPT
        self.assertIn('blank', prompt.lower())


class TestExtractSingleScorecard(unittest.TestCase):
    """Test the extract_single_scorecard function"""

    @patch('ai.AI_SCORING_ENABLED', False)
    def test_returns_none_when_ai_unavailable(self):
        """Should return None if AI scoring is not enabled"""
        result = ai.extract_single_scorecard('fake_base64')
        self.assertIsNone(result)

    @patch('ai.call_claude_api')
    @patch('ai.AI_SCORING_ENABLED', True)
    @patch('ai.anthropic_client', MagicMock())
    def test_parses_valid_response(self, mock_call):
        """Should correctly parse a valid JSON response from Claude"""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(type='text', text=json.dumps({
            'code': 'ABAR',
            'team_name': 'Test Team',
            'answers': ['chicken', 'pizza', '', '', '', ''],
            'tiebreaker': 42,
            'low_confidence_fields': ['answers.2']
        }))]
        mock_call.return_value = mock_message

        result = ai.extract_single_scorecard('fake_base64')

        self.assertIsNotNone(result)
        self.assertEqual(result['code'], 'ABAR')
        self.assertEqual(result['team_name'], 'Test Team')
        self.assertEqual(len(result['answers']), 6)
        self.assertEqual(result['tiebreaker'], 42)
        self.assertIn('answers.2', result['low_confidence_fields'])

    @patch('ai.call_claude_api')
    @patch('ai.AI_SCORING_ENABLED', True)
    @patch('ai.anthropic_client', MagicMock())
    def test_pads_short_answers_list(self, mock_call):
        """Should pad answers to exactly 6 if fewer are returned"""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(type='text', text=json.dumps({
            'code': 'XMPR',
            'team_name': 'Short',
            'answers': ['a', 'b'],
            'tiebreaker': 0
        }))]
        mock_call.return_value = mock_message

        result = ai.extract_single_scorecard('fake_base64')
        self.assertEqual(len(result['answers']), 6)
        self.assertEqual(result['answers'][2], '')

    @patch('ai.call_claude_api')
    @patch('ai.AI_SCORING_ENABLED', True)
    @patch('ai.anthropic_client', MagicMock())
    def test_handles_invalid_tiebreaker(self, mock_call):
        """Should default tiebreaker to 0 if not a valid int"""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(type='text', text=json.dumps({
            'code': 'ABAR',
            'team_name': 'TBTest',
            'answers': [''] * 6,
            'tiebreaker': 'unclear'
        }))]
        mock_call.return_value = mock_message

        result = ai.extract_single_scorecard('fake_base64')
        self.assertEqual(result['tiebreaker'], 0)

    @patch('ai.call_claude_api')
    @patch('ai.AI_SCORING_ENABLED', True)
    @patch('ai.anthropic_client', MagicMock())
    def test_handles_array_response(self, mock_call):
        """Should return None (not crash) if model returns a JSON array instead of object"""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(type='text', text=json.dumps([
            {'code': 'ABAR', 'team_name': 'Test', 'answers': ['a'] * 6, 'tiebreaker': 0}
        ]))]
        mock_call.return_value = mock_message

        result = ai.extract_single_scorecard('fake_base64')
        self.assertIsNone(result)


class TestPhotoScanExtractRoute(unittest.TestCase):
    """Test the /host/photo-scan/extract endpoint"""

    def setUp(self):
        app.app.config['TESTING'] = True
        app.app.config['SECRET_KEY'] = 'test-secret'
        self.client = app.app.test_client()
        with self.client.session_transaction() as sess:
            sess['host_authenticated'] = True

    @patch('routes.scoring.AI_SCORING_ENABLED', False)
    def test_extract_requires_ai(self):
        """Should return 503 if AI not enabled"""
        response = self.client.post('/host/photo-scan/extract',
                                     data=json.dumps({'image': 'abc', 'round_id': 1}),
                                     content_type='application/json')
        self.assertEqual(response.status_code, 503)

    @patch('routes.scoring.AI_SCORING_ENABLED', True)
    def test_extract_requires_image(self):
        """Should return 400 if no image provided"""
        response = self.client.post('/host/photo-scan/extract',
                                     data=json.dumps({}),
                                     content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_extract_requires_auth(self):
        """Should redirect to login if not authenticated"""
        client = app.app.test_client()
        response = client.post('/host/photo-scan/extract',
                                data=json.dumps({'image': 'abc', 'round_id': 1}),
                                content_type='application/json')
        self.assertEqual(response.status_code, 302)


class TestPhotoScanSubmitReviewedRoute(unittest.TestCase):
    """Test the /host/photo-scan/submit-reviewed endpoint"""

    def setUp(self):
        app.app.config['TESTING'] = True
        app.app.config['SECRET_KEY'] = 'test-secret'
        self.client = app.app.test_client()
        with self.client.session_transaction() as sess:
            sess['host_authenticated'] = True

    def test_submit_requires_auth(self):
        """Should redirect to login if not authenticated"""
        client = app.app.test_client()
        response = client.post('/host/photo-scan/submit-reviewed',
                                data=json.dumps({'code': 'ABAR'}),
                                content_type='application/json')
        self.assertEqual(response.status_code, 302)

    def test_submit_requires_data(self):
        """Should return 400 if no data"""
        response = self.client.post('/host/photo-scan/submit-reviewed',
                                     content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_submit_requires_code(self):
        """Should return 400 if no code provided"""
        response = self.client.post('/host/photo-scan/submit-reviewed',
                                     data=json.dumps({'team_name': 'Test', 'round_id': 1}),
                                     content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertFalse(data['success'])
        self.assertIn('code', data['error'].lower())


class TestPhotoScanTeamCountRoute(unittest.TestCase):
    """Test the /host/photo-scan/team-count endpoint"""

    def setUp(self):
        app.app.config['TESTING'] = True
        app.app.config['SECRET_KEY'] = 'test-secret'
        self.client = app.app.test_client()
        with self.client.session_transaction() as sess:
            sess['host_authenticated'] = True

    def test_team_count_requires_auth(self):
        """Should redirect if not authenticated"""
        client = app.app.test_client()
        response = client.get('/host/photo-scan/team-count')
        self.assertEqual(response.status_code, 302)

    def test_team_count_returns_json(self):
        """Should return JSON with submitted and total counts"""
        response = self.client.get('/host/photo-scan/team-count')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertIn('submitted', data)
        self.assertIn('total', data)


class TestSubmitReviewedDatabase(unittest.TestCase):
    """Test the submit-reviewed endpoint database operations"""

    def setUp(self):
        """Set up in-memory database to test submission logic"""
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row

        # Create tables matching app schema
        self.conn.execute("""
            CREATE TABLE team_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                used INTEGER DEFAULT 0,
                team_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_heartbeat TIMESTAMP DEFAULT NULL,
                reconnected INTEGER DEFAULT 0
            )
        """)
        self.conn.execute("""
            CREATE TABLE rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_number INTEGER NOT NULL,
                question TEXT,
                num_answers INTEGER DEFAULT 4,
                answer1 TEXT, answer2 TEXT, answer3 TEXT, answer4 TEXT,
                answer5 TEXT, answer6 TEXT,
                answer1_count INTEGER, answer2_count INTEGER,
                answer3_count INTEGER, answer4_count INTEGER,
                answer5_count INTEGER, answer6_count INTEGER,
                is_active INTEGER DEFAULT 0,
                submissions_closed INTEGER DEFAULT 0,
                winner_code TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                round_id INTEGER NOT NULL,
                answer1 TEXT, answer2 TEXT, answer3 TEXT,
                answer4 TEXT, answer5 TEXT, answer6 TEXT,
                tiebreaker INTEGER,
                score INTEGER DEFAULT 0,
                scored INTEGER DEFAULT 0,
                scored_at TIMESTAMP,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                previous_score INTEGER DEFAULT NULL,
                checked_answers TEXT,
                photo_path TEXT,
                UNIQUE(code, round_id)
            )
        """)

        # Insert test data
        self.conn.execute(
            "INSERT INTO team_codes (code, used, team_name) VALUES (?, ?, ?)",
            ('ABAR', 1, 'Test Team')
        )
        self.conn.execute(
            "INSERT INTO team_codes (code, used, team_name) VALUES (?, ?, ?)",
            ('HJNK', 0, None)
        )
        self.conn.execute(
            "INSERT INTO rounds (round_number, question, num_answers, is_active) VALUES (?, ?, ?, ?)",
            (1, 'Name something you find in a kitchen', 4, 1)
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_insert_submission_with_answers(self):
        """Submission should be inserted with all answer fields"""
        round_info = self.conn.execute("SELECT * FROM rounds WHERE id = 1").fetchone()
        num_answers = round_info['num_answers']

        code = 'ABAR'
        answers = ['stove', 'fridge', 'sink', 'microwave']
        tiebreaker = 25
        photo_path = 'uploads/scan_1_test.jpg'

        fields = ['code', 'round_id', 'tiebreaker', 'photo_path'] + [f'answer{i}' for i in range(1, num_answers + 1)]
        placeholders = ', '.join(['?'] * len(fields))
        values = [code, 1, tiebreaker, photo_path] + [answers[i] if i < len(answers) else '' for i in range(num_answers)]

        self.conn.execute(f"INSERT INTO submissions ({', '.join(fields)}) VALUES ({placeholders})", values)
        self.conn.commit()

        sub = self.conn.execute("SELECT * FROM submissions WHERE code = 'ABAR'").fetchone()
        self.assertEqual(sub['answer1'], 'stove')
        self.assertEqual(sub['answer2'], 'fridge')
        self.assertEqual(sub['answer3'], 'sink')
        self.assertEqual(sub['answer4'], 'microwave')
        self.assertEqual(sub['tiebreaker'], 25)
        self.assertEqual(sub['photo_path'], 'uploads/scan_1_test.jpg')

    def test_duplicate_submission_rejected(self):
        """Same code + round_id should raise IntegrityError"""
        self.conn.execute(
            "INSERT INTO submissions (code, round_id, answer1) VALUES (?, ?, ?)",
            ('ABAR', 1, 'test')
        )
        self.conn.commit()

        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO submissions (code, round_id, answer1) VALUES (?, ?, ?)",
                ('ABAR', 1, 'different')
            )

    def test_team_name_updated_on_submission(self):
        """Team name in team_codes should update when new name provided"""
        code = 'HJNK'
        new_name = 'New Team Name'
        self.conn.execute(
            "UPDATE team_codes SET used = 1, team_name = ? WHERE code = ?",
            (new_name, code)
        )
        self.conn.commit()

        row = self.conn.execute("SELECT * FROM team_codes WHERE code = ?", (code,)).fetchone()
        self.assertEqual(row['team_name'], new_name)
        self.assertEqual(row['used'], 1)

    def test_blank_answers_for_unreadable_fields(self):
        """Blank strings should be stored for fields AI couldn't read"""
        answers = ['chicken', '', '', '']  # Only first answer readable
        fields = ['code', 'round_id', 'answer1', 'answer2', 'answer3', 'answer4']
        self.conn.execute(
            f"INSERT INTO submissions ({', '.join(fields)}) VALUES (?, ?, ?, ?, ?, ?)",
            ('ABAR', 1, answers[0], answers[1], answers[2], answers[3])
        )
        self.conn.commit()

        sub = self.conn.execute("SELECT * FROM submissions WHERE code = 'ABAR'").fetchone()
        self.assertEqual(sub['answer1'], 'chicken')
        self.assertEqual(sub['answer2'], '')
        self.assertEqual(sub['answer3'], '')
        self.assertEqual(sub['answer4'], '')


class TestPhotoScanPageRoute(unittest.TestCase):
    """Test the /host/photo-scan page route"""

    def setUp(self):
        app.app.config['TESTING'] = True
        app.app.config['SECRET_KEY'] = 'test-secret'
        self.client = app.app.test_client()
        with self.client.session_transaction() as sess:
            sess['host_authenticated'] = True

    @patch('routes.scoring.AI_SCORING_ENABLED', False)
    def test_photo_scan_requires_ai(self):
        """Should redirect if AI not enabled"""
        response = self.client.get('/host/photo-scan', follow_redirects=False)
        self.assertEqual(response.status_code, 302)

    def test_photo_scan_requires_auth(self):
        """Should redirect to login if not authenticated"""
        client = app.app.test_client()
        response = client.get('/host/photo-scan')
        self.assertEqual(response.status_code, 302)

    def test_scan_alias_works(self):
        """The /host/scan alias should also work"""
        client = app.app.test_client()
        response = client.get('/host/scan')
        self.assertEqual(response.status_code, 302)  # Redirects to login without auth


class TestPhotoScanWaitingScreen(unittest.TestCase):
    """Test that photo scan shows waiting screen when no active round"""

    def setUp(self):
        app.app.config['TESTING'] = True
        app.app.config['SECRET_KEY'] = 'test-secret'
        self.client = app.app.test_client()
        with self.client.session_transaction() as sess:
            sess['host_authenticated'] = True

    @patch('routes.scoring.AI_SCORING_ENABLED', True)
    def test_no_active_round_shows_waiting_screen(self):
        """Should render waiting screen instead of redirecting when no active round"""
        response = self.client.get('/host/photo-scan')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Waiting for Round', response.data)

    @patch('routes.scoring.AI_SCORING_ENABLED', True)
    def test_no_active_round_does_not_redirect(self):
        """Should NOT redirect to dashboard when no active round"""
        response = self.client.get('/host/photo-scan', follow_redirects=False)
        self.assertEqual(response.status_code, 200)


class TestCheckActiveRoundEndpoint(unittest.TestCase):
    """Test that check-active-round returns round details"""

    def setUp(self):
        app.app.config['TESTING'] = True
        app.app.config['SECRET_KEY'] = 'test-secret'
        self.client = app.app.test_client()
        with self.client.session_transaction() as sess:
            sess['host_authenticated'] = True

    def test_no_active_round_returns_false(self):
        """Should return has_active_round: false with no extra fields"""
        response = self.client.get('/host/check-active-round')
        data = response.get_json()
        self.assertFalse(data['has_active_round'])
        self.assertNotIn('round_id', data)

    def test_active_round_returns_details(self):
        """Should return round_id and round_number when a round is active"""
        from database import db_connect
        with db_connect() as conn:
            conn.execute("""
                INSERT INTO rounds (round_number, question, num_answers, is_active,
                                    answer1, answer1_count)
                VALUES (3, 'Test Question', 4, 1, 'Test Answer', 10)
            """)
            conn.commit()
        try:
            response = self.client.get('/host/check-active-round')
            data = response.get_json()
            self.assertTrue(data['has_active_round'])
            self.assertIn('round_id', data)
            self.assertEqual(data['round_number'], 3)
        finally:
            with db_connect() as conn:
                conn.execute("DELETE FROM rounds")
                conn.commit()


if __name__ == '__main__':
    unittest.main(verbosity=2)
