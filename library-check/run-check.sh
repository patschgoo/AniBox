#!/bin/sh
# AniBox Library Check: run from any folder.
cd "$(dirname "$0")" || exit 1
exec python3 -m anibox_check "$@"
