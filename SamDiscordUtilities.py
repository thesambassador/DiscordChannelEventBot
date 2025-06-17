import re
import discord

def get_role_mentions_in_string(inStr : str, guild : discord.Guild ):
    result = []
    roleIDs = get_role_ids_in_string(inStr)
    for role_id in map(int, roleIDs):
        role = guild.get_role(role_id)
        if role is not None:
            result.append(role)
    return result


def get_role_ids_in_string(inStr : str):
    return [int(x) for x in re.findall(r'<@&([0-9]{15,20})>', inStr)]