#!/usr/bin/env bash
# Start the product on the loopback after the computer starts (S3-T20,
# decision 0041 item 6; docs/13_DEPLOYMENT_AND_OPERATIONS.md, "S3-T20 start
# on boot").
#
# The caller supplies the environment of the live installation. This script
# reads no settings file and prints no setting. It stops at the first command
# that fails and exits with that command's exit code.
set -euo pipefail

# A boot start is always a loopback start: the entry never receives the remote
# host name here, and the lead exposes again afterwards.
unset EII_REMOTE_HOST

cd "$(dirname "$0")/../.."

# 1. Retire the process records a previous boot left behind; nothing is
#    signalled. A record of this boot that is not owned refuses, and no later
#    step runs.
./eii down --previous-boot
# 2. Start the database service and wait for it to answer.
./eii db-up
# 3. Probe only.
./eii preflight
# 4. Start the product behind the loopback entry.
./eii up
