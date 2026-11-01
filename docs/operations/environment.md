# Environment files

`.env` and `SpeakCV/.env` are no longer tracked. Copy `.env.example` to `.env` and fill it in.

## Before pulling this change on any machine, including the VPS

Git deletes a file when a pull removes it from tracking. Back up first:

    cp .env ~/env-backup-interview-path && chmod 600 ~/env-backup-interview-path

After the pull, restore it, then add the new variables listed in `.env.example`.
Switching between a branch that tracks `.env` and one that does not has the same effect.

## Secrets exposed in history

History was not rewritten, because the repository is private. Rotate every value that was tracked:
the AI proxy key, `SECRET_KEY`, the MySQL root password and the admin password. If this repository
ever goes public or to the organiser, publish from a new repository, because old dumps remain in history.

## Upload size limits

The backend enforces `MAX_UPLOAD_MB` while reading a file, but multipart parsing has already spooled the
whole request to disk by then. So `deploy/Caddyfile` also sets `request_body max_size` on the API domain.
If you raise `MAX_UPLOAD_MB`, raise that limit too, keeping it a little above the upload limit.

## Public address for tracked links

`SPEAKCV_PUBLIC_URL` is the address candidates open, for example `https://speak.hire.test` (no trailing slash needed).
JD Studio builds each channel link from it as `${SPEAKCV_PUBLIC_URL}/jobs/{slug}?src={token}`. HR copies the content and
posts it by hand. When unset it defaults to `http://localhost:3000`, so set it on every server before copying links.
