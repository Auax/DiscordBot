import discord
from discord.ext import commands
from misc import auth

"""This is a Discord bot created by Ibai Farina (2006): https://github.com/auax
"""


def get_prefix(bot_, message):
    """A callable Prefix for our bot. This could be edited to allow per server prefixes."""

    # Notice how you can use spaces in prefixes. Try to keep them simple though.
    prefixes = ['/', "!"]

    # Check to see if we are outside of a guild. e.g DM's etc.
    if not message.guild:
        # Only allow ? to be used in DMs
        return '?'

    # If we are in a guild, we allow for the user to mention us or use any of the prefixes in our list.
    return commands.when_mentioned_or(*prefixes)(bot_, message)


# Below cogs represents our folder our cogs are in. Following is the file name. So 'example.py' in cogs,
# would be cogs.example Think of it like a dot path import
initial_extensions = ['modules.voice']

# Authentication token
token = auth.authenticate("config/authentication.json", "discord").get("token")

bot = commands.Bot(command_prefix=get_prefix, description="Auax Discord bot. Created by Ibai Farina (2006) "
                                                          "github.com/auax")


@bot.event
async def on_ready():
    """Init bot function"""
    print(f'Logged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')

    # Changes our bots Playing Status. type=1(streaming) for a standard game you could remove type and url.
    await bot.change_presence(activity=discord.Game(name='help', type=1, url='https://twitch.tv/astok'))
    print(f'Successfully logged in and booted...!')


if __name__ == "__main__":
    for extension in initial_extensions:
        bot.load_extension(extension)

    bot.run(token, bot=True, reconnect=True)
