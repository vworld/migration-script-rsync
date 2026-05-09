# Rsync Migration Script (Safe)

Small personal Python script built around rsync for consolidating and reorganizing large amounts of data across drives.

The script:
- reads src/dest mappings from CSV
- checks destination free space
- copies using rsync
- verifies using rsync dry-run
- deletes source only after successful verification
- logs successes/errors
- continues on failure

It is intentionally:
- Linux-focused
- sequential
- simple
- HDD-friendly

---

# Requirements

- Python 3
- rsync
- du

---

# CSV Format

```csv
"/mnt/PhoneBackups","/mnt/MediaStore/PhoneBackups"
"/path/to/source/dir-or-file","/path/to/dest"
````

> Notes: quotes recommended

---

# Verification

Verification uses:

```bash
rsync --dry-run --itemize-changes
```

Meaning:

* no meaningful output → verification successful
* output exists → verification failed

This intentionally does NOT use checksum verification because large HDD datasets make that prohibitively slow.

Extra files already existing in destination are allowed.

The destination is treated as a consolidation/archive target rather than an exact mirror.

---

# Logs

## success.log

Append-only JSON lines containing:

* timestamps
* src/dest
* size info
* status

## error.log

Append-only JSON lines containing:

* timestamps
* row info
* errors/exceptions

---

# Run

```bash
python3 migrate.py
```

or:

```bash
chmod +x migrate.py
./migrate.py
```

---

# Notes

* Source deletion is permanent.
* Source is deleted ONLY after successful verification.
* Processing continues even if a row fails.
* Sequential execution is intentional to avoid HDD thrashing.

---

# License

MIT