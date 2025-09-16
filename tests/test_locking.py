import os
import types
import unittest

import bymacclbot


class _DummyFile:
    def __init__(self, fileno_value=1, start_pos=0):
        self._fileno = fileno_value
        self._position = start_pos

    def fileno(self):
        return self._fileno

    def tell(self):
        return self._position

    def seek(self, pos, whence=os.SEEK_SET):
        if whence == os.SEEK_SET:
            self._position = pos
        elif whence == os.SEEK_CUR:
            self._position += pos
        elif whence == os.SEEK_END:
            raise NotImplementedError("SEEK_END not supported in dummy file")
        else:
            raise ValueError(f"Unsupported whence={whence}")


class FileLockBackendTests(unittest.TestCase):
    def test_posix_backend_uses_fcntl_module(self):
        calls = []

        def fake_flock(fd, mode):
            calls.append((fd, mode))

        fake_fcntl = types.SimpleNamespace(
            LOCK_SH="LOCK_SH",
            LOCK_EX="LOCK_EX",
            LOCK_UN="LOCK_UN",
            flock=fake_flock,
        )

        backend = bymacclbot._create_posix_file_lock_backend(fake_fcntl)
        dummy = _DummyFile(fileno_value=10)

        backend.acquire(dummy, backend.LOCK_SH)
        backend.release(dummy)

        self.assertEqual(
            calls,
            [
                (10, fake_fcntl.LOCK_SH),
                (10, fake_fcntl.LOCK_UN),
            ],
        )

    def test_windows_backend_restores_position_and_modes(self):
        calls = []

        class FakeMsvcrt:
            LK_RLCK = "RLCK"
            LK_LOCK = "LOCK"
            LK_UNLCK = "UNLOCK"

            @staticmethod
            def locking(fd, mode, length):
                calls.append((fd, mode, length))

        backend = bymacclbot._create_windows_file_lock_backend(FakeMsvcrt)
        dummy = _DummyFile(fileno_value=11, start_pos=7)

        backend.acquire(dummy, backend.LOCK_SH)
        self.assertEqual(dummy.tell(), 7)
        backend.release(dummy)
        self.assertEqual(dummy.tell(), 7)

        with bymacclbot._locked_file(dummy, backend.LOCK_EX, _backend=backend):
            self.assertEqual(dummy.tell(), 7)

        expected_length = backend._LOCK_LENGTH
        self.assertEqual(
            calls,
            [
                (11, FakeMsvcrt.LK_RLCK, expected_length),
                (11, FakeMsvcrt.LK_UNLCK, expected_length),
                (11, FakeMsvcrt.LK_LOCK, expected_length),
                (11, FakeMsvcrt.LK_UNLCK, expected_length),
            ],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
