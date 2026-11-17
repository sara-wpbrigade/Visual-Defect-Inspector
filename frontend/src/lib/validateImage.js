/** Client-side checks that give fast feedback before a photo is uploaded. */

import {
  ALLOWED_IMAGE_EXTENSIONS,
  ALLOWED_IMAGE_TYPES,
  MAX_IMAGE_BYTES,
  MAX_IMAGE_MEGABYTES,
} from '../constants';

const DOT = '.';

/** Whether the browser reports a JPEG/PNG type; a missing type falls back to the extension. */
export function isSupportedImage(file) {
  if (ALLOWED_IMAGE_TYPES.includes(file.type)) {
    return true;
  }
  return !file.type && ALLOWED_IMAGE_EXTENSIONS.includes(fileExtension(file.name));
}

/**
 * Return an operator-friendly problem description, or null when the file is usable.
 * The backend still validates the real bytes; this only avoids a pointless upload.
 *
 * @param {File | null | undefined} file
 * @returns {string | null}
 */
export function validateImage(file) {
  if (!file) {
    return 'Choose a photo to inspect.';
  }
  if (file.size === 0) {
    return 'That file is empty. Choose a photo.';
  }
  if (!isSupportedImage(file)) {
    return 'Use a JPEG or PNG photo.';
  }
  if (file.size > MAX_IMAGE_BYTES) {
    return `That photo is larger than ${MAX_IMAGE_MEGABYTES} MB. Choose a smaller one.`;
  }
  return null;
}

function fileExtension(name = '') {
  const dotIndex = name.lastIndexOf(DOT);
  return dotIndex === -1 ? '' : name.slice(dotIndex).toLowerCase();
}
