import unittest
from poker_worker.settlement import calculate_settlements

class TestSettlement(unittest.TestCase):
    def test_even_split(self):
        data = {"Alice": 10.0, "Bob": -10.0}
        result = calculate_settlements(data)
        self.assertEqual(result, [("Bob", "Alice", 10.0)])

    def test_multiple_players(self):
        data = {
            "Alice": 20.0,
            "Bob": -10.0,
            "Charlie": -10.0
        }
        result = calculate_settlements(data)
        # Bob pays Alice 10, Charlie pays Alice 10
        self.assertIn(("Bob", "Alice", 10.0), result)
        self.assertIn(("Charlie", "Alice", 10.0), result)

    def test_complex_split(self):
        data = {
            "Alice": 30.0,
            "Bob": -10.0,
            "Charlie": -15.0,
            "David": -5.0
        }
        result = calculate_settlements(data)
        total_paid = sum(amount for _, _, amount in result)
        self.assertEqual(total_paid, 30.0)

if __name__ == "__main__":
    unittest.main()
