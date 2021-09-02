from discord import opus
from discord.opus import _OpusStruct, APPLICATION_AUDIO


class Encoder(opus.Encoder):
    """
    Temporal fix for Darwin devices:
    self.voice.play checks whether there is an encoder defined (in my device it's not)
    If the encoder is undefined it will run the Encoder() class to define it.
    The class __init__ method tries to define some variables using
    _lib.opus_encoder_ctl().
    This method stops the code when it's executed.
    The fix creates a custom Encoder() class inheriting from the original subclass,
    but this one doesn't call the _lib.opus_encoder_ctl() method
    """
    def __init__(self, application=APPLICATION_AUDIO):
        _OpusStruct.get_opus_version()
        self.application = application
        self._state = self._create_state()
        self.set_bitrate(128)