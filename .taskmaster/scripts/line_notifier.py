#!/usr/bin/env python3
"""
Task Master自動実行システム向けLINE通知統合モジュール

LINE Notify APIを使用してエラー通知と実行サマリーを送信します。
httpxライブラリを使用したHTTPリクエスト（async対応済み）。

環境変数:
    LINE_NOTIFY_TOKEN: LINE Notify APIトークン（必須）
"""

import os
import sys
from datetime import datetime

import httpx


class LineNotifier:
    """LINE Notify API client using httpx"""

    API_ENDPOINT = "https://notify-api.line.me/api/notify"

    def __init__(self, token: str | None = None):
        """
        Initialize LINE Notifier

        Args:
            token: LINE Notify API token (defaults to LINE_NOTIFY_TOKEN env var)

        Raises:
            ValueError: If token is not provided and not found in environment
        """
        self.token = token or os.getenv("LINE_NOTIFY_TOKEN")
        if not self.token:
            raise ValueError(
                "LINE_NOTIFY_TOKEN environment variable not set. "
                "Please set it to your LINE Notify API token."
            )

    def send_notification(self, message: str, image_url: str | None = None) -> bool:
        """
        Send notification to LINE Notify API

        Args:
            message: Notification message (max 1000 chars)
            image_url: Optional image URL to attach

        Returns:
            True if notification sent successfully, False otherwise
        """
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {"message": message}

        if image_url:
            data["imageThumbnail"] = image_url
            data["imageFullsize"] = image_url

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(self.API_ENDPOINT, headers=headers, data=data)
                response.raise_for_status()
                return True
        except httpx.HTTPStatusError as e:
            print(
                f"❌ LINE Notify HTTP error: {e.response.status_code} - {e.response.text}",
                file=sys.stderr,
            )
            return False
        except httpx.RequestError as e:
            print(f"❌ LINE Notify request error: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"❌ LINE Notify unexpected error: {e}", file=sys.stderr)
            return False


def send_error_notification(
    task_id: str,
    task_title: str,
    task_key: str,
    error_message: str,
    retry_count: int = 0,
    max_retries: int = 0,
) -> bool:
    """
    Send task execution error notification to LINE

    Args:
        task_id: Task ID (e.g., "3.2.1")
        task_title: Task title
        task_key: Task key from allowed_tasks.yml
        error_message: Error message or exception
        retry_count: Current retry attempt
        max_retries: Maximum retry attempts configured

    Returns:
        True if notification sent successfully, False otherwise
    """
    notifier = LineNotifier()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    retry_status = f"Retry {retry_count}/{max_retries}" if max_retries > 0 else "No retry"

    message = f"""
🚨 Task Master Auto-Execution Error

📋 Task ID: {task_id}
📌 Title: {task_title}
🔑 Task Key: {task_key}
🔄 Status: {retry_status}
⏰ Time: {timestamp}

❌ Error:
{error_message}

Please check logs for details.
""".strip()

    return notifier.send_notification(message)


def send_success_summary(
    executed_tasks: list[dict], failed_tasks: list[dict], total_duration: float
) -> bool:
    """
    Send nightly execution summary to LINE

    Args:
        executed_tasks: List of successfully executed task dicts
        failed_tasks: List of failed task dicts
        total_duration: Total execution time in seconds

    Returns:
        True if notification sent successfully, False otherwise
    """
    notifier = LineNotifier()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    success_count = len(executed_tasks)
    failure_count = len(failed_tasks)
    total_count = success_count + failure_count

    # Status emoji
    status_emoji = "✅" if failure_count == 0 else "⚠️"

    # Summary header
    message = f"""
{status_emoji} Task Master Nightly Execution Summary

⏰ Completed: {timestamp}
⏱️ Duration: {total_duration:.1f}s
📊 Total: {total_count} tasks

✅ Success: {success_count}
❌ Failed: {failure_count}
""".strip()

    # Add executed tasks list
    if executed_tasks:
        message += "\n\n📋 Executed Tasks:"
        for task in executed_tasks[:5]:  # Max 5 tasks to keep message short
            message += f"\n  • {task['id']}: {task['title']}"
        if success_count > 5:
            message += f"\n  ... and {success_count - 5} more"

    # Add failed tasks list
    if failed_tasks:
        message += "\n\n❌ Failed Tasks:"
        for task in failed_tasks:
            message += f"\n  • {task['id']}: {task['title']}"

    return notifier.send_notification(message)


def main():
    """Test LINE notification functionality"""
    print("🔔 Testing LINE Notify integration...")

    # Test 1: Simple notification
    print("\n📤 Test 1: Sending simple notification...")
    notifier = LineNotifier()
    success = notifier.send_notification("✅ Task Master LINE integration test")
    print(f"Result: {'✅ Success' if success else '❌ Failed'}")

    # Test 2: Error notification
    print("\n📤 Test 2: Sending error notification...")
    success = send_error_notification(
        task_id="3.2.1",
        task_title="Nightly Integration Test Run",
        task_key="run_integration_tests",
        error_message="Exit code 1: 5 tests failed in test_async_client.py",
        retry_count=1,
        max_retries=2,
    )
    print(f"Result: {'✅ Success' if success else '❌ Failed'}")

    # Test 3: Success summary
    print("\n📤 Test 3: Sending execution summary...")
    success = send_success_summary(
        executed_tasks=[
            {"id": "3.2.1", "title": "Nightly Integration Test Run"},
            {"id": "8.1.2", "title": "Daily Security Scan"},
        ],
        failed_tasks=[{"id": "8.2.1", "title": "Weekly Performance Benchmark"}],
        total_duration=185.3,
    )
    print(f"Result: {'✅ Success' if success else '❌ Failed'}")

    print("\n✅ LINE Notify integration test completed!")


if __name__ == "__main__":
    main()
