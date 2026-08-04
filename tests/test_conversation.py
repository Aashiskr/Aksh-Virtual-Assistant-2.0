import unittest

from backend.brain.conversation import ConversationMemory


class ConversationMemoryTests(unittest.TestCase):
    def test_recent_turns_are_available_for_follow_up(self):
        memory = ConversationMemory(max_messages=4)
        memory.remember("Chrome kholo", "Chrome khol raha hoon.")
        memory.remember("ab usme YouTube kholo", "YouTube khol raha hoon.")
        self.assertEqual(
            [message["role"] for message in memory.messages()],
            ["user", "assistant", "user", "assistant"],
        )

    def test_old_turns_are_trimmed(self):
        memory = ConversationMemory(max_messages=2)
        memory.remember("one", "first")
        memory.remember("two", "second")
        self.assertEqual(memory.messages()[0]["content"], "two")


if __name__ == "__main__":
    unittest.main()
