import discord
from typing import List, Dict


def embed_msg(title: str = "",
              description: str = "",
              footer: str = None,
              field_values: List[Dict[str, str]] = None,
              inline: bool = False,
              thumbnail: str = None,
              color: int = 0x005BE8) -> discord.embeds.Embed:
    """
    Create an embed object
    :param title: ...
    :param description: ...
    :param footer: the footer of the embed
    :param field_values: The values for the fields. A list containing dicts with "name" and "value" keys.
    :param inline: Whether the field should be displayed inline.
    :param thumbnail: the img thumbnail url
    :param color: The color of the embed
    :return: discord.embeds.Embed
    """
    embed = discord.Embed(title=title, description=description, color=color)

    if footer:
        embed.set_footer(text=footer)

    if field_values:
        for field in range(len(field_values)):
            embed.add_field(**field_values[field], inline=inline)

    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    return embed


def video_embed(cls) -> discord.embeds.Embed:
    """
    Creates a video embed message with the misc.create_embed function
    :param cls:
    :return: discord.embeds.Embed
    """
    embed = embed_msg(
        title="Now playing",
        description=f"```css\n{cls.source.title}\n```",
        field_values=[
            {"name": "Duration", "value": cls.source.duration},
            {"name": "Requested by", "value": cls.requester.mention},
            {"name": "URL", "value": f"[YouTube]({cls.source.url})"}
        ],
        thumbnail=cls.source.thumbnail,
        inline=True
    )

    return embed
