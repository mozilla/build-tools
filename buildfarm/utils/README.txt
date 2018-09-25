nss is using retry.py and {win32,unix}_util.py. ircs://irc.mozilla.org:6697/mt,isnick says they'll pin the revision in nss, but we still may need to address this usage if we plan on archiving this repo.

Even if we remove tools usage in the gecko tree, we still need to uplift changes to nss to safely retire this repo.
