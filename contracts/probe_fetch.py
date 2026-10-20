# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Throwaway probe #2 v2 (NOT part of the product).

Answers, on the live Studio network:
  A. Is the in-contract clock the *transaction timestamp* (same for all
     validators) or the wall clock?
  B. Can a contract fetch a public https page inside a non-deterministic block?
  C. Does `run_nondet_unsafe` reach consensus when leader and validator both
     fetch the page independently?
  D. Does the sandboxed variant `run_nondet` also reach consensus?
  E. Positive control: does `run_nondet_unsafe` reach consensus at all when
     neither side touches the network?  (guards against "refusal for the wrong
     reason")
"""

import hashlib
import time

import genlayer.gl as gl
from genlayer.py.types import u256


def _digest(body: bytes) -> bytes:
    return hashlib.sha256(body).digest()


def _same(a, b) -> bool:
    """Compare two encoded results field by field.

    NOTE: calldata decodes a tuple into a *list*, so `a == b` on the decoded
    value is always False.  Element-wise comparison is required.
    """
    if a is None or b is None:
        return False
    la = list(a)
    lb = list(b)
    if len(la) != len(lb):
        return False
    for x, y in zip(la, lb):
        if isinstance(x, (bytes, bytearray)):
            if bytes(x) != bytes(y):
                return False
        elif int(x) != int(y):
            return False
    return True


class ProbeFetch(gl.Contract):
    clock: u256
    ctl_ok: bool
    nd_ok: bool
    nd_status: u256
    nd_len: u256
    nd_digest: bytes
    sb_ok: bool
    sb_status: u256
    sb_len: u256
    sb_digest: bytes
    plain_err: str

    def __init__(self) -> None:
        self.clock = u256(0)
        self.ctl_ok = False
        self.nd_ok = False
        self.nd_status = u256(0)
        self.nd_len = u256(0)
        self.nd_digest = b"\x00" * 32
        self.sb_ok = False
        self.sb_status = u256(0)
        self.sb_len = u256(0)
        self.sb_digest = b"\x00" * 32
        self.plain_err = ""

    @gl.public.write
    def probe_clock(self) -> None:
        self.clock = u256(int(time.time()))

    @gl.public.write
    def probe_plain(self, url: str) -> None:
        try:
            resp = gl.nondet.web.get(url)
            body = resp.body or b""
            self.plain_err = "ok:%d:%d" % (int(resp.status), len(body))
        except Exception as exc:  # noqa: BLE001
            self.plain_err = "err:" + str(exc)[:200]

    @gl.public.write
    def probe_control(self) -> None:
        """Positive control: no network at all."""

        def leader():
            return (7, 8, b"\xaa" * 32)

        def validator(leader_res):
            if not isinstance(leader_res, gl.vm.Return):
                return False
            return _same(leader(), leader_res.calldata)

        try:
            res = gl.vm.run_nondet_unsafe(leader, validator)
            self.ctl_ok = bool(_same(res, (7, 8, b"\xaa" * 32)))
        except Exception as exc:  # noqa: BLE001
            self.ctl_ok = False
            self.plain_err = "ctl:" + str(exc)[:200]

    @gl.public.write
    def probe_nondet(self, url: str) -> None:
        def leader():
            resp = gl.nondet.web.get(url)
            body = resp.body or b""
            return (int(resp.status), len(body), _digest(body))

        def validator(leader_res):
            if not isinstance(leader_res, gl.vm.Return):
                return False
            return _same(leader(), leader_res.calldata)

        try:
            res = gl.vm.run_nondet_unsafe(leader, validator)
            self.nd_ok = True
            self.nd_status = u256(int(res[0]))
            self.nd_len = u256(int(res[1]))
            self.nd_digest = bytes(res[2])
        except Exception as exc:  # noqa: BLE001
            self.nd_ok = False
            self.nd_digest = hashlib.sha256(str(exc).encode()).digest()

    @gl.public.write
    def probe_sandbox(self, url: str) -> None:
        def leader():
            resp = gl.nondet.web.get(url)
            body = resp.body or b""
            return (int(resp.status), len(body), _digest(body))

        def validator(leader_res):
            if not isinstance(leader_res, gl.vm.Return):
                return False
            return _same(leader(), leader_res.calldata)

        try:
            res = gl.vm.run_nondet(leader, validator)
            self.sb_ok = True
            self.sb_status = u256(int(res[0]))
            self.sb_len = u256(int(res[1]))
            self.sb_digest = bytes(res[2])
        except Exception as exc:  # noqa: BLE001
            self.sb_ok = False
            self.sb_digest = hashlib.sha256(str(exc).encode()).digest()

    @gl.public.view
    def get_clock(self) -> u256:
        return self.clock

    @gl.public.view
    def get_ctl(self) -> bool:
        return self.ctl_ok

    @gl.public.view
    def get_plain_err(self) -> str:
        return self.plain_err

    @gl.public.view
    def get_nd(self) -> tuple[bool, u256, u256, bytes]:
        return (self.nd_ok, self.nd_status, self.nd_len, self.nd_digest)

    @gl.public.view
    def get_sb(self) -> tuple[bool, u256, u256, bytes]:
        return (self.sb_ok, self.sb_status, self.sb_len, self.sb_digest)
