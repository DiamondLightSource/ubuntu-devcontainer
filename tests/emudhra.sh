#!/bin/bash
# Check that this image no longer trusts the compromised eMudhra intermediate CAs.
# See https://emudhra.we-have-a-problem.com/
#
# Each host serves a certificate chained through one of the compromised intermediates.
# A client that still trusts them connects fine, so a certificate verification failure
# is the PASS condition here. A failure for any other reason (DNS, network) is a FAIL,
# so a broken network cannot make this test pass by accident.
#
# Fixed by uv >= 0.13.4 (updated bundled roots) and the Ubuntu ca-certificates
# 20260816ubuntu0.* update (system roots, used by curl and by uv --system-certs).
set -u

HOSTS="dv-g3b-emudhra.we-have-a-problem.com dv-g3b-aaa-emudhra.we-have-a-problem.com"
rc=0

for host in $HOSTS; do
    # curl uses the system trust store; exit code 60 is "certificate verify failed"
    curl -sS -m 30 -o /dev/null "https://$host/" 2>/dev/null
    if [ $? -eq 60 ]; then
        echo "PASS curl rejects $host"
    else
        echo "FAIL curl did not reject $host with a certificate error"
        rc=1
    fi

    # uv with its bundled roots, then with the system store
    for flags in "" "--system-certs"; do
        out=$(UV_DEFAULT_INDEX="https://$host/simple" uvx $flags --no-cache pycowsay 2>&1)
        if grep -q "invalid peer certificate" <<< "$out"; then
            echo "PASS uvx $flags rejects $host"
        else
            echo "FAIL uvx $flags did not reject $host with a certificate error:"
            echo "$out" | tail -5
            rc=1
        fi
    done
done

echo "uv: $(uv --version)"
echo "ca-certificates: $(dpkg-query -W -f='${Version}' ca-certificates)"
exit $rc
