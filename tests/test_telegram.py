import unittest

from job_finder.notifications.telegram import TelegramNotifier


class TelegramNotifierTests(unittest.TestCase):
    def test_chunks_long_messages(self) -> None:
        notifier = TelegramNotifier("token", "chat")
        message = "\n".join([f"line {index} " + ("x" * 200) for index in range(60)])
        chunks = notifier._chunk_message(message)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(chunk) <= 3500 for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
