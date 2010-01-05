RELEASE			?=
BRANCH_NICK		?= $(error BRANCH_NICK must be defined)
LOCALE			?= $(error LOCALE must be defined)
SBOX_PATH		= /scratchbox/moz_scratchbox
RSYNC_ARGS		?= --delete --progress --partial
MAEMO_VERSION	?= chinook
FENNEC_FILEURL	?= $(error FENNEC_FILEURL must be defined)
XULRUNNER_VERSION	?=
SIGNDEBS_BASEDIR	?= sign-debs
SBOX_WORKDIR	?= $(SIGNDEBS_BASEDIR)/$(BRANCH_NICK)_$(LOCALE)
WORKDIR			?= /scratchbox/users/cltbld/home/cltbld/$(SBOX_WORKDIR)

BASE_STAGE_PATH	?= /home/ftp/pub/mozilla.org/mobile/repos
BASE_STAGE_URL	?= http://ftp.mozilla.org/pub/mozilla.org/mobile/repos
STAGE_USERNAME	?= ffxbld
STAGE_SERVER	?= stage.mozilla.org
STAGE_PATH		?= $(BASE_STAGE_PATH)/$(BRANCH_NICK)_$(LOCALE)
STAGE_URL       ?= $(BASE_STAGE_URL)/$(BRANCH_NICK)_$(LOCALE)
SSH_KEY			?= $(HOME)/.ssh/ffxbld_dsa

INSTALL_CONTENTS = "[install]\nrepo_deb_3 = deb $(STAGE_URL) $(MAEMO_VERSION) $(REPO_SECTION)\ncatalogues = fennec\npackage = fennec\n\n[fennec]\nname = Mozilla $(BRANCH_NICK) $(LOCALE) Catalog\nuri = $(STAGE_URL)\ndist = $(MAEMO_VERSION)\ncomponents = $(REPO_SECTION)"

FENNEC_FILENAME	= $(notdir $(FENNEC_FILEURL))
BASE_XULRUNNER_URL	?= $(dir $(FENNEC_FILEURL))
FENNEC_FILEPATH	= $(WORKDIR)/dists/$(MAEMO_VERSION)/$(REPO_SECTION)/binary-armel/$(FENNEC_FILENAME)
XULRUNNER_FILENAME	= xulrunner_$(XULRUNNER_VERSION)_armel.deb
XULRUNNER_FILEURL	= $(BASE_XULRUNNER_URL)/$(XULRUNNER_FILENAME)
XULRUNNER_FILEPATH	= $(WORKDIR)/dists/$(MAEMO_VERSION)/$(REPO_SECTION)/binary-armel/$(XULRUNNER_FILENAME)

TARGETS = echo setup download-repository clean-install-file

ifndef RELEASE
REPO_SECTION	:= extras
INSTALL_FILENAME	= $(BRANCH_NICK)_$(LOCALE)_nightly.install
TARGETS += clean-repository
else
REPO_SECTION	:= release
INSTALL_FILENAME	= $(BRANCH_NICK)_$(LOCALE).install
endif
INSTALL_FILEPATH	= $(WORKDIR)/$(INSTALL_FILENAME)


TARGETS += $(INSTALL_FILEPATH) download-fennec
ifndef XULRUNNER_VERSION
TARGETS += xulrunner-hack
else
TARGETS += download-xulrunner
endif

TARGETS += sign upload

all: $(TARGETS)

setup:
	mkdir -p $(WORKDIR)/dists/$(MAEMO_VERSION)/$(REPO_SECTION)/binary-armel

download-repository:
	ssh -i $(SSH_KEY) $(STAGE_USERNAME)@$(STAGE_SERVER) "test -d $(STAGE_PATH)/dists" && \
	  rsync -azv -e 'ssh -i $(SSH_KEY)' $(RSYNC_ARGS) $(STAGE_USERNAME)@$(STAGE_SERVER):$(STAGE_PATH)/dists/. $(WORKDIR)/dists/. || \
	  echo "No repository to download."

clean-install-file:
	rm -f $(WORKDIR)/*.install

clean-repository:
	find $(WORKDIR)/dists/$(MAEMO_VERSION)/$(REPO_SECTION)/binary-armel/. -name \*.deb -exec rm {} \;

download-fennec:
	rm -rf $(FENNEC_FILEPATH)
	wget -O $(FENNEC_FILEPATH) $(FENNEC_FILEURL)

xulrunner-hack:
	if [ -e tmp.deb ] ; then rm -rf tmp.deb; fi
	mkdir tmp.deb
	(cd tmp.deb && ar xv $(FENNEC_FILEPATH) && tar zxvf control.tar.gz)
	make -f signdebs.mk download-xulrunner XULRUNNER_VERSION=`grep xulrunner tmp.deb/control | sed -e 's/.*xulrunner (>= \([^)]*\)).*/\1/'`
	rm -rf tmp.deb

download-xulrunner:
	rm -f $(XULRUNNER_FILEPATH)
	wget -O $(XULRUNNER_FILEPATH) $(XULRUNNER_FILEURL)

echo:
	@echo STAGE_USERNAME: $(STAGE_USERNAME)
	@echo STAGE_SERVER: $(STAGE_SERVER)
	@echo STAGE_PATH: $(STAGE_PATH)
	@echo SSH_KEY: $(SSH_KEY)
	@echo WORKDIR: $(WORKDIR)
	@echo SBOX_WORKDIR: $(SBOX_WORKDIR)
	@echo SBOX_PATH: $(SBOX_PATH)
	@echo REPO_SECTION: $(REPO_SECTION)
	@echo FENNEC_FILEURL: $(FENNEC_FILEURL)
	@echo FENNEC_FILENAME: $(FENNEC_FILENAME)
	@echo FENNEC_FILEPATH: $(FENNEC_FILEPATH)
	@echo XULRUNNER_FILEURL: $(XULRUNNER_FILEURL)
	@echo XULRUNNER_FILENAME: $(XULRUNNER_FILENAME)
	@echo XULRUNNER_FILEPATH: $(XULRUNNER_FILEPATH)
	@echo INSTALL_FILENAME: $(INSTALL_FILENAME)

%.install:
	@echo -e $(INSTALL_CONTENTS) > "$@"

sign:
	$(SBOX_PATH) -p -d $(SBOX_WORKDIR) apt-ftparchive packages dists/$(MAEMO_VERSION)/$(REPO_SECTION)/binary-armel | gzip -9c > $(WORKDIR)/dists/$(MAEMO_VERSION)/$(REPO_SECTION)/binary-armel/Packages.gz
	for i in dists/$(MAEMO_VERSION)/$(REPO_SECTION)/binary-armel dists/$(MAEMO_VERSION)/$(REPO_SECTION) dists/$(MAEMO_VERSION); do \
	  rm -f $(WORKDIR)/$${i}/Release.gpg; \
	  $(SBOX_PATH) -p -d $(SBOX_WORKDIR)/$${i} apt-ftparchive release . > $(WORKDIR)/$${i}/Release; \
	  gpg -abs -o $(WORKDIR)/$${i}/Release.gpg $(WORKDIR)/$${i}/Release; \
	done

upload:
	ssh -i $(SSH_KEY) $(STAGE_USERNAME)@$(STAGE_SERVER) "mkdir -p $(STAGE_PATH)"
	rsync -e "ssh -i $(SSH_KEY)" -azv $(RSYNC_ARGS) $(WORKDIR)/dists $(WORKDIR)/$(INSTALL_FILENAME) \
	  $(STAGE_USERNAME)@$(STAGE_SERVER):$(STAGE_PATH)/.
