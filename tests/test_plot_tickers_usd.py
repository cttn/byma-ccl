import io
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

import bymacclbot


class PlotTickersUsdNormalizationTests(unittest.TestCase):
    def test_plot_tickers_usd_generates_bytes_and_keeps_tznaive_index(self):
        start = "2024-01-01"
        end = "2024-01-05"
        tz = "America/Buenos_Aires"
        dates = pd.date_range(start, periods=4, tz=tz)

        close_df = pd.DataFrame({"Close": [0.0, 110.0, 112.0, 115.0]}, index=dates)
        ccl_series = pd.Series([100.0, 102.0, 104.0, 106.0], index=dates, name="CCL")

        plots = []

        class FakeAxes:
            def __init__(self):
                self.plot_calls = []

            def plot(self, x, y, *args, **kwargs):
                self.plot_calls.append((x, y, args, kwargs))

            def set_ylabel(self, *_, **__):
                return None

            def set_xlabel(self, *_, **__):
                return None

            def set_title(self, *_, **__):
                return None

            def grid(self, *_, **__):
                return None

            def legend(self, *_, **__):
                return None

        class FakeFigure:
            def __init__(self, axes):
                self.axes = axes
                self.savefig_calls = []
                self.closed = False

            def savefig(self, bio, *args, **kwargs):
                self.savefig_calls.append((bio, args, kwargs))
                bio.write(b"fake-image-data")

            def close(self):
                self.closed = True

        figures = []

        def fake_subplots(*args, **kwargs):
            ax = FakeAxes()
            fig = FakeFigure(ax)
            plots.append(ax)
            figures.append(fig)
            return fig, ax

        def fake_close(fig):
            if hasattr(fig, "close"):
                fig.close()

        def fake_yf_download(tickers_arg, *args, **kwargs):
            tickers_list = list(tickers_arg)
            if tickers_list != ["ALUA.BA"]:
                raise AssertionError(f"Unexpected tickers: {tickers_list}")
            return close_df.copy()

        def fake_download_ccl(start_arg, end_arg):
            if (start_arg, end_arg) != (start, end):
                raise AssertionError((start_arg, end_arg))
            return ccl_series.copy()

        with patch.object(bymacclbot.yf, "download", side_effect=fake_yf_download), \
            patch.object(bymacclbot, "download_ccl", side_effect=fake_download_ccl), \
            patch.object(bymacclbot.plt, "subplots", side_effect=fake_subplots), \
            patch.object(bymacclbot.plt, "close", side_effect=fake_close):
            bio = bymacclbot.plot_tickers_usd(["ALUA"], start, end, normalize_flag=True)

        self.assertIsInstance(bio, io.BytesIO)
        self.assertGreater(bio.getbuffer().nbytes, 0)

        self.assertEqual(len(plots), 1)
        plot_calls = plots[0].plot_calls
        self.assertGreater(len(plot_calls), 0)
        for x, *_ in plot_calls:
            if isinstance(x, pd.Index):
                self.assertIsNone(getattr(x, "tz", None))
                self.assertTrue(all(getattr(ts, "tzinfo", None) is None for ts in x))

        self.assertTrue(all(fig.closed for fig in figures))

    def test_plot_tickers_usd_raises_when_no_valid_base_after_cleanup(self):
        start = "2024-02-01"
        end = "2024-02-05"
        tz = "America/Buenos_Aires"
        dates = pd.date_range(start, periods=4, tz=tz)

        close_df = pd.DataFrame({"Close": [0.0, 0.0, np.nan, 0.0]}, index=dates)
        ccl_series = pd.Series([100.0, 101.0, 102.0, 103.0], index=dates, name="CCL")

        def fake_yf_download(tickers_arg, *args, **kwargs):
            tickers_list = list(tickers_arg)
            if tickers_list != ["ALUA.BA"]:
                raise AssertionError(f"Unexpected tickers: {tickers_list}")
            return close_df.copy()

        def fake_download_ccl(start_arg, end_arg):
            if (start_arg, end_arg) != (start, end):
                raise AssertionError((start_arg, end_arg))
            return ccl_series.copy()

        with patch.object(bymacclbot.yf, "download", side_effect=fake_yf_download), \
            patch.object(bymacclbot, "download_ccl", side_effect=fake_download_ccl):
            with self.assertRaises(RuntimeError) as cm:
                bymacclbot.plot_tickers_usd(["ALUA"], start, end, normalize_flag=True)

        message = str(cm.exception)
        self.assertIn("No se encontraron valores válidos para normalizar", message)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
