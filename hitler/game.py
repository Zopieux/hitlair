import enum
import itertools
import random
from enum import auto
from typing import List, Optional, Dict, Iterator, NamedTuple, Tuple, \
    Iterable, Generator, Callable

# Keys are also the supported numbers of players.
PLAYER_COUNT_TO_LIBERAL_COUNT = {
    5: 3,
    6: 4,
    7: 4,
    8: 5,
    9: 5,
    10: 6,
}

FASCIST_POLICY_COUNT = 11
LIBERAL_POLICY_COUNT = 6
PRESIDENT_HAND = 3
CHANCELLOR_HAND = PRESIDENT_HAND - 1


class Error(Exception):
    pass


class InvalidAction(Error):
    pass


class IllegalState(Error):
    pass


def fascist_count(player_count: int) -> int:
    liberal_count = PLAYER_COUNT_TO_LIBERAL_COUNT[player_count]
    hitler = 1
    return player_count - liberal_count - hitler


class Stage(enum.Enum):
    # Players can join and game can start.
    lobby = auto()
    # President chooses (nominates) chancellor.
    nominate_chancellor = auto()
    # Players accept or deny the president's choice of chancellor.
    chancellor_election = auto()
    # President discards 1 policy and passes 2 remaining policies to chancellor.
    legislate = auto()
    # Chancellor discards 1 policy and enacts the remaining policy.
    enact = auto()
    # President accepts or deny Chancellor's veto call.
    confirm_veto = auto()
    # President executive actions (fascist policy).
    action_peek = auto()
    action_investigate = auto()
    action_kill = auto()
    action_special_election = auto()


class Role(enum.Enum):
    liberal = auto()
    fascist = auto()
    hitler = auto()


class Player:
    name: str
    role: Optional[Role] = None

    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other):
        return isinstance(other, Player) and (self.name,) == (other.name,)

    def __hash__(self):
        return hash((self.name,))

    def __repr__(self):
        return f"<Player {self.name} ({self.role})>"


class Policy(enum.Enum):
    liberal = auto()
    fascist = auto()


class ExecutiveAction(enum.Enum):
    peek = auto()
    kill = auto()
    investigate = auto()
    special_election = auto()

    @classmethod
    def get(cls, player_count: int, fascist_policy_count: int):
        pc_5_6 = {
            3: cls.peek,
            4: cls.kill,
            5: cls.kill,
        }
        pc_7_8 = {
            2: cls.investigate,
            3: cls.special_election,
            4: cls.kill,
            5: cls.kill,
        }
        pc_9_10 = {
            1: cls.investigate,
            2: cls.investigate,
            3: cls.special_election,
            4: cls.kill,
            5: cls.kill,
        }
        return ({5: pc_5_6, 6: pc_5_6,
                 7: pc_7_8, 8: pc_7_8,
                 9: pc_9_10, 10: pc_9_10}[player_count]
                .get(fascist_policy_count))

    @classmethod
    def veto_available(cls, fascist_policy_count: int):
        return fascist_policy_count >= 5


class Event:
    pass


class GameStarts(Event, NamedTuple):
    pass


class PlayerJoins(Event, NamedTuple):
    player: Player


class PlayerParts(Event, NamedTuple):
    player: Player


class PlayerQuits(Event, NamedTuple):
    player: Player


class PlayerRoleChanges(Event, NamedTuple):
    player: Player


class PlayerReplaces(Event, NamedTuple):
    parting_player: Player
    new_player: Player


class PresidentChanges(Event, NamedTuple):
    former_president: Optional[Player]
    new_president: Player


class PresidentNominates(Event, NamedTuple):
    president: Player
    candidate_chancellor: Player


class NominateVoteSucceeds(Event, NamedTuple):
    yes_count: int
    no_count: int
    new_chancellor: Player


class NominateVoteFails(Event, NamedTuple):
    yes_count: int
    no_count: int


class ElectrionTrackerProgresses(Event, NamedTuple):
    vote_failure_count: int


class ChaosHappens(Event, NamedTuple):
    policy: Policy


class PresidentLegislates(Event, NamedTuple):
    president: Player


class ChancellorEnacts(Event, NamedTuple):
    chancellor: Player
    policy: Policy


class ChancellorVetoes(Event, NamedTuple):
    president: Player
    chancellor: Player


class PresidentAcceptsVeto(Event, NamedTuple):
    president: Player
    chancellor: Player


class PresidentDeniesVeto(Event, NamedTuple):
    president: Player
    chancellor: Player


class PresidentPeeks(Event, NamedTuple):
    president: Player


class PresidentInvestigates(Event, NamedTuple):
    president: Player
    investigated: Player


class PresidentKills(Event, NamedTuple):
    president: Player
    killed: Player


class PresidentShallPeek(Event, NamedTuple):
    president: Player


class PresidentShallInvestigate(Event, NamedTuple):
    president: Player


class PresidentShallKill(Event, NamedTuple):
    president: Player


class PresidentShallSpeciallyElect(Event, NamedTuple):
    president: Player


class HitlerIsElectedChancellor(Event, NamedTuple):
    president: Player
    hitler_and_chancellor: Player


class HitlerIsKilled(Event, NamedTuple):
    president: Player
    killed_hitler: Player


class LiberalsWin(Event, NamedTuple):
    pass


class FascistsWin(Event, NamedTuple):
    pass


class StageChanges(Event, NamedTuple):
    stage: Stage


class State:
    """
    Refactor idea that should make this class slightly better:
    instead of having so much global state even though many of it is temporary
    state for particular actions, attach a container to each Stage with the
    relevant temporary state. Then in exit_foo(), validate foo temporary state
    and apply it to global state before advancing to next stage.

    Things that should remain global: players, dead_players, policy_deck, etc.
    Things that can go into temporary context-specific states: votes, veto, etc.
    """
    stage: Stage
    players: List[Player]
    player_cycle: Iterator[Player]
    dead_players: List[Player]
    policy_deck: List[Policy]
    discard_pile: List[Policy]
    president: Optional[Player]
    former_president: Optional[Player]
    chancellor: Optional[Player]
    former_chancellor: Optional[Player]
    votes: Dict[Player, bool]
    investigated_players: List[Player]
    failed_votes: int
    liberal_policies: int
    fascist_policies: int
    veto_requested: bool
    veto_accepted: bool
    killed_player: Optional[Player]
    special_election_next_president: Optional[Player]

    def __init__(self):
        self.reset()

    def reset(self):
        self.stage = Stage.lobby
        self.players = []
        self.player_cycle = []
        self.dead_players = []
        self.policy_deck = []
        self.discard_pile = []
        self.president = None
        self.former_president = None
        self.chancellor = None
        self.former_chancellor = None
        self.votes = {}
        self.investigated_players = []
        self.failed_votes = 0
        self.liberal_policies = 0
        self.fascist_policies = 0
        self.veto_requested = False
        self.veto_accepted = False
        self.killed_player = None
        self.special_election_next_president = None

    # Generic state advance method.

    def advance(self, current_stage=None) -> Tuple[Iterable[Event], Stage]:
        if current_stage is not None and self.stage is not current_stage:
            raise IllegalState()

        method_name = f'exit_{self.stage.name}'
        method: Callable[[], Generator[Event]] = getattr(self, method_name)
        events = list(method())

        *events, stage_event = events
        assert isinstance(stage_event, StageChanges)
        self.stage = stage_event.stage
        return events, self.stage

    # Stage: lobby

    @property
    def can_game_start(self) -> bool:
        return self.player_count in PLAYER_COUNT_TO_LIBERAL_COUNT

    def is_registered_player(self, player: Player) -> bool:
        return player in self.players

    def add_player(self, player: Player):
        self._ensure_stage(Stage.lobby)

        if self.player_count == max(PLAYER_COUNT_TO_LIBERAL_COUNT.keys()):
            raise InvalidAction()

        if player in self.players:
            raise InvalidAction()

        self.players.append(player)

    def remove_player(self, player: Player):
        self._ensure_stage(Stage.lobby)

        if player not in self.players:
            raise InvalidAction()

        self.players.remove(player)

    # Stage: nominate_chancellor

    def exit_lobby(self):
        self._ensure_stage(Stage.lobby)

        try:
            liberal_count = PLAYER_COUNT_TO_LIBERAL_COUNT[self.player_count]
        except KeyError:
            raise IllegalState() from None

        # First shuffle to distribute roles.
        random.shuffle(self.players)
        hitler, *not_hitler = self.players
        hitler.role = Role.hitler
        liberals, fascists = (not_hitler[:liberal_count],
                              not_hitler[liberal_count:])
        for liberal in liberals:
            liberal.role = Role.liberal
        for fascist in fascists:
            fascist.role = Role.fascist

        # Second shuffle for play order.
        random.shuffle(self.players)
        # President is picked at random.
        self.president = random.choice(self.players)
        self._build_player_cycle()

        self._init_policy_deck()

        yield GameStarts()
        yield from [PlayerRoleChanges(player) for player in self.players]
        yield PresidentChanges(None, self.president)
        yield StageChanges(Stage.nominate_chancellor)

    def nominate_chancellor(self, chancellor: Player):
        self._ensure_stage(Stage.nominate_chancellor)

        # Term limit: cannot nominate former chancellor or former president.
        if (chancellor == self.former_chancellor
                or chancellor == self.former_president
                or chancellor == self.president):
            raise InvalidAction()

        self.chancellor = chancellor

    # Stage: chancellor_election

    def exit_nominate_chancellor(self):
        self._ensure_stage(Stage.nominate_chancellor)

        if self.chancellor is None:
            raise IllegalState()

        yield PresidentNominates(self.president, self.chancellor)
        yield StageChanges(Stage.chancellor_election)

    @property
    def is_election_complete(self) -> bool:
        """Returns True if the election is complete."""
        return len(self.votes) == self.player_count

    def record_vote(self, player: Player, yes: bool):
        self._ensure_stage(Stage.chancellor_election)

        self.votes[player] = yes

    def exit_chancellor_election(self):
        self._ensure_stage(Stage.chancellor_election)

        if not self.is_election_complete:
            raise IllegalState()

        yes_count = sum(1 for vote in self.votes.values() if vote)
        no_count = self.player_count - yes_count
        # A tie is a failed election, hence strictly greater than.
        vote_succeeds = yes_count > no_count

        self.votes = {}

        if not vote_succeeds:
            yield NominateVoteFails(yes_count, no_count)

            yield from self._advance_election_tracker()
            # Chaos after too many failed votes.
            if self.failed_votes == 3:
                yield from self._chaos()
                return

            # Otherwise go to next president as usual.
            yield from self._next_president()
            return

        # Successful election resets the election tracker.
        self.failed_votes = 0
        self._ensure_valid_policy_deck()
        yield NominateVoteSucceeds(yes_count, no_count, self.chancellor)

        # Fascists win by electing Hitler chancellor after 3 enacted policies.
        if self.fascist_policies >= 3 and self.chancellor.role is Role.hitler:
            yield HitlerIsElectedChancellor(self.president, self.chancellor)
            yield FascistsWin()
            yield StageChanges(Stage.lobby)
            return

        # Otherwise normal turn.
        yield StageChanges(Stage.legislate)

    # Stage: legislate

    @property
    def president_hand(self) -> List[Policy]:
        self._ensure_stage(Stage.legislate)
        return self.policy_deck[-PRESIDENT_HAND:]

    @property
    def deck_without_president_hand(self) -> List[Policy]:
        self._ensure_stage(Stage.legislate)
        return self.policy_deck[:-PRESIDENT_HAND]

    def president_discards(self, discarded_policy: Policy):
        self._ensure_stage(Stage.legislate)

        hand = self.president_hand
        if discarded_policy not in hand:
            raise InvalidAction()

        hand.remove(discarded_policy)
        self.discard_pile.append(discarded_policy)
        # For convenience, we store the hand to the top of the deck.
        self.policy_deck = self.deck_without_president_hand + hand

    def exit_legislate(self):
        self._ensure_stage(Stage.legislate)
        yield PresidentLegislates(self.president)
        yield StageChanges(Stage.enact)

    # Stage: enact

    @property
    def chancellor_hand(self) -> List[Policy]:
        self._ensure_stage(Stage.enact)
        return self.policy_deck[-CHANCELLOR_HAND:]

    @property
    def deck_without_chancellor_hand(self) -> List[Policy]:
        self._ensure_stage(Stage.enact)
        return self.policy_deck[:-CHANCELLOR_HAND]

    def chancellor_discards(self, discarded_policy: Policy):
        self._ensure_stage(Stage.enact)

        if self.veto_requested:
            raise InvalidAction()

        hand = self.chancellor_hand
        if discarded_policy not in hand:
            raise InvalidAction()

        hand.remove(discarded_policy)
        assert len(hand) == 1
        self.discard_pile.append(discarded_policy)
        # For convenience, we put the enacted policy at the top of the deck.
        enacted_policy = hand[0]
        self.policy_deck = self.deck_without_chancellor_hand + [enacted_policy]

    def chancellor_vetoes(self):
        self._ensure_stage(Stage.legislate)

        # TODO: no check that c_vetoes() is never called after c_discard(),
        # trusting caller.
        if self.veto_requested:
            raise InvalidAction()

        if not ExecutiveAction.veto_available(self.fascist_policies):
            raise InvalidAction()

        self.veto_requested = True

    def exit_enact(self):
        self._ensure_stage(Stage.enact)

        if self.veto_requested:
            yield ChancellorVetoes(self.president, self.chancellor)
            yield StageChanges(Stage.confirm_veto)
            return

        self.veto_requested = False

        enacted_policy = self.policy_deck.pop(-1)
        yield ChancellorEnacts(self.chancellor, enacted_policy)
        yield from self._enact_outcome(enacted_policy)

    # Stage: confirm_veto

    def president_answers_to_veto(self, accept: bool):
        self._ensure_stage(Stage.confirm_veto)
        self.veto_accepted = accept

    def exit_confirm_veto(self):
        self._ensure_stage(Stage.confirm_veto)

        if not self.veto_accepted:
            yield PresidentDeniesVeto(self.president, self.chancellor)
            # Back to enact.
            yield StageChanges(Stage.enact)
            return

        yield PresidentAcceptsVeto(self.president, self.chancellor)

        yield from self._advance_election_tracker()
        if self.failed_votes == 3:
            # Chaos after too many failed votes.
            yield from self._chaos()
            return

        yield from self._next_president()

    # Stage: action_peek

    def president_peeks(self) -> List[Policy]:
        self._ensure_stage(Stage.action_peek)
        return self.policy_deck[-PRESIDENT_HAND:]

    def exit_action_peek(self):
        self._ensure_stage(Stage.action_peek)

        # TODO: no check that peek was in fact done, trusting caller.
        yield PresidentPeeks(self.president)
        yield from self._next_president()

    # Stage: action_investigate

    def president_investigates(self, investigated_player: Player) -> Role:
        # Nothing in the rules prevents from investigating dead players.
        if investigated_player not in self.players + self.dead_players:
            raise InvalidAction()

        if investigated_player == self.president:
            raise InvalidAction()

        self.investigated_players.append(investigated_player)
        return investigated_player.role

    def exit_action_investigate(self):
        self._ensure_stage(Stage.action_investigate)

        # Uses the fact that the last player is the one investigated.
        # Convenient but I don't like it.
        # TODO: no check that someone was in fact investigated, trusting caller.
        yield PresidentInvestigates(self.president,
                                    self.investigated_players[-1])
        yield from self._next_president()

    # Stage: action_kill

    def president_kills(self, killed_player: Player):
        self._ensure_stage(Stage.action_kill)

        # TODO: no check for multiple kills, trusting caller.
        if killed_player not in self.players:
            raise InvalidAction()

        if killed_player == self.president:
            raise InvalidAction()

        self.killed_player = killed_player

    def exit_action_kill(self):
        self._ensure_stage(Stage.action_kill)

        if not self.killed_player:
            raise IllegalState()

        self.dead_players.append(self.killed_player)
        self.players.remove(self.killed_player)
        self._build_player_cycle()

        yield PresidentKills(self.president, self.killed_player)
        yield from self._next_president()

    # Stage: action_special_election

    def president_chooses_next_president(self, next_president: Player):
        if next_president == self.president:
            raise InvalidAction()

        self.special_election_next_president = next_president

    def exit_action_special_election(self):
        self._ensure_stage(Stage.action_special_election)
        next_president = self.special_election_next_president
        self.special_election_next_president = None

        # We purposefully don't advance president.
        yield from self._next_president(specially_elected=next_president)

    # Utility functions.

    @property
    def player_count(self):
        """Count of alive players."""
        return len(self.players)

    @property
    def total_player_count(self):
        """Count of all (alive and dead) players."""
        return len(self.players) + len(self.dead_players)

    def _ensure_valid_policy_deck(self):
        """
        If there are less than POLICY_DRAW_COUNT policies in the deck, merge it
        with discard pile and shuffle. Otherwise, no op.
        """
        if len(self.policy_deck) < PRESIDENT_HAND:
            self.policy_deck.extend(self.discard_pile)
            self.discard_pile.clear()
            random.shuffle(self.policy_deck)

    def _ensure_stage(self, stage):
        if self.stage != stage:
            raise IllegalState(f"This can only be called during stage {stage}.")

    def _build_player_cycle(self):
        self.player_cycle = itertools.cycle(self.players)
        while True:
            if next(self.player_cycle) == self.president:
                break

    # Reusable state progress functions.

    def _advance_election_tracker(self):
        self.failed_votes += 1
        yield ElectrionTrackerProgresses(self.failed_votes)

    def _next_president(self, specially_elected: Optional[Player] = None):
        self.former_chancellor = self.chancellor
        self.chancellor = None
        self.former_president = self.president
        if specially_elected is not None:
            self.president = specially_elected
        else:
            self.president = next(self.player_cycle)
        yield PresidentChanges(self.former_president, self.president)
        yield StageChanges(Stage.nominate_chancellor)

    def _chaos(self):
        # Chaos resets the election tracker (obviously).
        self.failed_votes = 0

        self._ensure_valid_policy_deck()
        enacted_policy = self.policy_deck.pop(-1)
        self.discard_pile.append(enacted_policy)

        yield ChaosHappens(enacted_policy)
        yield from self._enact_outcome(enacted_policy)

    def _enact_outcome(self, enacted_policy: Policy):
        if enacted_policy is Policy.liberal:
            self.liberal_policies += 1
            if self.liberal_policies == 5:
                yield LiberalsWin()
                yield StageChanges(Stage.lobby)
                return

        else:
            self.fascist_policies += 1
            if self.fascist_policies == 6:
                yield FascistsWin()
                yield StageChanges(Stage.lobby)
                return

            executive_action = ExecutiveAction.get(self.total_player_count,
                                                   self.fascist_policies)
            if executive_action is ExecutiveAction.peek:
                yield PresidentShallPeek(self.president)
                yield StageChanges(Stage.action_peek)
                return
            elif executive_action is ExecutiveAction.investigate:
                yield PresidentShallInvestigate(self.president)
                yield StageChanges(Stage.action_investigate)
                return
            elif executive_action is ExecutiveAction.kill:
                yield PresidentShallKill(self.president)
                yield StageChanges(Stage.action_kill)
                return
            elif executive_action is ExecutiveAction.special_election:
                yield PresidentShallSpeciallyElect(self.president)
                yield StageChanges(Stage.action_special_election)
                return
            elif executive_action is None:
                pass
            else:
                raise ValueError()

        # No special event, proceed to next president.
        yield from self._next_president()

    def _init_policy_deck(self):
        self.policy_deck = list(itertools.chain(
            (Policy.liberal for _ in range(LIBERAL_POLICY_COUNT)),
            (Policy.fascist for _ in range(FASCIST_POLICY_COUNT))))
        random.shuffle(self.policy_deck)

    # Test helpers, should not be used outside of tests.

    def _skip_lobby_for_testing(self, players: List[Player], president: Player):
        self.players = players[:]
        self.president = president
        self._build_player_cycle()
        self._init_policy_deck()
        self.stage = Stage.nominate_chancellor

    def _skip_chancellor_election_for_testing(self, chancellor: Player):
        self.former_chancellor = self.chancellor
        self.chancellor = chancellor
        self.stage = Stage.legislate

    def _force_elect_chancellor_for_testing(self, chancellor: Player):
        self.stage = Stage.nominate_chancellor
        self.nominate_chancellor(chancellor)
        self.advance()
        for p in self.players:
            self.record_vote(p, True)

    def _force_failed_election(self):
        self.stage = Stage.nominate_chancellor
        # Random player.
        banned = {self.former_chancellor, self.chancellor,
                  self.former_president, self.president}
        self.nominate_chancellor(next((p for p in self.players
                                       if p not in banned)))
        self.advance()
        for p in self.players:
            self.record_vote(p, False)

    def _set_next_policies_for_testing(self, next_policies: List[Policy]):
        for policy in next_policies:
            self.policy_deck.remove(policy)

        self.policy_deck.extend(next_policies)

    def _set_policy_board_for_testing(self, liberal_policies: int,
                                      fascist_policies: int):
        self.liberal_policies = liberal_policies
        self.fascist_policies = fascist_policies

    def _set_election_tracker_for_testing(self, failed_votes: int):
        assert failed_votes < 3
        self.failed_votes = failed_votes

    def _set_next_enacted_policy_for_testing(self, enacted_policy: Policy):
        # Put enacted policy at the top (convention).
        self.policy_deck.remove(enacted_policy)
        self.policy_deck.append(enacted_policy)
        self.stage = Stage.enact
