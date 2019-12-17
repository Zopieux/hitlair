import pytest

from hitler.game import Player, Role


@pytest.fixture
def example_players():
    players = [Player(p) for p in
               ["zopieux", "delroth", "halfr", "spider", "sophie"]]
    for p in players[:3]:
        p.role = Role.liberal
    players[3].role = Role.fascist
    players[4].role = Role.hitler
    return players


@pytest.fixture
def more_example_players():
    players = [Player(p) for p in ["robert", "amour"]]
    players[0].role = Role.liberal
    players[1].role = Role.fascist
    return players


@pytest.fixture
def state():
    from hitler import game
    return game.State()
