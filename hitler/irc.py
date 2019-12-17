import asyncio
import enum
import functools
import os

import irc3
from irc3.plugins.command import command

from hitler import game
from hitler.game import Player
from hitler.irc_util import encode_modes

SELF_MODULE = 'hitler.irc'
CHANNEL = '##dieses-fn'


def ignore_wrong_channel(f):
    @functools.wraps(f)
    def wrapped(self, mask, target, *args, **kwargs):
        print("omg", self, mask, target)
        if target != CHANNEL:
            return
        return f(self, mask, target, *args, **kwargs)

    return wrapped


class State(enum.Enum):
    pending_setup = enum.auto()
    ready = enum.auto()


@irc3.plugin
class SecretHitlerPlugin:
    def __init__(self, bot):
        self.bot: irc3.IrcBot = bot
        self.state = State.pending_setup
        self.paused = False
        self.game = game.State()

    requires = [
        'irc3.plugins.core',
        'irc3.plugins.userlist',
        'irc3.plugins.command',
    ]

    @classmethod
    def reload(cls, old):
        return cls(old.bot)

    def after_reload(self):
        # asyncio.create_task(self.ensure_setup())
        pass

    def send_private(self, target, message: str):
        self.bot.privmsg(target, message)

    def send(self, message: str):
        self.send_private(CHANNEL, message)

    @property
    def users(self):
        return self.bot.channels[CHANNEL]

    def mode(self, *modes):
        for encoded in encode_modes(CHANNEL, *modes):
            print(encoded)
            self.bot.mode(CHANNEL, *encoded)

    @irc3.event(irc3.rfc.JOIN)
    def on_join(self, mask, channel, **kw):
        if mask.nick == self.bot.nick:
            asyncio.create_task(self.ensure_setup())

    @irc3.event(irc3.rfc.PART)
    def on_part(self, mask, channel, **kw):
        # TODO: handle parts better with eg. finding a replacement with timeout.
        if self.game.stage == game.Stage.lobby:
            return
        # Abort!
        self.game.reset()
        self.send("DAMIT l'autre con qui part en plein milieu")
        self.send("La partie est finie déso.")
        self.setup_lobby()
        self.pause(3, self.unpause)

    @irc3.event(irc3.rfc.QUIT)
    def on_quit(self, mask, **kw):
        self.on_part(mask, CHANNEL)

    @command
    def join(self, mask, target, args):
        """Join the next game.

            %%join
        """
        if self.paused:
            return
        nick = mask.nick
        try:
            self.game.add_player(Player(nick))
            self.mode(('+v', nick))
            self.send(f"{nick}: HEIL DAS IST GUT")
        except game.Error:
            self.send(f"{nick}: ASH DAS IST KEINE POßIBL")

    @command
    def part(self, mask, target, args):
        """Flee from the next game.

            %%part
        """
        if self.paused:
            return
        nick = mask.nick
        try:
            self.game.remove_player(Player(nick))
            self.mode(('-v', nick))
            self.send(f"{nick}: NEIN :'(")
        except game.Error:
            self.send(f"{nick}: ASH DAS IST KEINE POßIBL")

    @command
    def start(self, mask, target, args):
        """Start a game.

            %%start
        """
        if self.paused:
            return
        nick = mask.nick
        try:
            events, stage = self.game.advance(game.Stage.lobby)
            for event in events:
                if isinstance(event, game.GameStarts):
                    self.send("Et c'est parti pour une game de folie !")
                if isinstance(event, game.PlayerRoleChanges):
                    role = {
                        game.Role.liberal: "un libéral",
                        game.Role.fascist: "un fascho",
                        game.Role.hitler: "un fascho, et surtou tu es LITTÉRALEMENT HITLER",
                    }[event.player.role]
                    self.send_private(event.player.name, f"FYI tu es {role}")
                if isinstance(event, game.PresidentChanges):
                    self.send(f"Le président a été choisi au hasard, c'est {event.new_president.name} !")
            if stage is game.Stage.nominate_chancellor:
                self.send(f"Le président ({event.new_president.name}) doit choisir un chancelier. Annonces votre choix avec !chancelor <joueur>")
            else:
                raise game.Error("wtf")
        except game.Error as e:
            self.send(f"{nick}: ENSHULDIGONG ES GIBT EIN PRÖBLEM: {type(e)} {e}")

    @command
    def chancellor(self, mask, target, args):
        """Choose chancellor.

            %%chancellor <player>
        """
        if self.paused:
            return
        nick = mask.nick
        try:
            self.game.nominate_chancellor(Player(args["<player>"]))
            events, stage = self.game.advance()
            for event in events:
                if isinstance(event, game.PresidentNominates):
                    self.send(f"Le choix du président se porte sur {event.candidate_chancellor.name} comme chancelier.")
                else:
                    raise game.Error("wat")
            if stage is game.Stage.chancellor_election:
                self.send(f"Approuvez-vous ce choix ? Votez avec /query {self.bot.nick} !oui / !non.")
            else:
                raise game.Error("wtf")
        except game.Error as e:
            self.send(f"{nick}: ENSHULDIGONG ES GIBT EIN PRÖBLEM: {type(e)} {e}")

    @command
    def yes(self, mask, target, args):
        """Choose chancellor.

            %%yes
        """
        if self.paused:
            return
        nick = mask.nick
        try:
            self.game.record_vote(Player(nick), True)
            self.send_private(nick, "Je note ce OUI.")
        except game.Error as e:
            self.send(f"{nick}: ENSHULDIGONG ES GIBT EIN PRÖBLEM: {type(e)} {e}")

    @command
    def no(self, mask, target, args):
        """Choose chancellor.

            %%no
        """
        if self.paused:
            return
        nick = mask.nick
        try:
            self.game.record_vote(Player(nick), False)
            self.send_private(nick, "Je note ce NOPE.")
        except game.Error as e:
            self.send(f"{nick}: ENSHULDIGONG ES GIBT EIN PRÖBLEM: {type(e)} {e}")

    @command
    def x(self, mask, target, args):
        """Impersonate someone speaking in public.

            %%x <data>...
        """
        data = ' '.join(args['<data>'])
        self.send(repr(eval(data, {'self': self, 'game': game, 'g': self.game})))

    @command
    def reloadpls(self, mask, target, args):
        """Reload the bot.

            %%reloadpls
        """
        self.bot.reload(SELF_MODULE)

    def setup_lobby(self):
        self.mode('-m', *(('-v', m) for m in self.users.modes['+']))
        self.state = State.ready
        self.send("MY BODY IS READY")

    def unpause(self):
        self.paused = False

    def pause(self, delay: float, callback):
        self.paused = True
        asyncio.get_event_loop().call_later(delay, callback)

    async def ensure_setup(self):
        self.bot.privmsg(CHANNEL, "WAIT FOR IT…")
        while True:
            await asyncio.sleep(1)
            if self.bot.nick in self.users.modes['@']:
                self.setup_lobby()
                break


def main():
    password = os.getenv('BOTPSWD')
    config = dict(
        nick='hitlair', autojoins=[CHANNEL],
        host='chat.freenode.net', port=6697, ssl=True,
        password=f'hitlair:{password}',
        includes=[
            'irc3.plugins.core',
            'irc3.plugins.command',
            SELF_MODULE,
        ]
    )
    bot = irc3.IrcBot.from_config(config)
    bot.run(forever=True)


if __name__ == '__main__':
    main()
