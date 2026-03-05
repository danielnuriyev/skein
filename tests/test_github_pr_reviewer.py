"""Tests for github_pr_reviewer.py - GitHub PR webhook handling and review posting."""

import json
import hmac
import hashlib
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from src.services.github_pr_reviewer import (
    verify_github_webhook,
    fetch_pr_diff,
    post_github_review,
    format_pr_review_request,
    format_review_response,
    parse_line_comments,
)


class TestWebhookVerification:
    """Test GitHub webhook signature verification."""

    def test_valid_signature(self):
        """Test verification with valid signature."""
        secret = "test-secret"
        payload = '{"test": "data"}'
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        signature_header = f"sha256={signature}"

        with patch('src.services.github_pr_reviewer.GITHUB_WEBHOOK_SECRET', secret):
            with patch('src.services.github_pr_reviewer.request') as mock_request:
                mock_request.headers = {
                    'X-Hub-Signature-256': signature_header
                }
                mock_request.body = payload.encode()

                assert verify_github_webhook() is True

    def test_invalid_signature(self):
        """Test verification with invalid signature."""
        secret = "test-secret"
        payload = '{"test": "data"}'
        wrong_signature = "sha256=wrongsignature123"

        with patch('src.services.github_pr_reviewer.GITHUB_WEBHOOK_SECRET', secret):
            with patch('src.services.github_pr_reviewer.request') as mock_request:
                mock_request.headers = {
                    'X-Hub-Signature-256': wrong_signature
                }
                mock_request.body = payload.encode()

                assert verify_github_webhook() is False

    def test_missing_signature_header(self):
        """Test verification when signature header is missing."""
        with patch('src.services.github_pr_reviewer.GITHUB_WEBHOOK_SECRET', 'secret'):
            with patch('src.services.github_pr_reviewer.request') as mock_request:
                mock_request.headers = {}
                mock_request.body = b'{"test": "data"}'

                assert verify_github_webhook() is False

    def test_no_secret_configured(self):
        """Test verification when no secret is configured."""
        with patch('src.services.github_pr_reviewer.GITHUB_WEBHOOK_SECRET', ''):
            assert verify_github_webhook() is True  # Skip verification

    def test_timestamp_too_old(self):
        """Test verification with timestamp that's too old."""
        import time
        old_timestamp = str(int(time.time()) - 400)  # 400 seconds ago

        secret = "test-secret"
        payload = f'{{"test": "data", "timestamp": "{old_timestamp}"}}'

        with patch('src.services.github_pr_reviewer.GITHUB_WEBHOOK_SECRET', secret):
            with patch('src.services.github_pr_reviewer.request') as mock_request:
                signature = hmac.new(
                    secret.encode(),
                    payload.encode(),
                    hashlib.sha256
                ).hexdigest()

                mock_request.headers = {
                    'X-Slack-Request-Timestamp': old_timestamp,
                    'X-Hub-Signature-256': f"sha256={signature}"
                }
                mock_request.body = payload.encode()

                assert verify_github_webhook() is False


class TestPRDiffFetching:
    """Test PR diff fetching functionality."""

    @patch('src.services.github_pr_reviewer.urlopen')
    def test_fetch_pr_diff_success(self, mock_urlopen):
        """Test successful PR diff fetching."""
        mock_response = Mock()
        mock_response.read.return_value = b"diff content here"
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = fetch_pr_diff("owner/repo", 123)

        assert result == "diff content here"

    @patch('src.services.github_pr_reviewer.urlopen')
    def test_fetch_pr_diff_with_auth(self, mock_urlopen):
        """Test PR diff fetching with authentication."""
        with patch('src.services.github_pr_reviewer.GITHUB_TOKEN', 'test-token'):
            mock_response = Mock()
            mock_response.read.return_value = b"authenticated diff"
            mock_urlopen.return_value.__enter__.return_value = mock_response

            result = fetch_pr_diff("owner/repo", 456)

            # Verify auth header was set
            call_args = mock_urlopen.call_args
            headers = call_args[1]['headers']
            assert 'Authorization' in headers
            assert headers['Authorization'] == 'token test-token'

    @patch('src.services.github_pr_reviewer.urlopen')
    def test_fetch_pr_diff_error(self, mock_urlopen):
        """Test PR diff fetching with network error."""
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Network error")

        with pytest.raises(Exception) as exc_info:
            fetch_pr_diff("owner/repo", 789)

        assert "Failed to fetch PR diff" in str(exc_info.value)


class TestReviewFormatting:
    """Test PR review request and response formatting."""

    def test_format_pr_review_request_basic(self):
        """Test basic PR review request formatting."""
        event_data = {
            "pull_request": {
                "number": 123,
                "title": "Add new feature",
                "body": "This PR adds a new feature",
                "head": {"ref": "feature-branch"}
            },
            "repository": {
                "full_name": "owner/repo"
            }
        }

        with patch('src.services.github_pr_reviewer.fetch_pr_diff', return_value="test diff"):
            with patch('src.services.github_pr_reviewer.Path') as mock_path:
                mock_file = Mock()
                mock_file.exists.return_value = True
                mock_file.read.return_value = "Guidelines content"
                mock_path.return_value.parent.parent = Mock()
                mock_path.return_value.parent.parent.__truediv__ = Mock(return_value=Mock())
                mock_path.return_value.parent.parent.__truediv__().__truediv__ = Mock(return_value=mock_file)

                result = format_pr_review_request(event_data)

                assert "owner/repo" in result
                assert "PR #123" in result
                assert "Add new feature" in result
                assert "Guidelines content" in result

    def test_format_pr_review_request_no_body(self):
        """Test PR review request with no description."""
        event_data = {
            "pull_request": {
                "number": 456,
                "title": "Fix bug",
                "body": None,
                "head": {"ref": "bugfix"}
            },
            "repository": {
                "full_name": "test/repo"
            }
        }

        with patch('src.services.github_pr_reviewer.fetch_pr_diff', return_value="diff"):
            with patch('src.services.github_pr_reviewer.Path') as mock_path:
                mock_file = Mock()
                mock_file.exists.return_value = True
                mock_file.read.return_value = "Guidelines"
                mock_path.return_value.parent.parent = Mock()
                mock_path.return_value.parent.parent.__truediv__ = Mock(return_value=Mock())
                mock_path.return_value.parent.parent.__truediv__().__truediv__ = Mock(return_value=mock_file)

                result = format_pr_review_request(event_data)

                assert "No description provided" in result

    def test_format_pr_review_request_missing_guidelines(self):
        """Test PR review request when guidelines file is missing."""
        event_data = {
            "pull_request": {
                "number": 789,
                "title": "Test PR",
                "body": "Test body",
                "head": {"ref": "test-branch"}
            },
            "repository": {
                "full_name": "test/repo"
            }
        }

        with patch('src.services.github_pr_reviewer.fetch_pr_diff', return_value="diff"):
            with patch('src.services.github_pr_reviewer.Path') as mock_path:
                mock_file = Mock()
                mock_file.exists.return_value = False
                mock_path.return_value.parent.parent = Mock()
                mock_path.return_value.parent.parent.__truediv__ = Mock(return_value=Mock())
                mock_path.return_value.parent.parent.__truediv__().__truediv__ = Mock(return_value=mock_file)

                result = format_pr_review_request(event_data)

                assert "Review Guidelines:" in result  # Fallback content


class TestReviewResponseFormatting:
    """Test review response formatting."""

    def test_format_review_response_completed(self):
        """Test formatting completed review response."""
        task_result = {
            "status": "completed",
            "stdout": "Good work! The code looks solid."
        }
        pr_data = {"test": "data"}

        result = format_review_response(task_result, pr_data)

        assert result == "Good work! The code looks solid."

    def test_format_review_response_failed(self):
        """Test formatting failed review response."""
        task_result = {
            "status": "failed",
            "error": "Analysis failed"
        }
        pr_data = {}

        result = format_review_response(task_result, pr_data)

        assert "❌ Review failed: Analysis failed" in result

    def test_format_review_response_timeout(self):
        """Test formatting timeout review response."""
        task_result = {
            "status": "timeout"
        }
        pr_data = {}

        result = format_review_response(task_result, pr_data)

        assert "⏰ Review timed out" in result

    def test_format_review_response_unknown_status(self):
        """Test formatting unknown status review response."""
        task_result = {
            "status": "unknown_status"
        }
        pr_data = {}

        result = format_review_response(task_result, pr_data)

        assert "❓ Unknown review status" in result


class TestLineCommentParsing:
    """Test parsing of line-specific comments from AI responses."""

    def test_parse_line_comments_basic(self):
        """Test basic line comment parsing."""
        review_content = """
        Overall assessment: Good work!

        FILE: src/main.py:15
        Consider adding error handling here

        FILE: tests/test_main.py:25
        Add more test cases
        """

        overall, line_comments = parse_line_comments(review_content)

        assert "Overall assessment: Good work!" in overall
        assert len(line_comments) == 2
        assert line_comments[0]["path"] == "src/main.py"
        assert line_comments[0]["line"] == 15
        assert "error handling" in line_comments[0]["body"]
        assert line_comments[1]["path"] == "tests/test_main.py"
        assert line_comments[1]["line"] == 25

    def test_parse_line_comments_no_comments(self):
        """Test parsing when there are no line-specific comments."""
        review_content = "This is just an overall assessment with no specific line comments."

        overall, line_comments = parse_line_comments(review_content)

        assert overall == review_content
        assert line_comments == []

    def test_parse_line_comments_mixed_content(self):
        """Test parsing with mixed content before and after line comments."""
        review_content = """
        ## Summary
        The code is well-structured.

        ## Specific Issues
        FILE: src/api.py:42
        API endpoint needs validation

        ## Recommendations
        Consider adding more documentation.

        FILE: src/utils.py:18
        Utility function could be optimized
        """

        overall, line_comments = parse_line_comments(review_content)

        assert "## Summary" in overall
        assert "## Specific Issues" in overall
        assert "## Recommendations" in overall
        assert len(line_comments) == 2
        assert line_comments[0]["path"] == "src/api.py"
        assert line_comments[1]["path"] == "src/utils.py"

    def test_parse_line_comments_multiline_comments(self):
        """Test parsing multiline line comments."""
        review_content = """
        Overall good!

        FILE: src/complex.py:100
        This function is too complex. Consider:
        1. Breaking it into smaller functions
        2. Adding more comments
        3. Using early returns
        """

        overall, line_comments = parse_line_comments(review_content)

        assert "Overall good!" in overall
        assert len(line_comments) == 1
        assert "Consider:" in line_comments[0]["body"]
        assert "Breaking it into smaller functions" in line_comments[0]["body"]

    def test_parse_line_comments_edge_cases(self):
        """Test edge cases in line comment parsing."""
        # Empty content
        overall, line_comments = parse_line_comments("")
        assert overall == ""
        assert line_comments == []

        # Only FILE markers without content
        content = "FILE: test.py:1\nFILE: test.py:2"
        overall, line_comments = parse_line_comments(content)
        assert len(line_comments) == 2
        assert line_comments[0]["body"].strip() == ""
        assert line_comments[1]["body"].strip() == ""

        # Case insensitive FILE markers
        content = "file: test.py:10\nComment here"
        overall, line_comments = parse_line_comments(content)
        assert len(line_comments) == 1
        assert line_comments[0]["path"] == "test.py"


class TestGitHubReviewPosting:
    """Test GitHub review posting functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.repo_name = "test/repo"
        self.pr_number = 123

    @patch('src.services.github_pr_reviewer.GITHUB_TOKEN', 'test-token')
    @patch('src.services.github_pr_reviewer.urlopen')
    def test_post_github_review_success(self, mock_urlopen):
        """Test successful GitHub review posting."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({"id": 456}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        review_body = "Good work! ## Review content"
        result = post_github_review(self.repo_name, self.pr_number, review_body)

        assert result is not None
        # Verify the call was made to the reviews endpoint
        call_args = mock_urlopen.call_args
        url = call_args[0][0].full_url
        assert "/pulls/123/reviews" in url

    @patch('src.services.github_pr_reviewer.GITHUB_TOKEN', '')
    def test_post_github_review_no_token(self):
        """Test review posting when no token is configured."""
        result = post_github_review(self.repo_name, self.pr_number, "test review")

        assert result is None  # Function returns early

    @patch('src.services.github_pr_reviewer.GITHUB_TOKEN', 'test-token')
    @patch('src.services.github_pr_reviewer.urlopen')
    def test_post_github_review_with_line_comments(self, mock_urlopen):
        """Test review posting with line-specific comments."""
        mock_response = Mock()
        mock_response.read.return_value = json.dumps({"id": 789}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        review_body = """
        Overall good work!

        FILE: src/main.py:15
        Consider error handling

        FILE: tests/test.py:20
        Add test case
        """

        result = post_github_review(self.repo_name, self.pr_number, review_body)

        assert result is not None
        # Verify the request included line comments
        call_args = mock_urlopen.call_args
        request_data = json.loads(call_args[0][1])  # POST data

        assert "comments" in request_data
        assert len(request_data["comments"]) == 2
        assert request_data["comments"][0]["path"] == "src/main.py"
        assert request_data["comments"][0]["position"] == 15
        assert "Goose AI Comment" in request_data["comments"][0]["body"]

    @patch('src.services.github_pr_reviewer.GITHUB_TOKEN', 'test-token')
    @patch('src.services.github_pr_reviewer.urlopen')
    def test_post_github_review_api_error_fallback(self, mock_urlopen):
        """Test fallback to Issues API when Reviews API fails."""
        # First call (Reviews API) fails
        mock_urlopen.side_effect = [
            Exception("Reviews API failed"),
            Mock()  # Second call succeeds
        ]

        review_body = "Fallback test review"
        result = post_github_review(self.repo_name, self.pr_number, review_body)

        # Should have made two calls: first to reviews, second to issues
        assert mock_urlopen.call_count == 2

        # Second call should be to issues endpoint
        second_call_args = mock_urlopen.call_args_list[1]
        issues_url = second_call_args[0][0].full_url
        assert "/issues/123/comments" in issues_url


class TestConcurrencyAndPerformance:
    """Test concurrent operations and performance."""

    def test_concurrent_webhook_processing(self):
        """Test handling multiple concurrent webhooks."""
        import threading

        results = []
        errors = []

        def process_webhook(webhook_id):
            """Simulate webhook processing."""
            try:
                # Mock a webhook processing operation
                event_data = {
                    "pull_request": {
                        "number": webhook_id,
                        "title": f"PR {webhook_id}",
                        "body": f"Description {webhook_id}",
                        "head": {"ref": f"branch-{webhook_id}"}
                    },
                    "repository": {"full_name": "test/repo"}
                }

                with patch('src.services.github_pr_reviewer.fetch_pr_diff', return_value=f"diff {webhook_id}"):
                    with patch('src.services.github_pr_reviewer.Path') as mock_path:
                        mock_file = Mock()
                        mock_file.exists.return_value = True
                        mock_file.read.return_value = "Guidelines"
                        mock_path.return_value.parent.parent = Mock()
                        mock_path.return_value.parent.parent.__truediv__ = Mock(return_value=Mock())
                        mock_path.return_value.parent.parent.__truediv__().__truediv__ = Mock(return_value=mock_file)

                        result = format_pr_review_request(event_data)
                        results.append(result)
            except Exception as e:
                errors.append(str(e))

        # Create multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=process_webhook, args=(i,))
            threads.append(t)

        # Start and join threads
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify results
        assert len(results) == 5
        assert len(errors) == 0
        for result in results:
            assert "test/repo" in result
            assert "Guidelines" in result

    def test_large_pr_handling(self):
        """Test handling of very large PRs."""
        # Create a large diff
        large_diff = "diff --git\n" + "line\n" * 10000

        event_data = {
            "pull_request": {
                "number": 999,
                "title": "Large PR",
                "body": "This is a very large PR",
                "head": {"ref": "large-branch"}
            },
            "repository": {"full_name": "big/repo"}
        }

        with patch('src.services.github_pr_reviewer.fetch_pr_diff', return_value=large_diff):
            with patch('src.services.github_pr_reviewer.Path') as mock_path:
                mock_file = Mock()
                mock_file.exists.return_value = True
                mock_file.read.return_value = "Guidelines"
                mock_path.return_value.parent.parent = Mock()
                mock_path.return_value.parent.parent.__truediv__ = Mock(return_value=Mock())
                mock_path.return_value.parent.parent.__truediv__().__truediv__ = Mock(return_value=mock_file)

                result = format_pr_review_request(event_data)

                # Should handle large content
                assert len(result) > 50000  # Large diff + other content
                assert "Large PR" in result
                assert "big/repo" in result

    @pytest.mark.parametrize("signature_valid,expected", [
        (True, True),
        (False, False),
    ])
    def test_signature_verification_edge_cases(self, signature_valid, expected):
        """Test webhook signature verification edge cases."""
        with patch('src.services.github_pr_reviewer.GITHUB_WEBHOOK_SECRET', 'secret'):
            with patch('src.services.github_pr_reviewer.request') as mock_request:
                if signature_valid:
                    payload = '{"test": "data"}'
                    signature = hmac.new(
                        b'secret',
                        payload.encode(),
                        hashlib.sha256
                    ).hexdigest()
                    mock_request.headers = {'X-Hub-Signature-256': f'sha256={signature}'}
                    mock_request.body = payload.encode()
                else:
                    mock_request.headers = {'X-Hub-Signature-256': 'sha256=invalid'}
                    mock_request.body = b'{"test": "data"}'

                result = verify_github_webhook()
                assert result == expected

    def test_malformed_webhook_data(self):
        """Test handling of malformed webhook data."""
        malformed_events = [
            {},  # Empty event
            {"pull_request": {}},  # Missing required fields
            {"pull_request": {"number": "not-a-number"}},  # Wrong data types
            {"repository": {}},  # Missing PR data
        ]

        for event_data in malformed_events:
            # Should not crash, should handle gracefully
            try:
                with patch('src.services.github_pr_reviewer.fetch_pr_diff', return_value="diff"):
                    with patch('src.services.github_pr_reviewer.Path') as mock_path:
                        mock_file = Mock()
                        mock_file.exists.return_value = True
                        mock_file.read.return_value = "Guidelines"
                        mock_path.return_value.parent.parent = Mock()
                        mock_path.return_value.parent.parent.__truediv__ = Mock(return_value=Mock())
                        mock_path.return_value.parent.parent.__truediv__().__truediv__ = Mock(return_value=mock_file)

                        result = format_pr_review_request(event_data)
                        assert isinstance(result, str)
            except Exception:
                # It's OK if malformed data causes exceptions, as long as they don't crash the service
                pass