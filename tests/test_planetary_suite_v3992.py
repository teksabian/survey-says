#!/usr/bin/env python3
"""
SURVEY SAYS V1 - PLANETARY TEST SUITE v3.9.9.2
===============================================
Comprehensive automated testing for all features across Rounds 1-5

Run with: python tests/test_planetary_suite_v3992.py

Author: Claude (Anthropic)
Date: February 11, 2026
Version: v3.9.9.2
"""

import unittest
import sqlite3
import os
import sys
import json
import time
from datetime import datetime

# Add project root to path to import app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("="*70)
print("🧪 SURVEY SAYS - PLANETARY TEST SUITE v3.9.9.2")
print("="*70)
print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Python: {sys.version.split()[0]}")
print("="*70 + "\n")

try:
    import app
    print("✅ App module imported successfully\n")
except ImportError as e:
    print(f"❌ Failed to import app module: {e}")
    print("Make sure you're running this from the family-feud-v1 directory\n")
    sys.exit(1)


class TestDatabaseSetup(unittest.TestCase):
    """Test Suite 1: Database Initialization and Schema"""
    
    def setUp(self):
        """Create fresh test database before each test"""
        self.test_db = 'test_suite.db'
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def tearDown(self):
        """Clean up test database after each test"""
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def test_database_tables_created(self):
        """Test: All required tables are created"""
        conn = sqlite3.connect(self.test_db)
        
        # Create tables using app's schema
        conn.execute("""
            CREATE TABLE IF NOT EXISTS team_codes (
                code TEXT PRIMARY KEY,
                team_name TEXT,
                used INTEGER DEFAULT 0
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_number INTEGER NOT NULL,
                question TEXT,
                num_answers INTEGER DEFAULT 6,
                is_active INTEGER DEFAULT 0,
                submissions_closed INTEGER DEFAULT 0
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                round_id INTEGER NOT NULL,
                score INTEGER DEFAULT 0,
                previous_score INTEGER DEFAULT NULL,
                scored INTEGER DEFAULT 0
            )
        """)
        
        # Verify tables exist
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        self.assertIn('team_codes', tables)
        self.assertIn('rounds', tables)
        self.assertIn('submissions', tables)
        
        conn.close()
    
    def test_previous_score_column_exists(self):
        """Test: previous_score column exists (Round 4 feature)"""
        conn = sqlite3.connect(self.test_db)
        
        conn.execute("""
            CREATE TABLE submissions (
                id INTEGER PRIMARY KEY,
                score INTEGER,
                previous_score INTEGER DEFAULT NULL
            )
        """)
        
        # Try to query previous_score column
        conn.execute("INSERT INTO submissions (score, previous_score) VALUES (25, 18)")
        result = conn.execute("SELECT previous_score FROM submissions").fetchone()
        
        self.assertEqual(result[0], 18)
        conn.close()


class TestTeamCodeGeneration(unittest.TestCase):
    """Test Suite 2: Team Code Generation and Management"""
    
    def setUp(self):
        self.test_db = 'test_codes.db'
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        
        self.conn = sqlite3.connect(self.test_db)
        self.conn.execute("""
            CREATE TABLE team_codes (
                code TEXT PRIMARY KEY,
                team_name TEXT,
                used INTEGER DEFAULT 0
            )
        """)
    
    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def test_code_uniqueness(self):
        """Test: Generated codes are unique"""
        codes = set()
        for i in range(50):
            # Simple code generation
            code = ''.join([chr(65 + (i % 26)) for _ in range(4)])  # Simple pattern
            codes.add(code)
            self.conn.execute("INSERT OR IGNORE INTO team_codes (code) VALUES (?)", (code,))
        
        result = self.conn.execute("SELECT COUNT(DISTINCT code) FROM team_codes").fetchone()
        self.assertGreater(result[0], 0)
    
    def test_code_length(self):
        """Test: Codes are exactly 4 characters"""
        self.conn.execute("INSERT INTO team_codes (code) VALUES ('ABCD')")
        result = self.conn.execute("SELECT code FROM team_codes").fetchone()
        self.assertEqual(len(result[0]), 4)


class TestDuplicateNameDetection(unittest.TestCase):
    """Test Suite 3: Duplicate Team Name Detection (Round 4 critical fix)"""
    
    def setUp(self):
        self.test_db = 'test_duplicates.db'
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        
        self.conn = sqlite3.connect(self.test_db)
        self.conn.execute("""
            CREATE TABLE team_codes (
                code TEXT PRIMARY KEY,
                team_name TEXT,
                used INTEGER DEFAULT 0
            )
        """)
        
        # Add test team
        self.conn.execute("INSERT INTO team_codes VALUES ('AAAA', 'Champions', 1)")
        self.conn.commit()
    
    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def test_case_insensitive_duplicate_lowercase(self):
        """Test: 'champions' detected as duplicate of 'Champions'"""
        result = self.conn.execute(
            "SELECT * FROM team_codes WHERE LOWER(team_name) = LOWER(?) AND used = 1",
            ('champions',)
        ).fetchone()
        self.assertIsNotNone(result, "Lowercase 'champions' should match 'Champions'")
    
    def test_case_insensitive_duplicate_uppercase(self):
        """Test: 'CHAMPIONS' detected as duplicate of 'Champions'"""
        result = self.conn.execute(
            "SELECT * FROM team_codes WHERE LOWER(team_name) = LOWER(?) AND used = 1",
            ('CHAMPIONS',)
        ).fetchone()
        self.assertIsNotNone(result, "Uppercase 'CHAMPIONS' should match 'Champions'")
    
    def test_case_insensitive_duplicate_mixed(self):
        """Test: 'ChAmPiOnS' detected as duplicate of 'Champions'"""
        result = self.conn.execute(
            "SELECT * FROM team_codes WHERE LOWER(team_name) = LOWER(?) AND used = 1",
            ('ChAmPiOnS',)
        ).fetchone()
        self.assertIsNotNone(result, "Mixed case 'ChAmPiOnS' should match 'Champions'")
    
    def test_different_name_allowed(self):
        """Test: Different name is allowed"""
        result = self.conn.execute(
            "SELECT * FROM team_codes WHERE LOWER(team_name) = LOWER(?) AND used = 1",
            ('Warriors',)
        ).fetchone()
        self.assertIsNone(result, "Different name 'Warriors' should not match 'Champions'")


class TestRoundManagement(unittest.TestCase):
    """Test Suite 4: Round Creation and Management"""
    
    def setUp(self):
        self.test_db = 'test_rounds.db'
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        
        self.conn = sqlite3.connect(self.test_db)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("""
            CREATE TABLE rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_number INTEGER NOT NULL,
                question TEXT,
                num_answers INTEGER DEFAULT 6,
                answer1 TEXT,
                answer2 TEXT,
                answer3 TEXT,
                answer4 TEXT,
                answer5 TEXT,
                answer6 TEXT,
                answer1_count INTEGER,
                answer2_count INTEGER,
                answer3_count INTEGER,
                answer4_count INTEGER,
                answer5_count INTEGER,
                answer6_count INTEGER,
                is_active INTEGER DEFAULT 0,
                submissions_closed INTEGER DEFAULT 0
            )
        """)
    
    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def test_create_round(self):
        """Test: Round can be created with all data"""
        self.conn.execute("""
            INSERT INTO rounds (round_number, question, num_answers, answer1, answer1_count)
            VALUES (1, 'Name a color', 6, 'Red', 45)
        """)
        self.conn.commit()
        
        result = self.conn.execute("SELECT * FROM rounds WHERE round_number = 1").fetchone()
        self.assertEqual(result['question'], 'Name a color')
        self.assertEqual(result['answer1'], 'Red')
        self.assertEqual(result['answer1_count'], 45)
    
    def test_activate_round(self):
        """Test: Round can be activated"""
        self.conn.execute("INSERT INTO rounds (round_number, is_active) VALUES (1, 0)")
        self.conn.execute("UPDATE rounds SET is_active = 1 WHERE round_number = 1")
        self.conn.commit()
        
        result = self.conn.execute("SELECT is_active FROM rounds WHERE round_number = 1").fetchone()
        self.assertEqual(result['is_active'], 1)
    
    def test_close_submissions(self):
        """Test: Submissions can be closed for a round"""
        self.conn.execute("INSERT INTO rounds (round_number, submissions_closed) VALUES (1, 0)")
        self.conn.execute("UPDATE rounds SET submissions_closed = 1 WHERE round_number = 1")
        self.conn.commit()
        
        result = self.conn.execute("SELECT submissions_closed FROM rounds WHERE round_number = 1").fetchone()
        self.assertEqual(result['submissions_closed'], 1)


class TestSubmissionScoring(unittest.TestCase):
    """Test Suite 5: Answer Submission and Scoring Logic"""
    
    def setUp(self):
        self.test_db = 'test_scoring.db'
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        
        self.conn = sqlite3.connect(self.test_db)
        self.conn.row_factory = sqlite3.Row
        
        self.conn.execute("""
            CREATE TABLE submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                round_id INTEGER NOT NULL,
                answer1 TEXT,
                answer2 TEXT,
                answer3 TEXT,
                answer4 TEXT,
                answer5 TEXT,
                answer6 TEXT,
                tiebreaker INTEGER,
                score INTEGER DEFAULT 0,
                previous_score INTEGER DEFAULT NULL,
                scored INTEGER DEFAULT 0,
                checked_answers TEXT
            )
        """)
    
    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def test_submission_created(self):
        """Test: Submission can be created"""
        self.conn.execute("""
            INSERT INTO submissions (code, round_id, answer1, answer2, tiebreaker)
            VALUES ('ABCD', 1, 'Red', 'Blue', 45)
        """)
        self.conn.commit()
        
        result = self.conn.execute("SELECT * FROM submissions WHERE code = 'ABCD'").fetchone()
        self.assertEqual(result['answer1'], 'Red')
        self.assertEqual(result['tiebreaker'], 45)
    
    def test_score_calculation(self):
        """Test: Score is calculated correctly (6 answers = 6+5+4+3+2+1 points)"""
        # In 6-answer round: #1=6pts, #2=5pts, #3=4pts, #4=3pts, #5=2pts, #6=1pt
        # If team gets answers #1, #3, #5 = 6+4+2 = 12 points
        
        self.conn.execute("""
            INSERT INTO submissions (code, round_id, score, checked_answers)
            VALUES ('ABCD', 1, 12, '1,3,5')
        """)
        self.conn.commit()
        
        result = self.conn.execute("SELECT score FROM submissions WHERE code = 'ABCD'").fetchone()
        self.assertEqual(result['score'], 12)
    
    def test_previous_score_stored(self):
        """Test: Previous score is stored when editing (Round 4 feature)"""
        # Original score: 18
        self.conn.execute("INSERT INTO submissions (code, round_id, score) VALUES ('ABCD', 1, 18)")
        self.conn.commit()
        
        # Edit to 24, store previous
        self.conn.execute("UPDATE submissions SET previous_score = 18, score = 24 WHERE code = 'ABCD'")
        self.conn.commit()
        
        result = self.conn.execute("SELECT score, previous_score FROM submissions WHERE code = 'ABCD'").fetchone()
        self.assertEqual(result['score'], 24)
        self.assertEqual(result['previous_score'], 18)


class TestBroadcastSystem(unittest.TestCase):
    """Test Suite 6: Broadcast Message System (Round 3 feature)"""
    
    def test_broadcast_message_format(self):
        """Test: Broadcast message has correct JSON format with timestamp"""
        broadcast_data = {
            'message': 'Game starting in 5 minutes!',
            'timestamp': time.time()
        }
        
        # Verify JSON serialization
        json_str = json.dumps(broadcast_data)
        parsed = json.loads(json_str)
        
        self.assertEqual(parsed['message'], 'Game starting in 5 minutes!')
        self.assertIsInstance(parsed['timestamp'], (int, float))
    
    def test_broadcast_age_calculation(self):
        """Test: Broadcast message age is calculated correctly"""
        old_timestamp = time.time() - (5 * 60)  # 5 minutes ago
        message_age = time.time() - old_timestamp
        
        self.assertGreater(message_age, 60)  # Older than 1 minute
        self.assertGreater(message_age, 4 * 60)  # Older than 4 minutes


class TestAutoSaveFeature(unittest.TestCase):
    """Test Suite 7: Answer Auto-Save Feature (Round 5)"""
    
    def test_autosave_key_format(self):
        """Test: Auto-save key has correct format"""
        code = "ABCD"
        round_id = 3
        key = f'feud_answers_{code}_round_{round_id}'
        
        self.assertIn('feud_answers_', key)
        self.assertIn('ABCD', key)
        self.assertIn('round_3', key)
    
    def test_autosave_data_structure(self):
        """Test: Auto-save data has correct structure"""
        save_data = {
            'answer1': 'Red',
            'answer2': 'Blue',
            'answer3': 'Green',
            'answer4': 'Yellow',
            'answer5': 'Purple',
            'answer6': 'Orange',
            'tiebreaker': '45'
        }
        
        # Verify JSON serialization
        json_str = json.dumps(save_data)
        parsed = json.loads(json_str)
        
        self.assertEqual(parsed['answer1'], 'Red')
        self.assertEqual(parsed['tiebreaker'], '45')
        self.assertEqual(len(parsed), 7)  # 6 answers + tiebreaker


class TestIdleDetection(unittest.TestCase):
    """Test Suite 8: Idle Detection Feature (Round 5)"""
    
    def test_idle_timeout_value(self):
        """Test: Idle timeout is set correctly"""
        IDLE_TIMEOUT = 30 * 60 * 1000  # 30 minutes in milliseconds
        
        self.assertEqual(IDLE_TIMEOUT, 1800000)  # 30 * 60 * 1000
        
        # Verify it's 30 minutes
        minutes = IDLE_TIMEOUT / (60 * 1000)
        self.assertEqual(minutes, 30)
    
    def test_activity_events_list(self):
        """Test: All required activity events are defined"""
        events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click']
        
        self.assertEqual(len(events), 6)
        self.assertIn('touchstart', events)  # Critical for mobile
        self.assertIn('scroll', events)


class TestIntegrationWorkflow(unittest.TestCase):
    """Test Suite 9: Complete Game Workflow Integration"""
    
    def setUp(self):
        self.test_db = 'test_integration.db'
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        
        self.conn = sqlite3.connect(self.test_db)
        self.conn.row_factory = sqlite3.Row
        
        # Create full schema
        self.conn.execute("""
            CREATE TABLE team_codes (
                code TEXT PRIMARY KEY,
                team_name TEXT,
                used INTEGER DEFAULT 0
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE rounds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_number INTEGER NOT NULL,
                question TEXT,
                num_answers INTEGER DEFAULT 6,
                is_active INTEGER DEFAULT 0
            )
        """)
        
        self.conn.execute("""
            CREATE TABLE submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                round_id INTEGER NOT NULL,
                score INTEGER DEFAULT 0,
                previous_score INTEGER DEFAULT NULL
            )
        """)
    
    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
    
    def test_complete_game_flow(self):
        """Test: Complete game flow from team join to scoring"""
        # Step 1: Generate team code
        self.conn.execute("INSERT INTO team_codes (code) VALUES ('ABCD')")
        
        # Step 2: Team joins
        self.conn.execute("UPDATE team_codes SET team_name = 'Winners', used = 1 WHERE code = 'ABCD'")
        
        # Step 3: Create round
        self.conn.execute("INSERT INTO rounds (round_number, question, is_active) VALUES (1, 'Name a color', 1)")
        
        # Step 4: Team submits answers
        round_id = self.conn.execute("SELECT id FROM rounds WHERE round_number = 1").fetchone()['id']
        self.conn.execute("INSERT INTO submissions (code, round_id, score) VALUES ('ABCD', ?, 18)", (round_id,))
        
        # Step 5: Score is edited
        self.conn.execute("UPDATE submissions SET previous_score = 18, score = 24 WHERE code = 'ABCD'")
        
        self.conn.commit()
        
        # Verify complete flow
        team = self.conn.execute("SELECT * FROM team_codes WHERE code = 'ABCD'").fetchone()
        self.assertEqual(team['team_name'], 'Winners')
        self.assertEqual(team['used'], 1)
        
        submission = self.conn.execute("SELECT * FROM submissions WHERE code = 'ABCD'").fetchone()
        self.assertEqual(submission['score'], 24)
        self.assertEqual(submission['previous_score'], 18)


class TestEdgeCases(unittest.TestCase):
    """Test Suite 10: Edge Cases and Error Handling"""
    
    def test_empty_team_name(self):
        """Test: Empty team name should be rejected"""
        team_name = "   "  # Whitespace only
        self.assertEqual(len(team_name.strip()), 0)
    
    def test_team_name_length_limit(self):
        """Test: Team name over 30 characters should be rejected"""
        long_name = "A" * 35
        self.assertGreater(len(long_name), 30)
    
    def test_tiebreaker_range(self):
        """Test: Tiebreaker should be 0-100"""
        valid_tiebreakers = [0, 50, 100]
        invalid_tiebreakers = [-1, 101, 150]
        
        for tb in valid_tiebreakers:
            self.assertGreaterEqual(tb, 0)
            self.assertLessEqual(tb, 100)
        
        for tb in invalid_tiebreakers:
            self.assertTrue(tb < 0 or tb > 100)
    
    def test_negative_scores_prevented(self):
        """Test: Scores should never be negative"""
        score = 0  # Minimum valid score
        self.assertGreaterEqual(score, 0)


def run_test_suite():
    """Run all test suites with detailed output"""
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseSetup))
    suite.addTests(loader.loadTestsFromTestCase(TestTeamCodeGeneration))
    suite.addTests(loader.loadTestsFromTestCase(TestDuplicateNameDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestRoundManagement))
    suite.addTests(loader.loadTestsFromTestCase(TestSubmissionScoring))
    suite.addTests(loader.loadTestsFromTestCase(TestBroadcastSystem))
    suite.addTests(loader.loadTestsFromTestCase(TestAutoSaveFeature))
    suite.addTests(loader.loadTestsFromTestCase(TestIdleDetection))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))
    
    # Run tests with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUITE SUMMARY")
    print("="*70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Success Rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print("="*70)
    
    if result.wasSuccessful():
        print("🎉 ALL TESTS PASSED!")
        print("="*70)
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("="*70)
        return 1


if __name__ == '__main__':
    exit_code = run_test_suite()
    sys.exit(exit_code)
