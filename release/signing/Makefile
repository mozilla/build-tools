# This Makefile is meant to be run on keymaster after all locales are built
# and before partial MARs are generated.
# Common usage is as follows:
#  1. Open up signcodepwd.exe and enter passphrase
#  2. mkdir ~/signing-work/$product-$version
#  3. cd ~/signing-work/$product-$version
#  4. cp ~/Makefile .
#  5. make EMAIL=yourname@domain.com BUILD=1 VERSION=3.1b1 \
#          TAG=FIREFOX_3_1b1_RELEASE REPO=releases/mozilla-1.9.1
#
# You can pass the other variables listed below, too, if you want to use a
# different stage server, ssh key or username, or sign a different product, etc.
#
# You should receive mail a few times during this process:
#  * Right before sign-release.pl starts
#  * After sign-release.pl completes successfully
#  * Right before sign-files is called, to remind you to enter the passphrase
#  * After the entire process is done, and files are ready to inspected
#    and uploaded.
#
# Note that if something errors you will not receive e-mails past that point
# or mail about the error.
#
# When you're satisfied with the builds and ready to upload them you can run:
#     make upload
# with all of the same variable definitions which will rsync the signed builds
# back from whence they came.
# And use
#     make upload-log
# to upload the exe/dll signing log, which triggers the automation to continue.

# Make sure necessary variables are defined / set defaults
GPGPASS        := $(shell bash -c 'if [[ -z "${SKIP_PASS}" ]]; then read -s -p "Enter PGP passphrase:" pass; echo $$pass; fi')
VERSION         = $(error VERSION must be defined)
BUILD           = $(error BUILD must be defined)
REPO            = $(error REPO must be defined)
TAG            ?= FIREFOX_$(subst .,_,$(VERSION))_RELEASE
HGROOT         ?= https://hg.mozilla.org/
EMAIL          ?= release@mozilla.com
STAGE_USERNAME ?= ffxbld
STAGE_HOST     ?= stage.mozilla.org
SSH_KEY        ?= $(HOME)/.ssh/ffxbld_dsa
PRODUCT        ?= firefox
BRAND_NAME     ?= $(PRODUCT)
WORKDIR         = $(PWD)
MAR             = $(WORKDIR)/mar.exe
SEVENZIP        = $(WORKDIR)/7-Zip/7z.exe
UPX_BIN         = $(WORKDIR)/upx/upx.exe
CONCURRENCY    ?= 4
KEYDIR         ?= d:/2011-keys
GPG_KEY        ?= $(WORKDIR)/key-checkout/PUBLIC-KEY
FREE_SPACE_REQ ?= 10000000 # in KB
BASEDIR       ?= ~/signing-work
PYTHONPATH     := $(WORKDIR)/lib/python:${PYTHONPATH}
export PYTHONPATH
CONFIG_REPO_PATH ?= build/buildbot-configs
RELCONFIG       = $(error RELCONFIG must be defined)

ifeq ($(PRODUCT),firefox)
APP_NAME       ?= browser
else
APP_NAME        = $(error APP_NAME must be defined)
endif

all: df verify-gpg-passphrase setup stubs verify-signcode-passphrase download verify-download sign stage verify fake-upload

autosign: df verify-gpg-passphrase setup stubs verify-signcode-passphrase download-loop verify-download sign stage verify fake-upload postsign

echo:
	@echo EMAIL: $(EMAIL)
	@echo STAGE_USERNAME: $(STAGE_USERNAME)
	@echo SSH_KEY: $(SSH_KEY)
	@echo WORKDIR: $(WORKDIR)
	@echo PRODUCT: $(PRODUCT)
	@echo VERSION: $(VERSION)
	@echo BUILD: $(BUILD)
	@echo TAG: $(TAG)
	@echo REPO: $(REPO)

df:
	@AVAIL=$(shell df -k . | tail -n 1 | awk '{print $$4}'); \
	if [ $$AVAIL -lt $(FREE_SPACE_REQ) ]; then \
		echo "Not enough disk space available." ; \
		echo "Required disk space: $(FREE_SPACE_REQ) KB ($$AVAIL KB available)"; \
		echo "Run \"make cleanup\" explicitly to remove old binaries"; \
		exit 1; \
	fi

verify-gpg-passphrase:
ifndef GPGPASS
	echo "GPG Passphrase must be defined for these targets"
	exit 1
endif
	@f=`mktemp` \
	&& (touch $$f \
	&& gpg --no-use-agent --batch --passphrase "$(GPGPASS)" -sba $$f \
	&& rm -f $$f $$f.asc \
	&& blat -to $(EMAIL) \
	    -subject "GPG passphrase verification for $(PRODUCT) $(VERSION) succeeded" \
	    -body "EOM") \
	|| \
	(rm -f $$f $$f.asc \
	&& blat -to $(EMAIL) \
	    -subject "GPG passphrase verification for $(PRODUCT) $(VERSION) failed" \
	    -body "EOM"; exit 1)

verify-signcode-passphrase:
	@d=`mktemp -d` \
	&& mkdir -p $$d \
	&& (cp signing/signcodepwd.exe $$d \
	&& cd $$d \
	&& signcode \
	    -spc $(KEYDIR)/MozAuthenticode.spc \
	    -v $(KEYDIR)/MozAuthenticode.pvk \
	    -t http://timestamp.verisign.com/scripts/timestamp.dll \
	    -i http://www.mozilla.com \
	    -a sha1 \
	    -tr 5 \
	    -tw 60 \
	    signcodepwd.exe \
	&& chktrust /q signcodepwd.exe \
	&& cd - && rm -rf "$$d" \
	&& blat -to $(EMAIL) \
	    -subject "signcode.exe password verification for $(PRODUCT) $(VERSION) succeeded" \
	    -body "EOM") \
	|| \
	(rm -rf "$$d"; \
	 blat -to $(EMAIL) \
	    -subject "signcode.exe password verification for $(PRODUCT) $(VERSION) failed" \
	    -body "EOM"; exit 1)

cleanup:
	./cleanup.sh -s $(FREE_SPACE_REQ) -d $(BASEDIR)/

setup:
	# Pull/copy the required tools.
	cvs -d:ext:cltbld@cvs.mozilla.org:/mofo co -d signing release/signing/tools
	cvs -d:ext:cltbld@cvs.mozilla.org:/mofo co -d stage release/stage
	cvs -d:ext:cltbld@cvs.mozilla.org:/mofo co -d key-checkout release/keys/pgp
	cvs -d:ext:cltbld@cvs.mozilla.org:/cvsroot co -d MozBuild mozilla/tools/release/MozBuild
	rsync -av $(HOME)/signing-utils/7-Zip . 
	rsync -av $(HOME)/signing-utils/mar.exe . 
	rsync -av $(HOME)/signing-utils/upx . 

ifneq ($(filter 3.0.%,$(VERSION)),)
stubs: stubs-cvs checkouts/stubs/7z/7zSD.sfx.compressed

else
stubs: stubs-hg checkouts/stubs/7z/7zSD.sfx.compressed

endif

checkouts/stubs/7z/7zSD.sfx.compressed: checkouts/stubs/7z/7zSD.sfx
	$(UPX_BIN) --best -o $@ $<

stubs-cvs:
	rm -rf checkouts/stubs
	mkdir -p checkouts/stubs
	(cd checkouts/stubs; cvs -d:ext:cltbld@cvs.mozilla.org:/cvsroot co -r $(TAG) -d 7z mozilla/other-licenses/7zstub/$(PRODUCT))
	(cd checkouts/stubs; cvs -d:ext:cltbld@cvs.mozilla.org:/cvsroot co -r $(TAG) -d tagfile mozilla/$(APP_NAME)/installer/windows/app.tag)

stubs-hg:
	rm -rf checkouts/stubs
	mkdir -p checkouts/stubs/7z
	mkdir -p checkouts/stubs/tagfile
	(cd checkouts/stubs/7z; wget -O 7zSD.sfx $(HGROOT)$(REPO)/raw-file/$(TAG)/other-licenses/7zstub/$(PRODUCT)/7zSD.sfx)
	(cd checkouts/stubs/tagfile; wget -O app.tag $(HGROOT)$(REPO)/raw-file/$(TAG)/$(APP_NAME)/installer/windows/app.tag)

verify-download:
	python download_builds.py -V --product $(PRODUCT) -r $(CONFIG_REPO_PATH) \
        --hgurl $(HGROOT) $(VERSION) \
        unsigned-build$(BUILD)/ $(SSH_KEY) $(STAGE_USERNAME) \
        $(STAGE_HOST) $(RELCONFIG)

download-loop:
	python download_builds.py --product $(PRODUCT) -r $(CONFIG_REPO_PATH) \
        --hgurl $(HGROOT) $(VERSION) unsigned-build$(BUILD)/ $(SSH_KEY) \
		$(STAGE_USERNAME) $(STAGE_HOST) $(RELCONFIG)

download:
	# Download the builds.
	rsync -av --exclude-from download-exclude.list -e "ssh -i $(SSH_KEY)" \
	  $(STAGE_USERNAME)@$(STAGE_HOST):/home/ftp/pub/$(PRODUCT)/nightly/$(VERSION)-candidates/build$(BUILD)/ \
	  unsigned-build$(BUILD)
	# Copy linux/mac builds over to the signed dir, because they don't need internal signing.
	rsync -av --exclude '*unsigned*' unsigned-build$(BUILD)/ signed-build$(BUILD)/
	# Make sure we copy over linux/mac partner repacks (which are in unsigned, unfortunately)
	rsync -av --exclude '*win32*' unsigned-build$(BUILD)/unsigned/ signed-build$(BUILD)/

sign: sign-files checksum-files create-sigs verify-sigs quick-verify

sign-files:
	blat -to $(EMAIL) \
	     -subject "sign-release.py for $(PRODUCT) $(VERSION) starting" \
		 -body "EOM"
	./sign-release.py --keydir $(KEYDIR) -j$(CONCURRENCY) --product $(BRAND_NAME) -o signed-build$(BUILD) unsigned-build$(BUILD) >> win32_signing_build$(BUILD).log 2>&1
	# And copy over the info file and XPIs.
	cp -pv ./unsigned-build$(BUILD)/unsigned/win32_info.txt ./signed-build$(BUILD)/
	rsync -av ./unsigned-build$(BUILD)/unsigned/win32/xpi ./signed-build$(BUILD)/win32
	blat -to $(EMAIL) \
	     -subject "sign-release.py for $(PRODUCT) $(VERSION) completed" \
		 -body "EOM"

create-sigs:
ifndef GPGPASS
	echo "GPG Passphrase must be defined for these targets"
	exit 1
endif
	# Generate detached sigs.
	blat -to $(EMAIL) \
	     -subject "Running sign-files for $(PRODUCT) $(VERSION)" \
		 -body "EOM"
	@cd $(WORKDIR)/signed-build$(BUILD) && echo $(GPGPASS) | ../signing/sign-files .

verify-sigs:
	if ./verify-gpg.py --verbose --key-file $(GPG_KEY) \
		signed-build$(BUILD) > verify_gpg_build$(BUILD).log 2>&1; then \
	    blat -to $(EMAIL) \
		 -subject "GPG Signature verification succeeded" \
		 -body "EOM"; \
	else \
	    blat verify_gpg_build$(BUILD).log -to $(EMAIL) \
		 -subject "GPG Signature verification failed"; \
	fi

stage: create-contrib fix-permissions

create-contrib:
	mkdir -p $(WORKDIR)/signed-build$(BUILD)/contrib
	chmod 2775 $(WORKDIR)/signed-build$(BUILD)/contrib
	mkdir -p $(WORKDIR)/signed-build$(BUILD)/contrib-localized
	chmod 2775 $(WORKDIR)/signed-build$(BUILD)/contrib-localized
	cp $(GPG_KEY) $(WORKDIR)/signed-build$(BUILD)/KEY

checksum-files:
	$(WORKDIR)/stage/checksum-files $(WORKDIR)/signed-build$(BUILD)
	# exclude partner repacks from SUMS files
	grep -v "partner-repack" $(WORKDIR)/signed-build$(BUILD)/MD5SUMS > $(WORKDIR)/signed-build$(BUILD)/MD5SUMS.out \
	&& mv $(WORKDIR)/signed-build$(BUILD)/MD5SUMS.out $(WORKDIR)/signed-build$(BUILD)/MD5SUMS
	grep -v "partner-repack" $(WORKDIR)/signed-build$(BUILD)/SHA1SUMS > $(WORKDIR)/signed-build$(BUILD)/SHA1SUMS.out \
	&& mv $(WORKDIR)/signed-build$(BUILD)/SHA1SUMS.out $(WORKDIR)/signed-build$(BUILD)/SHA1SUMS

fix-permissions:
	# Because these files will be owned by 'firefox' (which has users in it
	# whom we don't want to be able to mess with release files) we need to
	# ensure the permissions are locked down. Everything should already only
	# be writeable by the owning user, but this will make sure of that.
	# Additionally, when the MARs are signed they end up with 755 permissions,
	# which is a little silly. This will fix them to be 644, too.
	find $(WORKDIR)/signed-build$(BUILD)/ -type f \
	  -exec chmod 644 {} \;

verify: verify-signatures verify-win32 verify-asc
	echo "Verification completed"

# This test verifies that installer signing is valid and can be traced back to
# a valid root certificate. Basically, it runs 'chktrust /q *.exe' for every
# win32 locale directory.
verify-signatures:
	cd $(WORKDIR)/signed-build$(BUILD)/win32 && ../../signing/verify-signatures

verify-signatures2:
	if ./verify-signature.py --product $(BRAND_NAME) unsigned-build$(BUILD) signed-build$(BUILD) > verify-signatures-build${BUILD}.log 2>&1; then \
	    blat -to $(EMAIL) \
		 -subject "Signature verification succeeded"\
		 -body "EOM"; \
	else \
	    blat verify-signatures-build${BUILD}.log -to $(EMAIL) \
		 -subject "Signature verification failed"; \
	fi

# This test ensures that every exe and mar in the signed-build$(BUILD) directory
# differs from its unsigned counterpart.
verify-win32: DIFF_FILES=$(strip $(shell diff -rq $(WORKDIR)/unsigned-build$(BUILD)/unsigned/ \
                           signed-build$(BUILD)/ | grep -E '(\.exe|\.mar)\ ' | wc -l))
verify-win32: TOTAL_FILES=$(strip $(shell find $(WORKDIR)/unsigned-build$(BUILD)/unsigned/ \
                            -name '*.exe' -or -name '*.mar' | wc -l))
verify-win32:
	@test $(TOTAL_FILES) -gt 0 || \
	  (echo "No files in $(WORKDIR)/unsigned-build$(BUILD)/unsigned, bailing..." && exit 1)
	@test $(DIFF_FILES) -eq $(TOTAL_FILES) || \
	  (echo "Some files are unsigned, bailing..." && exit 1)
	@echo "Win32 installers appear to be signed properly"

# Finally, this test makes sure we have asc files for every build in
# signed-build$(BUILD). Note that we do not generate detached sigs for MARs,
# XPIs, logs, text files, etc. Basically, we only generate them for installers,
# packages (tar.bz2, dmg, exe), and source files (tar.bz2, .bundle).
verify-asc: ASC_FILES=$(strip $(shell find $(WORKDIR)/signed-build$(BUILD)/ \
                        -name "*.asc" -type f | wc -l))
verify-asc: TOTAL_FILES=$(strip $(shell find $(WORKDIR)/signed-build$(BUILD)/ \
                          -not -wholename '*update*' -not -name "*.xpi" -not -name "*.asc" \
                          -not -name "*.txt" -not -name "*.log" \
                          -not -name KEY -not -name "partner_build*" -type f | wc -l))
verify-asc:
	@test $(TOTAL_FILES) -gt 0 || \
	  (echo "No files in $(WORKDIR)/signed-build$(BUILD), bailing..." && exit 1)
	@test $(ASC_FILES) -eq $(TOTAL_FILES) || \
	  (echo "Incorrect number of .asc files" && exit 1)
	@echo "Correct number of .asc files are present"

fake-upload:
	rsync -n -e "ssh -i $(SSH_KEY)" -avO $(WORKDIR)/signed-build$(BUILD)/ \
	  $(STAGE_USERNAME)@$(STAGE_HOST):/home/ftp/pub/$(PRODUCT)/nightly/$(VERSION)-candidates/build$(BUILD)/ \
	  | grep -v asc | grep -v exe | grep -v 'update/win32/.*/.*\.mar'
	blat -to $(EMAIL) \
	     -subject "Signing of $(PRODUCT) $(VERSION) done, ready for inspection"\
	     -body "EOM"

postsign: upload upload-log verify-signatures2

quick-verify:
	if ./verify-signature.py --product $(BRAND_NAME) unsigned-build$(BUILD) \
        --quick-verify signed-build$(BUILD) > quick-verify-signatures-build${BUILD}.log 2>&1; then \
	    blat -to $(EMAIL) \
		 -subject "Quick Signature verification succeeded"\
		 -body "EOM"; \
	else \
	    blat quick-verify-signatures-build${BUILD}.log -to $(EMAIL) \
		 -subject "Quick Signature verification failed"; \
	fi

upload:
	rsync -e "ssh -i $(SSH_KEY)" -avO $(WORKDIR)/signed-build$(BUILD)/ \
	  $(STAGE_USERNAME)@$(STAGE_HOST):/home/ftp/pub/$(PRODUCT)/nightly/$(VERSION)-candidates/build$(BUILD)/

upload-log:
	rsync -e "ssh -i $(SSH_KEY)" -av $(WORKDIR)/win32_signing_build${BUILD}.log \
	  $(STAGE_USERNAME)@$(STAGE_HOST):/home/ftp/pub/$(PRODUCT)/nightly/$(VERSION)-candidates/build$(BUILD)/
