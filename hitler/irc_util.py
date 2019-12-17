def encode_modes(target, *modes):
    def key(i):
        if isinstance(i, str):
            name = i
            val = ''
        else:
            name, val = i

        return not bool(val), name, val

    m = tuple(sorted(modes, key=key))
    if not m:
        return ''

    j = 0
    while j < len(m):
        cur_sign = None
        modenames = ''
        modevals = []

        i = 0
        while len(target + modenames + ' '.join(modevals)) < 450 and i < 4 and j < len(m):
            _, name, val = key(m[j])
            if cur_sign != name[0]:
                cur_sign = name[0]
                modenames += name[0]
            modenames += name[1:]
            if val:
                modevals += [val]
            i += 1
            j += 1

        yield [modenames] + modevals


def parse_modes(server_config, modestr, targets):
    last = None
    i = 0
    out = []

    param_modes, list_modes, param_set_modes, *_ = server_config['CHANMODES'].split(',')

    for char in modestr:
        if char in '+-':
            last = char
            continue

        if last is None:
            raise ValueError("Modes have to begin with + or -")

        param_modes = param_modes | list_modes
        if last == '+':
            param_modes |= param_set_modes

        if char in param_modes:
            out.append((last == '+', char, targets[i]))
            i += 1
        else:
            out.append((last == '+', char, None))
    return out
