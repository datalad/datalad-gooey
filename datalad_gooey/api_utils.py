

def get_cmd_displayname(api, cmdname):
    return api.get(cmdname, {}).get(
        'name',
        cmdname.replace('_', ' ').capitalize()
    )
