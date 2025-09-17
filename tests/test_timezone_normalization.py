import unittest
from unittest.mock import patch

import pandas as pd
import pandas.testing as pdt

import bymacclbot


class EnsureUtcNaiveIndexTests(unittest.TestCase):
    def test_normalizes_tzaware_and_copies_tznaive_indexes(self):
        tzaware = pd.date_range("2024-01-01", periods=3, tz="America/Buenos_Aires")
        tznaive = pd.date_range("2024-01-01", periods=3)

        result_tzaware = bymacclbot.ensure_utc_naive_index(tzaware)
        result_tznaive = bymacclbot.ensure_utc_naive_index(tznaive)

        self.assertIsInstance(result_tzaware, pd.DatetimeIndex)
        self.assertIsNone(result_tzaware.tz)
        self.assertIsNot(result_tzaware, tzaware)
        expected_tzaware = tzaware.tz_convert("UTC").tz_localize(None)
        self.assertTrue(result_tzaware.equals(expected_tzaware))

        self.assertIsInstance(result_tznaive, pd.DatetimeIndex)
        self.assertIsNone(result_tznaive.tz)
        self.assertIsNot(result_tznaive, tznaive)
        self.assertTrue(result_tznaive.equals(tznaive))

        self.assertIsNotNone(tzaware.tz)
        self.assertIsNone(tznaive.tz)


class GetVarTimezoneNormalizationTests(unittest.TestCase):
    def test_get_var_handles_tzaware_indexes(self):
        tickers = ["ALUA.BA", "BMA.BA"]
        tz = "America/Buenos_Aires"
        dates = pd.date_range("2024-01-01", periods=3, tz=tz)
        columns = pd.MultiIndex.from_product([["Close"], tickers])
        bulk_close = pd.DataFrame(
            [
                [100.0, 200.0],
                [110.0, 190.0],
                [120.0, 195.0],
            ],
            index=dates,
            columns=columns,
        )
        ccl_series = pd.Series([100.0, 105.0, 110.0], index=dates, name="CCL")

        download_calls = []

        def fake_download(tickers_arg, *args, **kwargs):
            tickers_list = list(tickers_arg)
            download_calls.append(tickers_list)
            if tickers_list == tickers:
                return bulk_close.copy()
            raise AssertionError(f"Unexpected download call: {tickers_arg}")

        def fake_download_ccl(start, end):
            return ccl_series.copy()

        with patch.object(bymacclbot, "TICKERS", tickers), \
            patch.object(bymacclbot.yf, "download", side_effect=fake_download), \
            patch.object(bymacclbot, "download_ccl", side_effect=fake_download_ccl):
            result, message = bymacclbot.get_var("2024-01-01", "2024-01-04")

        self.assertEqual(download_calls, [tickers])
        self.assertEqual(message, "")

        expected_close = bulk_close["Close"].copy()
        expected_close.index = bymacclbot.ensure_utc_naive_index(expected_close.index)
        expected_ccl = ccl_series.copy()
        expected_ccl.index = bymacclbot.ensure_utc_naive_index(expected_ccl.index)
        expected_close_usd = expected_close.div(expected_ccl, axis=0)
        expected_series = (expected_close_usd.iloc[-1] / expected_close_usd.iloc[0] - 1.0) * 100.0
        expected_series = expected_series.dropna().sort_values()

        pdt.assert_series_equal(result, expected_series)
        self.assertTrue(result.equals(result.sort_values()))
        self.assertTrue(all(getattr(idx, "tzinfo", None) is None for idx in result.index))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
