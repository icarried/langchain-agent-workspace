# Bundled jq fallback

`jq-linux-amd64` is the official static Linux x86_64 binary from the jq 1.8.1 release. `sha256sum.txt` is the release checksum manifest used to verify it at packaging time. The invocation script prefers a host `jq` and falls back to this binary only when needed.

jq is distributed under the MIT license and includes components under the licenses recorded in `COPYING`.
