

def get_cmd_displayname(api, cmdname):
    dname = api.get(cmdname, {}).get(
        'name',
        cmdname.replace('_', ' ').capitalize()
    )
    dname_parts = dname.split(' ')
    if dname_parts[:2] == ['Create', 'sibling']:
        dname = f'Create a {" ".join(dname_parts[2:])}' \
                f'{" " if len(dname_parts) > 2 else ""}sibling'
    return dname
