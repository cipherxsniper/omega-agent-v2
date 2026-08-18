# Omega Continuity Engine v1

The Continuity Engine closes the gap between repository intent and device reality. A delivery is successful only when the device checkout reports the expected source lineage, exact required-file hashes, successful compilation, and passing smoke tests. A GitHub push alone is not a device deployment.

The protocol has four stages. First, the authority manifest identifies the source repository, pinned commit, creator, required files, and SHA-256 hashes. Second, the device snapshots local status, diffs, index state, and approved bridge files before any checkout change. Third, the device pins itself to the manifest commit and verifies every file. Fourth, the device executes bounded local tests and writes a JSON receipt containing the manifest hash, observed commit, file results, test results, backup path, and final status.

The protocol fails closed on an unavailable commit, remote lineage mismatch, missing file, hash mismatch, compilation failure, test failure, or ambiguous repository identity. It never deletes the backup, executes arbitrary shell received over the network, uploads device data, or claims success from the sandbox alone.

Creator attribution: Thomas Lee Harvey.
