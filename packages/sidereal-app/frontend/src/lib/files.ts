import { readFile } from "@directus/sdk";
import { useEffect, useState } from "react";

import { directus, directusUrl } from "@/lib/directus";

export interface FileBlob {
  /** An object URL, revoked when the file changes or the component goes away. */
  url: string | null;
  /** What Directus calls the file, or the caller's fallback while that is unknown. */
  name: string;
  isLoading: boolean;
  error: string | null;
}

/** The id of an `m2o directus_files` field, however far the SDK expanded it. */
export function fileIdOf(value: unknown): string | null {
  if (typeof value === "string") {
    return value || null;
  }
  const row = typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
  const id = row?.["id"];
  return typeof id === "string" ? id : null;
}

/**
 * A Directus file as an object URL. The caller's token authorises the asset, and it stays in
 * an `Authorization` header rather than a query string a link or a frame would carry around.
 */
export function useFileBlob(fileId: string | null, fallbackName: string): FileBlob {
  const [state, setState] = useState<FileBlob>({
    url: null,
    name: fallbackName,
    isLoading: fileId !== null,
    error: null,
  });

  useEffect(() => {
    if (!fileId) {
      setState({ url: null, name: fallbackName, isLoading: false, error: null });
      return;
    }

    let objectUrl: string | null = null;
    let cancelled = false;
    const controller = new AbortController();
    setState({ url: null, name: fallbackName, isLoading: true, error: null });

    const bytes = async () => {
      const token = await directus.getToken();
      const response = await fetch(`${directusUrl}/assets/${fileId}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(String(response.status));
      }
      return response.blob();
    };

    // The row is only wanted for the download name, so losing it costs the name, not the file.
    const name = async () => {
      try {
        const row = await directus.request(readFile(fileId, { fields: ["filename_download"] }));
        return row.filename_download || fallbackName;
      } catch {
        return fallbackName;
      }
    };

    const load = async () => {
      try {
        const [blob, downloadName] = await Promise.all([bytes(), name()]);
        if (cancelled) {
          return;
        }
        objectUrl = URL.createObjectURL(blob);
        setState({ url: objectUrl, name: downloadName, isLoading: false, error: null });
      } catch {
        if (!cancelled) {
          setState({
            url: null,
            name: fallbackName,
            isLoading: false,
            error: "This file could not be opened.",
          });
        }
      }
    };

    void load();
    return () => {
      cancelled = true;
      controller.abort();
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [fileId, fallbackName]);

  return state;
}

// A figure names its file the way sidereal_generate does: the Directus file id and a suffix,
// so the renderer sees a file name and never a path.
const ASSET_NAME = /^([0-9a-f-]{36})\.(png|jpe?g|svg)$/i;

/** The file behind an asset name, or null when the name does not name one. */
export function assetFileId(asset: string): string | null {
  return ASSET_NAME.exec(asset.trim())?.[1] ?? null;
}

function base64(bytes: Uint8Array): string {
  // In chunks: one spread of a whole image's bytes overflows the argument list.
  let binary = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }
  return btoa(binary);
}

/** An asset's bytes as the render request carries them: standard base64, no data: prefix. */
export async function assetBase64(asset: string): Promise<string> {
  const fileId = assetFileId(asset);
  if (fileId === null) {
    throw new Error(`${asset} does not name a file`);
  }
  const token = await directus.getToken();
  const response = await fetch(`${directusUrl}/assets/${fileId}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    throw new Error(String(response.status));
  }
  return base64(new Uint8Array(await response.arrayBuffer()));
}
