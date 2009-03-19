STAGE_USERNAME ?= ffxbld
STAGE_SERVER   ?= stage.mozilla.org
STAGE_PATH     ?= /home/ftp/pub/mozilla.org/mobile/dists
SSH_KEY        ?= $(HOME)/.ssh/ffxbld_dsa
WORKDIR         = /scratchbox/users/cltbld/home/cltbld/sign-debs
SBOX_WORKDIR    = sign-debs
SBOX_PATH       = /scratchbox/moz_scratchbox

all: setup download-repository download-debs sign

echo:
	@echo STAGE_USERNAME: $(STAGE_USERNAME)
	@echo STAGE_SERVER: $(STAGE_SERVER)
	@echo STAGE_PATH: $(STAGE_PATH)
	@echo SSH_KEY: $(SSH_KEY)
	@echo WORKDIR: $(WORKDIR)
	@echo SBOX_WORKDIR: $(SBOX_WORKDIR)
	@echo SBOX_PATH: $(SBOX_PATH)

setup:
	mkdir -p $(WORKDIR)/dists/chinook/release/binary-armel

download-repository:
	rsync -azv -e 'ssh -i $(SSH_KEY)' $(STAGE_USERNAME)@$(STAGE_SERVER):$(STAGE_PATH)/. $(WORKDIR)/dists/.

download-debs:
	@echo -n Copy the debs to $(WORKDIR)/dists/chinook/release/binary-armel and hit return.  [done]
	@read

sign:
	$(SBOX_PATH) -p -d $(SBOX_WORKDIR) dpkg-scanpackages dists/chinook/release/binary-armel/ /dev/null | gzip -9c > $(WORKDIR)/dists/chinook/release/binary-armel/Packages.gz
	for i in dists/chinook/release/binary-armel dists/chinook/release dists/chinook; do \
	  rm -f $(WORKDIR)/$$i/Release.gpg; \
	  $(SBOX_PATH) -p -d $(SBOX_WORKDIR)/$$i apt-ftparchive release . > $(WORKDIR)/$$i/Release; \
	  gpg -abs -o $(WORKDIR)/$$i/Release.gpg $(WORKDIR)/$$i/Release; \
	done

upload:
	rsync -e "ssh -i $(SSH_KEY)" -azv $(WORKDIR)/dists/. \
	  $(STAGE_USERNAME)@$(STAGE_SERVER):$(STAGE_PATH)/.
