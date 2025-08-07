import os
from unittest.mock import MagicMock, patch

import pg8000
import pytest
from mlservice.db import (
    MUTATING_KEYWORDS,
    SUSPICIOUS_PATTERNS,
    Settings,
    check_sql_injection_risk,
    detect_mutating_keywords,
    get_cnxn,
)


class TestSettings:
    """Test cases for Settings class."""

    @patch("aws_lambda_powertools.utilities.parameters.get_secret")
    @patch.dict(os.environ, {"SECRET_ID": "test-secret"})
    def test_settings_with_secret_id_username(self, mock_get_secret):
        """Test Settings with AWS Secrets Manager using 'username' key."""
        mock_secret = {
            "host": "test-host",
            "port": 5432,
            "username": "test-user",
            "password": "test-password",
            "dbname": "test-db",
        }
        mock_get_secret.return_value = mock_secret

        # When secret_id is provided in environment, Settings() should work
        settings = Settings()  # type: ignore

        assert settings.pg_host == "test-host"
        assert settings.pg_port == 5432
        assert settings.pg_user == "test-user"
        assert settings.pg_password == "test-password"
        assert settings.pg_dbname == "test-db"
        mock_get_secret.assert_called_once_with("test-secret", transform="json")

    @patch("aws_lambda_powertools.utilities.parameters.get_secret")
    @patch.dict(os.environ, {"SECRET_ID": "test-secret"})
    def test_settings_with_secret_id_user(self, mock_get_secret):
        """Test Settings with AWS Secrets Manager using 'user' key."""
        mock_secret = {
            "host": "test-host",
            "user": "test-user",
            "password": "test-password",
            "dbname": "test-db",
        }
        mock_get_secret.return_value = mock_secret

        settings = Settings()  # type: ignore

        assert settings.pg_host == "test-host"
        assert settings.pg_port == 5432  # Default port
        assert settings.pg_user == "test-user"
        assert settings.pg_password == "test-password"
        assert settings.pg_dbname == "test-db"

    @patch("aws_lambda_powertools.utilities.parameters.get_secret")
    @patch.dict(os.environ, {"SECRET_ID": "test-secret"})
    def test_settings_missing_host_key(self, mock_get_secret):
        """Test error when required key is missing from secret."""
        mock_secret = {
            "username": "test-user",
            "password": "test-password",
            "dbname": "test-db",
        }
        mock_get_secret.return_value = mock_secret

        with pytest.raises(KeyError, match="host"):
            Settings()  # type: ignore

    @patch.dict(
        os.environ,
        {
            "PG_HOST": "env-host",
            "PG_PORT": "3306",
            "PG_USER": "env-user",
            "PG_PASSWORD": "env-password",
            "PG_DBNAME": "env-db",
        },
        clear=True,
    )
    def test_settings_from_env_variables(self):
        """Test Settings from environment variables."""
        settings = Settings()  # type: ignore

        assert settings.pg_host == "env-host"
        assert settings.pg_port == 3306
        assert settings.pg_user == "env-user"
        assert settings.pg_password == "env-password"
        assert settings.pg_dbname == "env-db"

    @patch.dict(
        os.environ,
        {
            "PG_HOST": "env-host",
            "PG_USER": "env-user",
            "PG_PASSWORD": "env-password",
            "PG_DBNAME": "env-db",
        },
        clear=True,
    )
    def test_settings_from_env_variables_default_port(self):
        """Test Settings from environment variables with default port."""
        settings = Settings()  # type: ignore

        assert settings.pg_host == "env-host"
        assert settings.pg_port == 5432  # Default port when PG_PORT not set
        assert settings.pg_user == "env-user"
        assert settings.pg_password == "env-password"
        assert settings.pg_dbname == "env-db"

    @patch.dict(os.environ, {}, clear=True)
    def test_settings_no_connection_details(self):
        """Test Settings when no connection details are provided."""
        # Without secret_id or env vars, Settings should raise validation error
        # since required fields are missing
        with pytest.raises(ValueError):
            Settings()  # type: ignore

    def test_settings_default_values(self):
        """Test Settings default values for new fields."""
        settings = Settings(
            pg_host="test-host",
            pg_user="test-user",
            pg_password="test-password",
            pg_dbname="test-db",
        )

        # Test default values
        assert settings.read_only_connection is True
        assert settings.debug is False
        assert settings.pg_port == 5432
        assert settings.secret_id is None

    def test_settings_custom_values(self):
        """Test Settings with custom values."""
        settings = Settings(
            pg_host="test-host",
            pg_user="test-user",
            pg_password="test-password",
            pg_dbname="test-db",
            read_only_connection=False,
            debug=True,
            pg_port=3306,
        )

        assert settings.read_only_connection is False
        assert settings.debug is True
        assert settings.pg_port == 3306


class TestGetCnxn:
    """Test cases for get_cnxn function."""

    @patch("mlservice.db.pg8000.connect")
    def test_get_cnxn_success(self, mock_connect):
        """Test successful database connection."""
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection

        settings = Settings(
            pg_host="test-host",
            pg_port=5432,
            pg_user="test-user",
            pg_password="test-password",
            pg_dbname="test-db",
        )

        result = get_cnxn(settings)

        assert result == mock_connection
        mock_connect.assert_called_once_with(
            host="test-host",
            port=5432,
            user="test-user",
            password="test-password",
            database="test-db",
            ssl_context=True,
        )

    @patch("mlservice.db.pg8000.connect")
    def test_get_cnxn_connection_error(self, mock_connect):
        """Test database connection error."""
        mock_connect.side_effect = pg8000.Error("Connection failed")

        settings = Settings(
            pg_host="test-host",
            pg_port=5432,
            pg_user="test-user",
            pg_password="test-password",
            pg_dbname="test-db",
        )

        with pytest.raises(pg8000.Error, match="Connection failed"):
            get_cnxn(settings)


class TestDetectMutatingKeywords:
    """Test cases for detect_mutating_keywords function."""

    def test_detect_mutating_keywords_single_keyword(self):
        """Test detection of single mutating keyword."""
        sql = "SELECT * FROM users WHERE id = 1; INSERT INTO logs VALUES (1);"
        result = detect_mutating_keywords(sql)
        assert "INSERT" in result

    def test_detect_mutating_keywords_multiple_keywords(self):
        """Test detection of multiple mutating keywords."""
        sql = "INSERT INTO table1 VALUES (1); UPDATE table2 SET col = 'value'; DELETE FROM table3;"
        result = detect_mutating_keywords(sql)
        assert "INSERT" in result
        assert "UPDATE" in result
        assert "DELETE" in result

    def test_detect_mutating_keywords_case_insensitive(self):
        """Test case insensitive detection."""
        sql = (
            "insert into table values (1); UPDATE table set col = 1; Delete from table;"
        )
        result = detect_mutating_keywords(sql)
        assert "INSERT" in result
        assert "UPDATE" in result
        assert "DELETE" in result

    def test_detect_mutating_keywords_no_keywords(self):
        """Test SQL with no mutating keywords."""
        sql = "SELECT * FROM users WHERE status = 'active';"
        result = detect_mutating_keywords(sql)
        assert result == []

    def test_detect_mutating_keywords_deduplication(self):
        """Test deduplication of repeated keywords."""
        sql = "INSERT INTO table1 VALUES (1); INSERT INTO table2 VALUES (2);"
        result = detect_mutating_keywords(sql)
        assert set(result) == set(["INSERT"])

    def test_detect_mutating_keywords_all_keywords(self):
        """Test detection of various keyword types."""
        test_cases = [
            ("CREATE TABLE test (id INT);", ["CREATE"]),
            ("DROP TABLE test;", ["DROP"]),
            ("ALTER TABLE test ADD COLUMN name VARCHAR(50);", ["ALTER"]),
            ("GRANT SELECT ON table TO user;", ["GRANT"]),
            ("REVOKE SELECT ON table FROM user;", ["REVOKE"]),
            ("TRUNCATE TABLE test;", ["TRUNCATE"]),
            ("MERGE INTO target USING source ON condition;", ["MERGE"]),
            ("RENAME TABLE old TO new;", ["RENAME"]),
            ("CLUSTER table USING index;", ["CLUSTER"]),
            ("REINDEX INDEX test_idx;", ["REINDEX"]),
            ("VACUUM table;", ["VACUUM"]),
            ("ANALYZE table;", ["ANALYZE"]),
        ]

        for sql, expected in test_cases:
            result = detect_mutating_keywords(sql)
            assert all(keyword in result for keyword in expected), (
                f"Failed for SQL: {sql}"
            )

    def test_detect_mutating_keywords_word_boundaries(self):
        """Test that keywords are detected only as whole words."""
        sql = "SELECT * FROM table_insert WHERE column_update = 'delete_value';"
        result = detect_mutating_keywords(sql)
        assert result == []  # Should not detect keywords within other words


class TestCheckSqlInjectionRisk:
    """Test cases for check_sql_injection_risk function."""

    def test_check_sql_injection_numeric_tautology(self):
        """Test detection of numeric tautology SQL injection."""
        sql = "SELECT * FROM users WHERE id = 1 OR 1=1"
        result = check_sql_injection_risk(sql)
        assert len(result) == 1
        assert result[0]["type"] == "sql"
        assert result[0]["severity"] == "high"
        assert "Suspicious pattern" in result[0]["message"]

    def test_check_sql_injection_string_tautology(self):
        """Test detection of string tautology SQL injection."""
        sql = "SELECT * FROM users WHERE name = 'admin' OR 'a'='a'"
        result = check_sql_injection_risk(sql)
        assert len(result) == 1
        assert result[0]["type"] == "sql"
        assert result[0]["severity"] == "high"

    def test_check_sql_injection_drop_statement(self):
        """Test detection of DROP statement."""
        sql = "SELECT * FROM users; DROP TABLE users;"
        result = check_sql_injection_risk(sql)
        assert len(result) == 1
        assert result[0]["severity"] == "high"

    def test_check_sql_injection_truncate_statement(self):
        """Test detection of TRUNCATE statement."""
        sql = "SELECT * FROM users; TRUNCATE TABLE logs;"
        result = check_sql_injection_risk(sql)
        assert len(result) == 1

    def test_check_sql_injection_grant_revoke(self):
        """Test detection of GRANT/REVOKE statements."""
        test_cases = [
            "SELECT * FROM users; GRANT ALL ON *.* TO 'user'@'%';",
            "SELECT * FROM users; REVOKE ALL ON *.* FROM 'user'@'%';",
        ]
        for sql in test_cases:
            result = check_sql_injection_risk(sql)
            assert len(result) == 1

    def test_check_sql_injection_sleep_functions(self):
        """Test detection of sleep functions."""
        test_cases = [
            "SELECT * FROM users WHERE id = 1 AND SLEEP(5)",
            "SELECT * FROM users WHERE id = 1 AND PG_SLEEP(5)",
        ]
        for sql in test_cases:
            result = check_sql_injection_risk(sql)
            assert len(result) == 1

    def test_check_sql_injection_file_operations(self):
        """Test detection of file operation functions."""
        test_cases = [
            "SELECT * FROM users UNION SELECT LOAD_FILE('/etc/passwd')",
            "SELECT * FROM users INTO OUTFILE '/tmp/users.txt'",
        ]
        for sql in test_cases:
            result = check_sql_injection_risk(sql)
            assert len(result) == 1

    def test_check_sql_injection_case_insensitive(self):
        """Test case insensitive detection."""
        sql = "SELECT * FROM users WHERE id = 1 or 1=1"
        result = check_sql_injection_risk(sql)
        assert len(result) == 1

    def test_check_sql_injection_clean_sql(self):
        """Test clean SQL with no injection risks."""
        sql = "SELECT id, name, email FROM users WHERE status = 'active' AND created_date > '2023-01-01'"
        result = check_sql_injection_risk(sql)
        assert result == []

    def test_check_sql_injection_stops_at_first_match(self):
        """Test that function stops at first suspicious pattern found."""
        sql = "SELECT * FROM users WHERE id = 1 OR 1=1; DROP TABLE users;"
        result = check_sql_injection_risk(sql)
        assert (
            len(result) == 1
        )  # Should only return one issue despite multiple patterns

    def test_check_sql_injection_empty_sql(self):
        """Test with empty SQL string."""
        result = check_sql_injection_risk("")
        assert result == []

    def test_check_sql_injection_whitespace_variations(self):
        """Test detection with various whitespace patterns."""
        test_cases = [
            "SELECT * FROM users WHERE id = 1 OR  1 = 1",
            "SELECT * FROM users WHERE id = 1 OR\t1\t=\t1",
            "SELECT * FROM users WHERE id = 1 OR\n1\n=\n1",
        ]
        for sql in test_cases:
            result = check_sql_injection_risk(sql)
            assert len(result) == 1, f"Failed to detect injection in: {sql}"


class TestConstants:
    """Test cases for module constants."""

    def test_mutating_keywords_complete(self):
        """Test that MUTATING_KEYWORDS contains expected keywords."""
        expected_keywords = {
            "INSERT",
            "UPDATE",
            "DELETE",
            "MERGE",
            "TRUNCATE",
            "CREATE",
            "DROP",
            "ALTER",
            "RENAME",
            "GRANT",
            "REVOKE",
            "COMMENT ON",
            "SECURITY LABEL",
            "CREATE EXTENSION",
            "CREATE FUNCTION",
            "INSTALL",
            "CLUSTER",
            "REINDEX",
            "VACUUM",
            "ANALYZE",
        }
        assert expected_keywords.issubset(MUTATING_KEYWORDS)

    def test_suspicious_patterns_count(self):
        """Test that we have the expected number of suspicious patterns."""
        assert len(SUSPICIOUS_PATTERNS) == 9

    def test_suspicious_patterns_are_strings(self):
        """Test that all suspicious patterns are strings."""
        assert all(isinstance(pattern, str) for pattern in SUSPICIOUS_PATTERNS)


class TestIntegration:
    """Integration tests combining multiple functions."""

    @patch("aws_lambda_powertools.utilities.parameters.get_secret")
    @patch("mlservice.db.pg8000.connect")
    @patch.dict(os.environ, {"SECRET_ID": "test-secret"})
    def test_full_connection_flow_with_secret(self, mock_connect, mock_get_secret):
        """Test complete flow from Settings to establishing connection."""
        mock_secret = {
            "host": "test-host",
            "port": 5432,
            "username": "test-user",
            "password": "test-password",
            "dbname": "test-db",
        }
        mock_get_secret.return_value = mock_secret
        mock_connection = MagicMock()
        mock_connect.return_value = mock_connection

        # Create settings (will load from secret)
        settings = Settings()  # type: ignore

        # Establish connection
        connection = get_cnxn(settings)

        assert connection == mock_connection
        mock_connect.assert_called_once_with(
            host="test-host",
            port=5432,
            user="test-user",
            password="test-password",
            database="test-db",
            ssl_context=True,
        )

    def test_sql_security_checks_comprehensive(self):
        """Test comprehensive SQL security checking."""
        malicious_sql = "SELECT * FROM users WHERE id = 1 OR 1=1; DROP TABLE users;"

        # Check for injection risks
        injection_risks = check_sql_injection_risk(malicious_sql)
        assert len(injection_risks) == 1

        # Check for mutating keywords
        mutating_keywords = detect_mutating_keywords(malicious_sql)
        assert "DROP" in mutating_keywords
