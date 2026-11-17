import { describe, expect, it } from 'vitest';

import { MAX_IMAGE_BYTES } from '../constants';
import { isSupportedImage, validateImage } from './validateImage';

function makeFile(name, type, size = 4) {
  const file = new File(['data'], name, { type });
  if (size !== 4) {
    Object.defineProperty(file, 'size', { value: size });
  }
  return file;
}

describe('isSupportedImage', () => {
  it('accepts JPEG and PNG content types', () => {
    expect(isSupportedImage(makeFile('a.jpg', 'image/jpeg'))).toBe(true);
    expect(isSupportedImage(makeFile('a.png', 'image/png'))).toBe(true);
  });

  it('falls back to the extension when the browser reports no type', () => {
    expect(isSupportedImage(makeFile('a.JPEG', ''))).toBe(true);
    expect(isSupportedImage(makeFile('a.txt', ''))).toBe(false);
    expect(isSupportedImage(makeFile('noextension', ''))).toBe(false);
  });

  it('rejects other image formats', () => {
    expect(isSupportedImage(makeFile('a.gif', 'image/gif'))).toBe(false);
  });
});

describe('validateImage', () => {
  it('asks for a file when nothing is selected', () => {
    expect(validateImage(null)).toBe('Choose a photo to inspect.');
  });

  it('rejects an empty file', () => {
    expect(validateImage(makeFile('empty.png', 'image/png', 0))).toBe(
      'That file is empty. Choose a photo.',
    );
  });

  it('rejects an unsupported type', () => {
    expect(validateImage(makeFile('photo.gif', 'image/gif'))).toBe('Use a JPEG or PNG photo.');
  });

  it('rejects a file over the upload limit', () => {
    const tooBig = makeFile('big.png', 'image/png', MAX_IMAGE_BYTES + 1);

    expect(validateImage(tooBig)).toContain('10 MB');
  });

  it('accepts a photo exactly at the limit', () => {
    expect(validateImage(makeFile('edge.png', 'image/png', MAX_IMAGE_BYTES))).toBeNull();
  });
});
