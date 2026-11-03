import unittest

from adapter.msg_queue import toogle2nb
from plugins.math import Calculator
from toogle.message import Group, Member, MessageChain, Plain
from toogle.message_handler import MessagePack


class CalculatorTest(unittest.IsolatedAsyncioTestCase):
    async def test_results_preserve_decimals_as_outbound_text(self):
        cases = (
            ("1/8=", "0.125"),
            ("1.25+2.5=", "3.75"),
            ("-5/2=", "-2.5"),
            ("1/100000000=", "1e-08"),
            ("2^(-3)=", "0.125"),
            ("2+3=", "5"),
            ("10000000+0.125=", "10,000,000.125"),
        )
        calculator = Calculator()
        for message_type in ("group", "private"):
            for expression, expected in cases:
                with self.subTest(message_type=message_type, expression=expression):
                    message = MessagePack(
                        id=1,
                        message=MessageChain.plain(expression),
                        group=Group(100 if message_type == "group" else 0, "fixture"),
                        member=Member(200, "tester"),
                        quote=None,
                        message_type=message_type,
                    )
                    self.assertTrue(calculator.is_trigger(message))
                    result = await calculator.ret(message)
                    self.assertEqual(result.get(Plain)[0].text, expected)
                    self.assertTrue(result.asDisplay().endswith(expected))
                    self.assertEqual(
                        toogle2nb(result),
                        [
                            {"type": "reply", "data": {"id": message.id}},
                            {"type": "text", "data": {"text": expected}},
                        ],
                    )


if __name__ == "__main__":
    unittest.main()
