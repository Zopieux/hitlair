from typing import Type

import pytest

from hitlair import game
from hitlair.game import Stage, IllegalState, Player, InvalidAction, Policy


def has_one_event_of_type(events, cls: Type[game.Event]):
    return sum(1 for e in events if isinstance(e, cls))


def get_event_of_type(events, cls: Type[game.Event]):
    matching = [e for e in events if isinstance(e, cls)]
    assert len(matching) == 1
    return matching[0]


def test_cannot_play(state):
    state.add_player(Player("zopieux"))
    assert not state.can_game_start


def test_can_play(state, example_players):
    [state.add_player(p) for p in example_players]
    assert state.can_game_start


def test_game_starts(state, example_players):
    assert state.stage is Stage.lobby

    with pytest.raises(IllegalState):
        state.advance()

    [state.add_player(p) for p in example_players[:-1]]
    with pytest.raises(IllegalState):
        state.advance()

    state.add_player(example_players[-1])
    events, stage = state.advance()

    assert stage is Stage.nominate_chancellor
    assert game.GameStarts() in events
    for p in example_players:
        assert game.PlayerRoleChanges(p) in events
    assert has_one_event_of_type(events, game.PresidentChanges)


def test_chancellor_nomination_vote_fails(state: game.State, example_players):
    president, chancellor, *_ = example_players
    state._skip_lobby_for_testing(example_players, president)
    assert state.stage is Stage.nominate_chancellor

    with pytest.raises(InvalidAction):
        state.nominate_chancellor(president)

    state.nominate_chancellor(chancellor)
    events, stage = state.advance()

    assert (
        get_event_of_type(events, game.PresidentNominates).candidate_chancellor
        == chancellor
    )
    with pytest.raises(IllegalState):
        state.advance()

    # Vote failure
    state.record_vote(example_players[0], False)
    state.record_vote(example_players[1], False)
    state.record_vote(example_players[2], False)
    state.record_vote(example_players[3], True)
    state.record_vote(example_players[4], True)

    events, stage = state.advance()
    assert stage is Stage.nominate_chancellor
    assert game.NominateVoteFails(2, 3) in events
    assert game.ElectrionTrackerProgresses(1) in events
    assert game.PresidentChanges(president, example_players[1]) in events


def test_chancellor_nomination_vote_succeeds(state: game.State, example_players):
    president, chancellor, *_ = example_players
    state._skip_lobby_for_testing(example_players, president)
    assert state.stage is Stage.nominate_chancellor

    state.nominate_chancellor(chancellor)
    state.advance()

    # Vote success.
    state.record_vote(example_players[0], True)
    state.record_vote(example_players[1], True)
    state.record_vote(example_players[2], True)
    state.record_vote(example_players[3], False)
    state.record_vote(example_players[4], False)

    events, stage = state.advance()
    assert stage is Stage.legislate
    assert game.NominateVoteSucceeds(3, 2, chancellor) in events


def test_legislate_and_enact(state, example_players):
    president, chancellor, *_ = example_players
    state._skip_lobby_for_testing(example_players, president)
    state._skip_chancellor_election_for_testing(chancellor)
    assert state.stage is Stage.legislate

    state._set_next_policies_for_testing(
        [Policy.fascist, Policy.fascist, Policy.fascist]
    )
    with pytest.raises(InvalidAction):
        state.president_discards(Policy.liberal)

    state._set_next_policies_for_testing(
        [Policy.liberal, Policy.liberal, Policy.fascist]
    )
    state.president_discards(Policy.liberal)
    assert state.policy_deck[-2:] == [Policy.liberal, Policy.fascist]

    events, stage = state.advance()
    assert stage is Stage.enact
    assert game.PresidentLegislates(president) in events

    state._set_next_policies_for_testing([Policy.fascist, Policy.fascist])
    with pytest.raises(InvalidAction):
        state.chancellor_discards(Policy.liberal)

    state._set_next_policies_for_testing([Policy.fascist, Policy.liberal])
    state.chancellor_discards(Policy.fascist)
    assert state.policy_deck[-1:] == [Policy.liberal]

    events, stage = state.advance()
    assert stage is Stage.nominate_chancellor
    assert game.ChancellorEnacts(chancellor, Policy.liberal) in events
    assert game.PresidentChanges(president, example_players[1]) in events


def test_liberals_win_by_policies(state, example_players):
    president, chancellor, *_ = example_players
    state._skip_lobby_for_testing(example_players, president)
    state._skip_chancellor_election_for_testing(chancellor)
    state._set_policy_board_for_testing(4, 1)

    state._set_next_enacted_policy_for_testing(Policy.liberal)
    events, stage = state.advance()
    assert stage is Stage.lobby
    assert game.LiberalsWin() in events


def test_fascists_win_by_policies(state, example_players):
    president, chancellor, *_ = example_players
    state._skip_lobby_for_testing(example_players, president)
    state._skip_chancellor_election_for_testing(chancellor)
    state._set_policy_board_for_testing(1, 5)

    state._set_next_enacted_policy_for_testing(Policy.fascist)
    events, stage = state.advance()
    assert stage is Stage.lobby
    assert game.FascistsWin() in events


def test_fascists_cannot_win_by_hitler_chancellor_whithout_3_policies(
    state, example_players
):
    president, chancellor, *_, hitler = example_players
    state._skip_lobby_for_testing(example_players, president)
    state._skip_chancellor_election_for_testing(chancellor)
    # Requires at least 3 fascist policies.
    state._set_policy_board_for_testing(1, 2)

    state._force_elect_chancellor_for_testing(hitler)
    events, stage = state.advance()
    assert game.FascistsWin() not in events


def test_fascists_win_by_hitler_chancellor(state, example_players):
    president, chancellor, *_, hitler = example_players
    state._skip_lobby_for_testing(example_players, president)
    state._skip_chancellor_election_for_testing(chancellor)
    # Requires at least 3 fascist policies.
    state._set_policy_board_for_testing(1, 3)

    state._force_elect_chancellor_for_testing(hitler)
    events, stage = state.advance()
    assert game.FascistsWin() in events
    assert stage is Stage.lobby


def tests_chaos(state, example_players):
    president, chancellor, *_ = example_players
    state._skip_lobby_for_testing(example_players, president)
    state._skip_chancellor_election_for_testing(chancellor)

    # Next is chaos!
    state._set_election_tracker_for_testing(2)
    state._set_next_policies_for_testing([Policy.fascist])

    state._force_failed_election()
    events, stage = state.advance()
    assert game.ChaosHappens(Policy.fascist) in events
    assert stage is Stage.nominate_chancellor


def tests_chaos_snowball(state, example_players):
    president, chancellor, *_ = example_players
    state._skip_lobby_for_testing(example_players, president)
    state._skip_chancellor_election_for_testing(chancellor)
    # Next is chaos, and it snowballs into liberal win (5 liberals policies).
    state._set_election_tracker_for_testing(2)
    state._set_policy_board_for_testing(4, 1)
    state._set_next_policies_for_testing([Policy.liberal])

    state._force_failed_election()
    events, stage = state.advance()
    assert game.ChaosHappens(Policy.liberal) in events
    assert game.LiberalsWin() in events
    assert stage is Stage.lobby


def test_executive_action_peek(state, example_players):
    president, chancellor, *_ = example_players
    state._skip_lobby_for_testing(example_players, president)
    state._skip_chancellor_election_for_testing(chancellor)
    # Next fascist policy is peek.
    state._set_policy_board_for_testing(1, 2)
    state._set_next_enacted_policy_for_testing(Policy.fascist)

    events, stage = state.advance()
    assert game.PresidentShallPeek(president) in events
    assert stage is Stage.action_peek

    state.president_peeks()
    events, stage = state.advance()
    assert game.PresidentPeeks(president) in events
    assert stage is Stage.nominate_chancellor


def test_executive_action_kill(state, example_players):
    president, chancellor, *_ = example_players
    state._skip_lobby_for_testing(example_players, president)
    state._skip_chancellor_election_for_testing(chancellor)
    # Next fascist policy is kill.
    state._set_policy_board_for_testing(1, 3)
    state._set_next_enacted_policy_for_testing(Policy.fascist)

    events, stage = state.advance()
    assert game.PresidentShallKill(president) in events
    assert stage is Stage.action_kill

    with pytest.raises(InvalidAction):
        state.president_kills(president)

    state.president_kills(chancellor)
    events, stage = state.advance()
    assert game.PresidentKills(president, chancellor) in events
    assert stage is Stage.nominate_chancellor


def test_executive_action_investigate(state, example_players, more_example_players):
    president, chancellor, *_ = example_players
    state._skip_lobby_for_testing(example_players + more_example_players, president)
    state._skip_chancellor_election_for_testing(chancellor)
    # Next fascist policy is investigate.
    state._set_policy_board_for_testing(1, 1)
    state._set_next_enacted_policy_for_testing(Policy.fascist)

    events, stage = state.advance()
    assert game.PresidentShallInvestigate(president) in events
    assert stage is Stage.action_investigate

    with pytest.raises(InvalidAction):
        state.president_investigates(president)

    state.president_investigates(chancellor)
    events, stage = state.advance()
    assert game.PresidentInvestigates(president, chancellor) in events
    assert stage is Stage.nominate_chancellor


def test_executive_action_special_election(
    state, example_players, more_example_players
):
    president, chancellor, *_ = example_players
    state._skip_lobby_for_testing(example_players + more_example_players, president)
    state._skip_chancellor_election_for_testing(chancellor)
    # Next fascist policy is special election.
    state._set_policy_board_for_testing(1, 2)
    state._set_next_enacted_policy_for_testing(Policy.fascist)

    events, stage = state.advance()
    assert game.PresidentShallSpeciallyElect(president) in events
    assert stage is Stage.action_special_election

    with pytest.raises(InvalidAction):
        state.president_chooses_next_president(president)

    state.president_chooses_next_president(chancellor)
    events, stage = state.advance()
    assert game.PresidentChanges(president, chancellor) in events
    assert stage is Stage.nominate_chancellor
    # Chancellor is indeed next president (by special election).
    assert state.president == chancellor

    # Force an election to get the next president.
    state._force_failed_election()
    state.advance()
    # Chancellor is president again, this time thanks to the natural player
    # order.
    assert state.president == chancellor
