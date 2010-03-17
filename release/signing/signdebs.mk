RELEASE			?=
BRANCH_NICK		?= $(error BRANCH_NICK must be defined)
LOCALE			?= $(error LOCALE must be defined)
SBOX_PATH		= /scratchbox/moz_scratchbox
RSYNC_ARGS		?= --delete --progress --partial
MAEMO_VERSION	?= chinook
FENNEC_FILEURL	?= $(error FENNEC_FILEURL must be defined)
SIGNDEBS_BASEDIR	?= sign-debs
SBOX_WORKDIR	?= $(SIGNDEBS_BASEDIR)/$(BRANCH_NICK)_$(LOCALE)
WORKDIR			?= /scratchbox/users/cltbld/home/cltbld/$(SBOX_WORKDIR)

STAGE_DIR		?= /pub/mozilla.org/mobile/repos
BASE_STAGE_PATH	?= /home/ftp
BASE_STAGE_URL	?= http://ftp.mozilla.org
STAGE_USERNAME	?= ffxbld
STAGE_SERVER	?= stage.mozilla.org
STAGE_PATH		?= $(BASE_STAGE_PATH)/$(STAGE_DIR)/$(BRANCH_NICK)_$(LOCALE)
STAGE_URL       ?= $(BASE_STAGE_URL)/$(STAGE_DIR)/$(BRANCH_NICK)_$(LOCALE)
SSH_KEY			?= $(HOME)/.ssh/ffxbld_dsa

INSTALL_CONTENTS = "[install]\nrepo_deb_3 = deb $(STAGE_URL) $(MAEMO_VERSION) $(REPO_SECTION)\ncatalogues = fennec\npackage = fennec\n\n[fennec]\nname = Mozilla $(BRANCH_NICK) $(LOCALE) Catalog\nuri = $(STAGE_URL)\ndist = $(MAEMO_VERSION)\ncomponents = $(REPO_SECTION)"

FENNEC_FILENAME	= $(notdir $(FENNEC_FILEURL))
FENNEC_FILEPATH	= $(WORKDIR)/dists/$(MAEMO_VERSION)/$(REPO_SECTION)/binary-armel/$(FENNEC_FILENAME)

TARGETS = echo setup

ifndef RELEASE
REPO_SECTION	:= extras
INSTALL_FILENAME	= $(BRANCH_NICK)_$(LOCALE)_nightly.install
else
REPO_SECTION	:= release
INSTALL_FILENAME	= $(BRANCH_NICK)_$(LOCALE).install
endif
INSTALL_FILEPATH	= $(WORKDIR)/$(INSTALL_FILENAME)


TARGETS += $(INSTALL_FILEPATH) download-fennec

TARGETS += sign upload

all: $(TARGETS)

setup:
	rm -rf $(WORKDIR)/dists $(INSTALL_FILEPATH)
	mkdir -p $(WORKDIR)/dists/$(MAEMO_VERSION)/$(REPO_SECTION)/binary-armel

download-fennec:
	wget -O $(FENNEC_FILEPATH) $(FENNEC_FILEURL)

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
	@echo INSTALL_FILENAME: $(INSTALL_FILENAME)

%.install:
	@echo -e $(INSTALL_CONTENTS) > "$@"

sign:
	$(SBOX_PATH) -p -d $(SBOX_WORKDIR) apt-ftparchive packages dists/$(MAEMO_VERSION)/$(REPO_SECTION)/binary-armel | gzip -9c > $(WORKDIR)/dists/$(MAEMO_VERSION)/$(REPO_SECTION)/binary-armel/Packages.gz
	for i in dists/$(MAEMO_VERSION)/$(REPO_SECTION)/binary-armel dists/$(MAEMO_VERSION)/$(REPO_SECTION) dists/$(MAEMO_VERSION); do \
	  rm -f $(WORKDIR)/$${i}/Release.gpg; \
	  $(SBOX_PATH) -p -d $(SBOX_WORKDIR)/$${i} apt-ftparchive release . > $(WORKDIR)/Release.tmp; \
	  mv $(WORKDIR)/Release.tmp $(WORKDIR)/$${i}/Release; \
	  gpg -abs -o $(WORKDIR)/$${i}/Release.gpg $(WORKDIR)/$${i}/Release; \
	done

upload:
	ssh -i $(SSH_KEY) $(STAGE_USERNAME)@$(STAGE_SERVER) "mkdir -p $(STAGE_PATH)"
	rsync -e "ssh -i $(SSH_KEY)" -azv $(RSYNC_ARGS) $(WORKDIR)/dists $(WORKDIR)/$(INSTALL_FILENAME) \
	  $(STAGE_USERNAME)@$(STAGE_SERVER):$(STAGE_PATH)/.
