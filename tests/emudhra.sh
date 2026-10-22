#!/bin/bash
# Check that this image no longer trusts the compromised eMudhra intermediate CAs.
# See https://emudhra.we-have-a-problem.com/
#
# The host serves a certificate chained through one of the compromised intermediates.
# A client that still trusts them connects fine, so a certificate verification failure
# is the PASS condition here. A failure for any other reason (DNS, network) is a FAIL,
# so a broken network cannot make this test pass by accident.
#
# Fixed by the Ubuntu ca-certificates 20260816ubuntu0.* update (system roots, used by
# curl) and uv >= 0.13.4 (updated bundled roots). Each check below fails on an image
# without its fix.
set -u

host=dv-g3b-emudhra.we-have-a-problem.com
rc=0

# curl uses the system trust store; exit code 60 is "certificate verify failed"
curl -sS -m 30 -o /dev/null "https://$host/" 2>/dev/null
if [ $? -eq 60 ]; then
    echo "PASS curl rejects $host"
else
    echo "FAIL curl did not reject $host with a certificate error"
    rc=1
fi

# uv with its bundled roots
out=$(UV_DEFAULT_INDEX="https://$host/simple" uvx --no-cache pycowsay 2>&1)
if grep -q "invalid peer certificate" <<< "$out"; then
    echo "PASS uvx rejects $host"
else
    echo "FAIL uvx did not reject $host with a certificate error:"
    echo "$out" | tail -5
    rc=1
fi

echo "uv: $(uv --version)"
echo "ca-certificates: $(dpkg-query -W -f='${Version}' ca-certificates)"
exit $rc
