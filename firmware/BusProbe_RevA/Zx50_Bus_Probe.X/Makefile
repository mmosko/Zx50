# Environment 
MKDIR=mkdir
CP=cp
CCADMIN=CCadmin
RANLIB=ranlib

# Define your source directory
SRC_DIR = src

# build
build: .build-post

.build-pre:
	@echo "--- Pre-Build: Checking $(SRC_DIR) ---"
	# Uncomment the line below if you want to trigger your custom src/Makefile
	# $(MAKE) -C $(SRC_DIR) all

.build-post: .build-impl
# Add your post 'build' code here...

# clean
clean: .clean-post

.clean-pre:
	@echo "--- Pre-Clean: Cleaning $(SRC_DIR) ---"
	# Uncomment the line below if you want to trigger your custom src/Makefile clean
	# $(MAKE) -C $(SRC_DIR) clean

.clean-post: .clean-impl
# Add your post 'clean' code here...

# clobber
clobber: .clobber-post

.clobber-pre:
# Add your pre 'clobber' code here...

.clobber-post: .clobber-impl
# Add your post 'clobber' code here...

# all
all: .all-post

.all-pre:
# Add your pre 'all' code here...

.all-post: .all-impl
# Add your post 'all' code here...

# help
help: .help-post

.help-pre:
# Add your pre 'help' code here...

.help-post: .help-impl
# Add your post 'help' code here...

# include project implementation makefile
include nbproject/Makefile-impl.mk

# include project make variables
include nbproject/Makefile-variables.mk