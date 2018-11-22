def parsePlainL10nChangesets(changesets):
    ret = {}
    for line in changesets.splitlines():
        locale, revision = line.rstrip().split()
        ret[locale] = revision
    return ret
