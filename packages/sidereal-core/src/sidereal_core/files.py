"""What has to happen to a user's uploads before that user can be deleted."""

from __future__ import annotations

import logging
from uuid import UUID

from sidereal_core.directus import DirectusClient, DirectusError
from sidereal_core.models import DirectusFile

logger = logging.getLogger(__name__)
# A practice's whole file store is smaller than this; a user's share of it always is.
MAX_UPLOADS = 1000


async def release_uploads(
    client: DirectusClient, user_id: UUID, *, to: UUID | None = None
) -> list[DirectusFile]:
    """Hand every file this user uploaded to `to`, or to nobody.

    Deleting the user leaves `uploaded_by` null, and a tutor's write rule on a file is that
    column, so material nobody is named on can be maintained by an administrator alone.
    """
    files = await client.list_files(
        filter={"uploaded_by": {"_eq": str(user_id)}}, limit=MAX_UPLOADS
    )
    for file in files:
        await _reassign(client, file.id, to)
    if files:
        logger.info("released %d upload(s) from user %s to %s", len(files), user_id, to)
    return files


async def _reassign(client: DirectusClient, file_id: UUID, to: UUID | None) -> None:
    """A caller a rule will not let the file point at leaves it pointing at nobody."""
    try:
        await client.update_file(file_id, {"uploaded_by": None if to is None else str(to)})
    except DirectusError:
        if to is None:
            raise
        logger.warning("file %s could not be handed to %s; releasing it instead", file_id, to)
        await client.update_file(file_id, {"uploaded_by": None})
