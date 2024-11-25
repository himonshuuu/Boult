""" 
MIT License

Copyright (c) 2024 Himangshu Saikia

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""




from discord.ext import commands
from wavelink.exceptions import WavelinkException

__all__ = [
    'BoultCheckFailure',
    'BoultWavelinkException',
    'NotSameVoice',
    'NoDJRole',
    'NotInVoice',
    'NotBotInVoice',
    'NoChannelProvided',
    'IncorrectChannelError'
]



class BoultCheckFailure(commands.CheckFailure):
    """
    Base exception for the check failures.
    """
    pass

class BoultWavelinkException(WavelinkException):
    """
    Base exception for the Wavelink exceptions.
    """
    pass

class NotSameVoice(BoultCheckFailure):
    """
    Error raised when someone tries to use a command without being in the same voice channel as the bot.
    """
    pass

class NoDJRole(BoultCheckFailure):
    """
    Error raised when someone tries to use a DJ command without the DJ role.
    """
    pass


class NotInVoice(BoultCheckFailure):
    """
    Error raised when someone tries do to something when they are not in the voice channel.
    """
    pass


class NotBotInVoice(BoultCheckFailure):
    """
    Error raised when the bot is not in the voice channel.
    """
    pass


class NoChannelProvided(BoultCheckFailure):
    """
    Error raised when no suitable voice channel was supplied.
    """

    pass


class IncorrectChannelError(BoultCheckFailure):
    """
    Error raised when commands are used outside of the players session channel.
    """


class NotInVoice(BoultCheckFailure):
    """
    Error raised when someone tries do to something when they are not in the voice channel.
    """

    pass


class BotNotInVoice(BoultCheckFailure):
    """
    Error raised when the bot is not in the voice channel.
    """
    pass

class NoResultFound(BoultWavelinkException):
    """
    Error raised when no track is found.
    """
    pass

class InvalidSearch(BoultWavelinkException):
    """
    Error raised when the search is invalid.
    """
    pass

class NoTracksFound(BoultWavelinkException):
    """
    Error raised when no tracks are found.
    """
    pass

