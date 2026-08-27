import math
import unittest

from core.datatype import decode_value, encode_value, get_type_info, supported_types


class DataTypeTests(unittest.TestCase):
    def test_round_trip(self):
        values = {
            "int8": "-12",
            "uint8": "250",
            "int16": "-12345",
            "uint16": "54321",
            "int32": "-123456789",
            "uint32": "0xDEADBEEF",
            "int64": "-1234567890123",
            "uint64": "0x123456789ABCDEF0",
            "float": "12.5",
            "double": "-1234.125",
        }
        for type_name, text in values.items():
            raw = encode_value(text, type_name)
            self.assertEqual(len(raw), get_type_info(type_name).size)
            decoded = decode_value(raw, type_name)
            if type_name in ("float", "double"):
                self.assertTrue(math.isclose(decoded, float(text), rel_tol=1e-6, abs_tol=1e-6))
            else:
                self.assertEqual(decoded, int(text, 0))

    def test_supported_type_count(self):
        self.assertEqual(len(supported_types()), 10)

    def test_reject_nan(self):
        with self.assertRaises(ValueError):
            encode_value("nan", "float")


if __name__ == "__main__":
    unittest.main()
