# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Falsifiable — a stake market on checkable claims about a public web page.

A market is one https URL + one precisely-worded claim + one machine-checkable
rule + a fixed close time.  People stake native GEN on YES or NO.  When the
window closes, validators independently fetch the page and decide YES, NO or
UNDETERMINED under the market's own written rule.  The whole pot is split pro
rata among the winning side; UNDETERMINED refunds everybody; a single-sided
pool refunds everybody.  Winnings are pulled through `withdraw`, never pushed.

Not escrow.  Not arbitration.  Not a court.  No appeals, no fees, no admin
payouts, and no owner.
"""

import hashlib
import json
import time

import genlayer.gl as gl
from genlayer.py.types import Address, u8, u64, u256
from genlayer.py.storage import DynArray, TreeMap, allow_storage

# --------------------------------------------------------------------------
# States
# --------------------------------------------------------------------------

STATUS_OPEN = 0
STATUS_CLOSED = 1
STATUS_RESOLVED_YES = 2
STATUS_RESOLVED_NO = 3
STATUS_RESOLVED_UNDETERMINED = 4
STATUS_RESOLVED_REFUNDED = 5

# --------------------------------------------------------------------------
# Sides and outcomes
# --------------------------------------------------------------------------

SIDE_YES = 0
SIDE_NO = 1

OUTCOME_NONE = 0
OUTCOME_YES = 1
OUTCOME_NO = 2
OUTCOME_UNDETERMINED = 3

# --------------------------------------------------------------------------
# The closed set of rules.  There is no regex, no LLM and no free text: the
# outcome is a pure function of (bytes fetched, rule).
# --------------------------------------------------------------------------

RULE_BODY_CONTAINS = 1
RULE_BODY_EQUALS = 2
RULE_TITLE_CONTAINS = 3
RULE_TITLE_EQUALS = 4
RULE_JSON_FIELD_CONTAINS = 5
RULE_JSON_FIELD_EQUALS = 6

VALID_RULE_KINDS = (
    RULE_BODY_CONTAINS,
    RULE_BODY_EQUALS,
    RULE_TITLE_CONTAINS,
    RULE_TITLE_EQUALS,
    RULE_JSON_FIELD_CONTAINS,
    RULE_JSON_FIELD_EQUALS,
)

JSON_RULE_KINDS = (RULE_JSON_FIELD_CONTAINS, RULE_JSON_FIELD_EQUALS)

# --------------------------------------------------------------------------
# Parameters
# --------------------------------------------------------------------------

MIN_STAKE = 1_000_000_000_000_000  # 0.001 GEN
RESOLUTION_WINDOW = 3600  # seconds after close_time before the deterministic refund
MIN_HORIZON = 60  # a market must close at least this far in the future
MAX_HORIZON = 30 * 24 * 3600  # ... and at most this far
MAX_URL_LEN = 512
MAX_CLAIM_LEN = 512
MAX_PARAM_LEN = 1024
MAX_PATH_LEN = 128

EMPTY_DIGEST = b"\x00" * 32


# --------------------------------------------------------------------------
# Evidence extraction — pure functions, safe to run inside a non-deterministic
# block on the leader and on every validator.
# --------------------------------------------------------------------------


def _extract_title(body: bytes):
    """Return the text of the first <title> element, stripped, or None."""
    lowered = body.lower()
    start = lowered.find(b"<title")
    if start < 0:
        return None
    open_gt = lowered.find(b">", start)
    if open_gt < 0:
        return None
    end = lowered.find(b"</title>", open_gt)
    if end < 0:
        return None
    return body[open_gt + 1 : end].strip()


def _json_path_value(doc, path: str):
    """Walk a dotted path.  Returns (found, value)."""
    if path == "":
        return (True, doc)
    current = doc
    for segment in path.split("."):
        if isinstance(current, dict):
            if segment not in current:
                return (False, None)
            current = current[segment]
        elif isinstance(current, list):
            try:
                index = int(segment)
            except ValueError:
                return (False, None)
            if index < 0 or index >= len(current):
                return (False, None)
            current = current[index]
        else:
            return (False, None)
    return (True, current)


def _json_display(value) -> str:
    """Deterministic textual form of a JSON value."""
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _extract_evidence(body: bytes, kind: int, path: str):
    """The exact bytes the rule is applied to, or None if they cannot be read."""
    if kind in (RULE_BODY_CONTAINS, RULE_BODY_EQUALS):
        return body
    if kind in (RULE_TITLE_CONTAINS, RULE_TITLE_EQUALS):
        return _extract_title(body)
    if kind in JSON_RULE_KINDS:
        try:
            doc = json.loads(body.decode("utf-8"))
        except Exception:
            return None
        found, value = _json_path_value(doc, path)
        if not found:
            return None
        return _json_display(value).encode("utf-8")
    return None


def _evaluate(evidence: bytes, kind: int, param: str) -> int:
    """YES / NO from bytes and a literal.  Never anything else."""
    needle = param.encode("utf-8")
    if kind in (RULE_BODY_EQUALS, RULE_TITLE_EQUALS, RULE_JSON_FIELD_EQUALS):
        return OUTCOME_YES if evidence == needle else OUTCOME_NO
    return OUTCOME_YES if needle in evidence else OUTCOME_NO


def _fetch_and_evaluate(url: str, kind: int, param: str, path: str):
    """Fetch the page and rule on it.  Returns (outcome:int, digest:bytes).

    Never raises: a failed fetch is an UNDETERMINED outcome with the empty
    digest, so that every validator which also fails agrees with the leader.
    """
    try:
        response = gl.nondet.web.get(url)
    except Exception:
        return (OUTCOME_UNDETERMINED, hashlib.sha256(b"").digest())
    status = int(response.status)
    body = response.body or b""
    if status < 200 or status >= 300:
        return (OUTCOME_UNDETERMINED, hashlib.sha256(b"").digest())
    evidence = _extract_evidence(body, kind, path)
    if evidence is None:
        return (OUTCOME_UNDETERMINED, hashlib.sha256(b"").digest())
    return (_evaluate(evidence, kind, param), hashlib.sha256(evidence).digest())


def _same_result(mine, theirs) -> bool:
    """Compare two encoded results field by field.

    `genlayer.py.calldata` decodes a tuple into a *list*, so comparing the
    decoded value to a tuple with `==` is always False.  Compare fields.
    """
    if mine is None or theirs is None:
        return False
    left = list(mine)
    right = list(theirs)
    if len(left) != len(right):
        return False
    for a, b in zip(left, right):
        if isinstance(a, (bytes, bytearray)):
            if bytes(a) != bytes(b):
                return False
        else:
            if int(a) != int(b):
                return False
    return True


# --------------------------------------------------------------------------
# Storage records
# --------------------------------------------------------------------------


@allow_storage
class Position:
    """One account's stake in one market."""

    yes: u256
    no: u256
    settled_yes: u256
    settled_no: u256

    def __init__(self) -> None:
        self.yes = u256(0)
        self.no = u256(0)
        self.settled_yes = u256(0)
        self.settled_no = u256(0)


def _new_position() -> Position:
    return Position()


@allow_storage
class Market:
    """One market: a claim, the rule that decides it, and the pot."""

    creator: Address
    url: str
    claim: str
    rule_kind: u8
    rule_param: str
    rule_path: str
    close_time: u64
    status: u8
    rule_outcome: u8
    pot_yes: u256
    pot_no: u256
    payout_pot: u256
    settled_yes_stake: u256
    settled_no_stake: u256
    evidence_digest: bytes
    positions: TreeMap[Address, Position]

    def __init__(self) -> None:
        self.creator = gl.message.sender_address
        self.url = ""
        self.claim = ""
        self.rule_kind = u8(0)
        self.rule_param = ""
        self.rule_path = ""
        self.close_time = u64(0)
        self.status = u8(STATUS_OPEN)
        self.rule_outcome = u8(OUTCOME_NONE)
        self.pot_yes = u256(0)
        self.pot_no = u256(0)
        self.payout_pot = u256(0)
        self.settled_yes_stake = u256(0)
        self.settled_no_stake = u256(0)
        self.evidence_digest = EMPTY_DIGEST
        self.positions = TreeMap()


# --------------------------------------------------------------------------
# The contract
# --------------------------------------------------------------------------


class Falsifiable(gl.Contract):
    """Stake market on checkable claims about a public web page."""

    markets: DynArray[Market]
    total_staked: u256
    total_paid: u256

    def __init__(self) -> None:
        pass

    # -- helpers ---------------------------------------------------------

    def _now(self) -> int:
        """The transaction timestamp.

        GenLayer v0.2.16 pins the contract clock to the transaction timestamp,
        so this is identical for the leader and for every validator.  It is
        used only as a gate, never as evidence.
        """
        return int(time.time())

    def _market(self, market_id: int) -> Market:
        if market_id < 0 or market_id >= len(self.markets):
            raise gl.vm.UserError("no such market")
        return self.markets[market_id]

    def _entitlement(self, market: Market, side: int, remaining: int) -> int:
        """What the caller is owed on one side, right now."""
        if remaining <= 0:
            return 0
        status = int(market.status)
        if status in (STATUS_RESOLVED_UNDETERMINED, STATUS_RESOLVED_REFUNDED):
            # Everybody is made exactly whole; no division, so no dust.
            return remaining
        outcome = int(market.rule_outcome)
        won = (side == SIDE_YES and outcome == OUTCOME_YES) or (
            side == SIDE_NO and outcome == OUTCOME_NO
        )
        if not won:
            return 0
        pool = int(market.pot_yes) if side == SIDE_YES else int(market.pot_no)
        total = int(market.payout_pot)
        if pool <= 0 or total <= 0:
            return 0
        settled = (
            int(market.settled_yes_stake)
            if side == SIDE_YES
            else int(market.settled_no_stake)
        )
        # Cumulative allocation: the shares telescope to exactly `total`,
        # in any withdrawal order, with no rounding dust.
        return (total * (settled + remaining)) // pool - (total * settled) // pool

    # -- create ----------------------------------------------------------

    @gl.public.write
    def create_market(
        self,
        url: str,
        claim: str,
        rule_kind: u8,
        rule_param: str,
        rule_path: str,
        close_time: u64,
    ) -> u64:
        """Open a market on one https page with one checkable claim.

        The creator is always `gl.message.sender_address`; there is no way to name a
        different account anywhere in this contract.
        """
        if not url.startswith("https://"):
            raise gl.vm.UserError("url must be an https url")
        if len(url) > MAX_URL_LEN:
            raise gl.vm.UserError("url is too long")
        if any(ch.isspace() for ch in url):
            raise gl.vm.UserError("url must not contain whitespace")
        if len(claim) == 0:
            raise gl.vm.UserError("claim must not be empty")
        if len(claim) > MAX_CLAIM_LEN:
            raise gl.vm.UserError("claim is too long")
        if int(rule_kind) not in VALID_RULE_KINDS:
            raise gl.vm.UserError("unknown rule kind")
        if len(rule_param) == 0:
            raise gl.vm.UserError("rule parameter must not be empty")
        if len(rule_param) > MAX_PARAM_LEN:
            raise gl.vm.UserError("rule parameter is too long")
        if len(rule_path) > MAX_PATH_LEN:
            raise gl.vm.UserError("rule path is too long")
        if int(rule_kind) in JSON_RULE_KINDS and len(rule_path) == 0:
            raise gl.vm.UserError("json rules need a path")
        now = self._now()
        horizon = int(close_time) - now
        if horizon < MIN_HORIZON:
            raise gl.vm.UserError("close time is too close")
        if horizon > MAX_HORIZON:
            raise gl.vm.UserError("close time is too far away")

        market = Market()
        market.url = url
        market.claim = claim
        market.rule_kind = u8(int(rule_kind))
        market.rule_param = rule_param
        market.rule_path = rule_path
        market.close_time = u64(int(close_time))
        market.status = u8(STATUS_OPEN)
        market.rule_outcome = u8(OUTCOME_NONE)
        market.pot_yes = u256(0)
        market.pot_no = u256(0)
        market.payout_pot = u256(0)
        market.settled_yes_stake = u256(0)
        market.settled_no_stake = u256(0)
        market.evidence_digest = EMPTY_DIGEST
        market.positions = TreeMap()

        self.markets.append(market)
        return u64(len(self.markets) - 1)

    # -- stake -----------------------------------------------------------

    @gl.public.write.payable
    def stake(self, market_id: u64, side: u8) -> None:
        """Back YES (side 0) or NO (side 1) with native GEN."""
        market = self._market(int(market_id))
        if int(market.status) != STATUS_OPEN:
            raise gl.vm.UserError("market is not open")
        if self._now() >= int(market.close_time):
            raise gl.vm.UserError("market has closed")
        if int(side) != SIDE_YES and int(side) != SIDE_NO:
            raise gl.vm.UserError("side must be 0 (yes) or 1 (no)")
        if gl.message.sender_address == market.creator:
            raise gl.vm.UserError("the creator cannot stake on their own market")
        value = int(gl.message.value)
        if value < MIN_STAKE:
            raise gl.vm.UserError("stake is below the minimum")
        if value == 0:
            raise gl.vm.UserError("stake must be greater than zero")

        key = gl.message.sender_address
        position = market.positions.get(key)
        if position is None:
            # NOTE: TreeMap.compute_if_absent is broken in this SDK version
            # (it never invokes the "exists" callback when inserting), so the
            # insert is done explicitly and the value read back.
            market.positions[key] = _new_position()
            position = market.positions[key]
        if int(side) == SIDE_YES:
            position.yes = u256(int(position.yes) + value)
            market.pot_yes = u256(int(market.pot_yes) + value)
        else:
            position.no = u256(int(position.no) + value)
            market.pot_no = u256(int(market.pot_no) + value)
        self.total_staked = u256(int(self.total_staked) + value)

    # -- close and resolve -----------------------------------------------

    @gl.public.write
    def close_market(self, market_id: u64) -> None:
        """Stop accepting stakes.  Permissionless, once the close time has passed."""
        market = self._market(int(market_id))
        if int(market.status) != STATUS_OPEN:
            raise gl.vm.UserError("market is not open")
        if self._now() < int(market.close_time):
            raise gl.vm.UserError("market has not closed yet")
        market.status = u8(STATUS_CLOSED)

    @gl.public.write
    def resolve(self, market_id: u64) -> None:
        """Rule on the market.  Permissionless.

        The answer is decided by the validators fetching the page themselves;
        the caller cannot choose it.  After the resolution window the market
        resolves deterministically as UNDETERMINED, so funds can never be
        locked.
        """
        market = self._market(int(market_id))
        if int(market.status) == STATUS_OPEN:
            if self._now() < int(market.close_time):
                raise gl.vm.UserError("market has not closed yet")
            market.status = u8(STATUS_CLOSED)
        if int(market.status) != STATUS_CLOSED:
            raise gl.vm.UserError("market is not awaiting resolution")

        if self._now() >= int(market.close_time) + RESOLUTION_WINDOW:
            # Deterministic fallback: no fetch, no consensus needed, everybody
            # is refunded.  This is what guarantees funds cannot be locked.
            self._settle(
                market,
                OUTCOME_UNDETERMINED,
                STATUS_RESOLVED_UNDETERMINED,
                EMPTY_DIGEST,
            )
            return

        url = market.url
        kind = int(market.rule_kind)
        param = market.rule_param
        path = market.rule_path

        outcome, digest = self._rule_on_the_page(url, kind, param, path)

        if outcome == OUTCOME_UNDETERMINED:
            self._settle(
                market, outcome, STATUS_RESOLVED_UNDETERMINED, digest
            )
            return
        if int(market.pot_yes) == 0 or int(market.pot_no) == 0:
            # One-sided pool: the rule was decided, but there is nobody on the
            # other side, so the money goes back to the people who put it in.
            self._settle(market, outcome, STATUS_RESOLVED_REFUNDED, digest)
            return
        if outcome == OUTCOME_YES:
            self._settle(market, outcome, STATUS_RESOLVED_YES, digest)
        else:
            self._settle(market, outcome, STATUS_RESOLVED_NO, digest)

    def _rule_on_the_page(self, url: str, kind: int, param: str, path: str):
        """Run the non-deterministic block.

        The leader fetches the page; every validator fetches it again and must
        arrive at the same outcome *and* the same digest of the evidence bytes.
        """

        def leader():
            return _fetch_and_evaluate(url, kind, param, path)

        def validator(leader_result):
            if not isinstance(leader_result, gl.vm.Return):
                return False
            return _same_result(_fetch_and_evaluate(url, kind, param, path), leader_result.calldata)

        result = gl.vm.run_nondet_unsafe(leader, validator)
        return int(result[0]), bytes(result[1])

    def _settle(
        self, market: Market, outcome: int, status: int, digest: bytes
    ) -> None:
        market.rule_outcome = u8(outcome)
        market.status = u8(status)
        market.evidence_digest = digest
        if status in (STATUS_RESOLVED_UNDETERMINED, STATUS_RESOLVED_REFUNDED):
            market.payout_pot = u256(0)
        else:
            market.payout_pot = u256(int(market.pot_yes) + int(market.pot_no))

    # -- withdraw --------------------------------------------------------

    @gl.public.write
    def withdraw(self, market_id: u64) -> None:
        """Pull your winnings (or your refund).  Pays the caller, always."""
        market = self._market(int(market_id))
        status = int(market.status)
        if status not in (
            STATUS_RESOLVED_YES,
            STATUS_RESOLVED_NO,
            STATUS_RESOLVED_UNDETERMINED,
            STATUS_RESOLVED_REFUNDED,
        ):
            raise gl.vm.UserError("market is not resolved")
        position = market.positions.get(gl.message.sender_address)
        if position is None:
            raise gl.vm.UserError("nothing to withdraw")
        remaining_yes = int(position.yes) - int(position.settled_yes)
        remaining_no = int(position.no) - int(position.settled_no)
        if remaining_yes == 0 and remaining_no == 0:
            raise gl.vm.UserError("nothing to withdraw")

        amount_yes = self._entitlement(market, SIDE_YES, remaining_yes)
        amount_no = self._entitlement(market, SIDE_NO, remaining_no)
        amount = amount_yes + amount_no
        if amount == 0:
            # A losing side has nothing to collect.  Refusing (rather than
            # settling for zero) keeps the contract and the UI in agreement
            # about what "withdraw" means.
            #
            # This cannot strand a real winner: the cumulative allocation
            # gives a winner at least its own stake (P >= W), so a winner's
            # entitlement is never zero.
            raise gl.vm.UserError("nothing to withdraw")

        # Checks before effects: settle the position *before* emitting the
        # transfer, so a second call (or a re-entrant one) finds nothing.
        position.settled_yes = u256(int(position.yes))
        position.settled_no = u256(int(position.no))
        market.settled_yes_stake = u256(int(market.settled_yes_stake) + remaining_yes)
        market.settled_no_stake = u256(int(market.settled_no_stake) + remaining_no)

        if amount > 0:
            self.total_paid = u256(int(self.total_paid) + amount)
            gl.get_contract_at(gl.message.sender_address).emit_transfer(value=u256(amount))

    # -- views -----------------------------------------------------------

    @gl.public.view
    def get_market_count(self) -> u64:
        return u64(len(self.markets))

    @gl.public.view
    def get_market(self, market_id: u64) -> tuple:
        market = self._market(int(market_id))
        return (
            market_id,
            market.creator.as_hex,
            market.url,
            market.claim,
            int(market.rule_kind),
            market.rule_param,
            market.rule_path,
            int(market.close_time),
            int(market.status),
            int(market.rule_outcome),
            int(market.pot_yes),
            int(market.pot_no),
            int(market.payout_pot),
            market.evidence_digest,
        )

    @gl.public.view
    def get_status(self, market_id: u64) -> u8:
        return self._market(int(market_id)).status

    @gl.public.view
    def get_position(self, market_id: u64, account: str) -> tuple:
        market = self._market(int(market_id))
        try:
            key = Address(account)
        except Exception:
            return (u256(0), u256(0), u256(0), u256(0))
        position = market.positions.get(key)
        if position is None:
            return (u256(0), u256(0), u256(0), u256(0))
        return (
            position.yes,
            position.no,
            position.settled_yes,
            position.settled_no,
        )

    @gl.public.view
    def get_payout_preview(self, market_id: u64, account: str) -> u256:
        """What `withdraw` would pay the account right now."""
        market = self._market(int(market_id))
        try:
            key = Address(account)
        except Exception:
            return u256(0)
        position = market.positions.get(key)
        if position is None:
            return u256(0)
        remaining_yes = int(position.yes) - int(position.settled_yes)
        remaining_no = int(position.no) - int(position.settled_no)
        if remaining_yes == 0 and remaining_no == 0:
            return u256(0)
        amount = self._entitlement(
            market, SIDE_YES, remaining_yes
        ) + self._entitlement(market, SIDE_NO, remaining_no)
        return u256(amount)

    @gl.public.view
    def get_totals(self) -> tuple:
        return (self.total_staked, self.total_paid)

    @gl.public.view
    def get_now(self) -> u64:
        return u64(self._now())

    @gl.public.view
    def get_contract_balance(self) -> u256:
        return u256(int(self.balance))
