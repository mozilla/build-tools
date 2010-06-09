import re

def getPrettyVersion(version):
    version = re.sub(r'a([0-9]+)$', r' Alpha \1', version)
    version = re.sub(r'b([0-9]+)$', r' Beta \1', version)
    version = re.sub(r'rc([0-9]+)$', r' RC \1', version)
    return version
